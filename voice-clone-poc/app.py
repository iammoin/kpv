"""Local IndicF5 voice-cloning proof of concept."""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
import types
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

import numpy as np
import soundfile as sf
import torch
from transformers import AutoModel

BASE_DIR = Path(__file__).resolve().parent
MODEL_ID = "ai4bharat/IndicF5"
MODEL_REVISION = "ba85abedf18dc479a447eaa0eccbd76ab78a47d5"
OUTPUT_SAMPLE_RATE = 24_000

REFERENCE_MODE = "hinglish"
REFERENCE_TEXT = """<replace this with the exact words spoken in spouse_hinglish.wav>"""
HINDI_REFERENCE_TEXT = """<replace with the exact Hindi reference transcript>"""
ENGLISH_REFERENCE_TEXT = """<replace with the exact English reference transcript>"""

_ALLOWED_REFERENCE_MODES = ("hindi", "english", "hinglish")
_REFERENCE_FILES = {
    "hindi": "spouse_hindi.wav",
    "english": "spouse_english.wav",
    "hinglish": "spouse_hinglish.wav",
}
_REFERENCE_TEXTS = {
    "hindi": HINDI_REFERENCE_TEXT,
    "english": ENGLISH_REFERENCE_TEXT,
    "hinglish": REFERENCE_TEXT,
}

LOCAL_REFERENCE_TEXTS = BASE_DIR / "reference_texts.local.json"
_TEST_PHRASES = (
    "Namaste, aapko kya problem ho rahi hai?",
    "Okay ma'am, aap mujhe batayiye ki aapko ye problem kitne time se ho rahi hai.",
    "Aap currently koi medicines le rahe hain?",
    "Aap Kapiva ka product kitne time se use kar rahe hain?",
    "Okay, aur aapko diabetes, blood pressure ya thyroid ki koi problem hai?",
)

LOGGER = logging.getLogger("indicf5_poc")
_MODEL = None
_MODEL_DEVICE: torch.device | None = None
_ACTIVE_REFERENCE_MODE = REFERENCE_MODE


@dataclass(frozen=True)
class ReferenceProfile:
    mode: str
    audio_path: Path
    transcript: str


class GenerationError(RuntimeError):
    """An actionable user-facing generation error."""


def _configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")


def _reference_transcript(mode: str) -> str:
    if not LOCAL_REFERENCE_TEXTS.exists():
        return _REFERENCE_TEXTS[mode]
    try:
        local_texts = json.loads(LOCAL_REFERENCE_TEXTS.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GenerationError(
            f"Could not read local reference transcripts from {LOCAL_REFERENCE_TEXTS}: {exc}"
        ) from exc
    if not isinstance(local_texts, dict):
        raise GenerationError(
            f"Local reference transcripts must be a JSON object: {LOCAL_REFERENCE_TEXTS}"
        )
    transcript = local_texts.get(mode, _REFERENCE_TEXTS[mode])
    if not isinstance(transcript, str):
        raise GenerationError(f"Local transcript for reference mode {mode!r} must be a string.")
    return transcript


def _reference_profile(mode: str) -> ReferenceProfile:
    if mode not in _ALLOWED_REFERENCE_MODES:
        allowed = ", ".join(_ALLOWED_REFERENCE_MODES)
        raise GenerationError(f"Unknown reference mode {mode!r}; choose one of: {allowed}.")
    return ReferenceProfile(
        mode=mode,
        audio_path=BASE_DIR / "samples" / _REFERENCE_FILES[mode],
        transcript=_reference_transcript(mode),
    )


def _is_placeholder(transcript: str) -> bool:
    normalized = transcript.strip().lower()
    return not normalized or normalized.startswith("<replace")


def _resolved_path(path: Path) -> Path:
    return path.expanduser().resolve(strict=False)


def _same_path(left: Path, right: Path) -> bool:
    return os.path.normcase(str(_resolved_path(left))) == os.path.normcase(
        str(_resolved_path(right))
    )


def _validate_reference(profile: ReferenceProfile) -> None:
    if _is_placeholder(profile.transcript):
        raise GenerationError(
            "Create reference_texts.local.json with the exact spoken text or replace "
            "the corresponding transcript constant in app.py."
        )
    if not profile.audio_path.exists():
        raise GenerationError(
            f"Reference audio for mode {profile.mode!r} was not found: "
            f"{profile.audio_path}. Place the WAV file in voice-clone-poc/samples/."
        )
    if not profile.audio_path.is_file():
        raise GenerationError(f"Reference audio path is not a regular file: {profile.audio_path}.")
    try:
        sf.info(profile.audio_path)
    except Exception as exc:
        raise GenerationError(
            f"Reference audio for mode {profile.mode!r} is not readable as audio: "
            f"{profile.audio_path} ({exc})."
        ) from exc


def _validate_request(text: str, mode: str, output_path: Path) -> ReferenceProfile:
    if not text or not text.strip():
        raise GenerationError("Target text must not be empty or whitespace-only.")
    profile = _reference_profile(mode)
    _validate_reference(profile)
    configured_references = (
        BASE_DIR / "samples" / filename for filename in _REFERENCE_FILES.values()
    )
    if any(_same_path(output_path, reference_path) for reference_path in configured_references):
        raise GenerationError("Output path must not overwrite a configured reference audio file.")
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise GenerationError(f"Could not create output directory {output_path.parent}: {exc}") from exc
    return profile


def _output_path(value: str | None) -> Path:
    if value is None:
        return _automatic_output_path()
    if not value.strip():
        raise GenerationError("Output path must not be empty.")
    candidate = Path(value).expanduser()
    if not candidate.is_absolute():
        candidate = BASE_DIR / candidate
    return candidate


def _select_device() -> torch.device:
    cuda_available = torch.cuda.is_available()
    LOGGER.info("CUDA available: %s", cuda_available)
    if cuda_available:
        device = torch.device("cuda")
        LOGGER.info("GPU name: %s", torch.cuda.get_device_name(device))
    else:
        device = torch.device("cpu")
        LOGGER.info("GPU name: none detected; using CPU")
    LOGGER.info("Selected execution device: %s", device)
    return device



def _prepare_inference_imports() -> None:
    """Avoid importing IndicF5's training-only dataset path on affected Windows hosts."""
    if sys.platform != "win32":
        return
    try:
        import pyarrow.dataset  # noqa: F401
    except ImportError as exc:
        if "Application Control policy" not in str(exc):
            raise
        trainer_module = types.ModuleType("f5_tts.model.trainer")
        trainer_module.Trainer = object
        sys.modules.setdefault("f5_tts.model.trainer", trainer_module)
def _prepare_torchaudio_loader() -> None:
    """Use SoundFile for WAV references instead of TorchCodec on Windows."""
    if sys.platform != "win32":
        return
    import torchaudio

    def load_with_soundfile(
        filepath,
        frame_offset: int = 0,
        num_frames: int = -1,
        normalize: bool = True,
        channels_first: bool = True,
        format=None,
        buffer_size: int = 4096,
    ):
        del normalize, format, buffer_size
        frames = -1 if num_frames < 0 else num_frames
        samples, sample_rate = sf.read(
            filepath,
            start=frame_offset,
            stop=None if frames < 0 else frame_offset + frames,
            always_2d=True,
            dtype="float32",
        )
        tensor = torch.from_numpy(samples.T if channels_first else samples)
        return tensor, sample_rate

    torchaudio.load = load_with_soundfile


def _load_model():
    global _MODEL, _MODEL_DEVICE
    if _MODEL is not None:
        return _MODEL

    device = _select_device()
    LOGGER.info("Loading model %s at revision %s", MODEL_ID, MODEL_REVISION)
    try:
        _prepare_inference_imports()
        _prepare_torchaudio_loader()
        model = AutoModel.from_pretrained(
            MODEL_ID,
            revision=MODEL_REVISION,
            trust_remote_code=True,
        )
        if device.type == "cuda":
            model = model.to(device)
        if not callable(model):
            raise TypeError("loaded model is not callable")
    except Exception as exc:
        raise GenerationError(
            "IndicF5 could not be loaded. Confirm gated model access, Hugging Face authentication, "
            f"and compatible dependencies ({exc})."
        ) from exc

    _MODEL = model
    _MODEL_DEVICE = device
    LOGGER.info("Model loaded successfully")
    return _MODEL


def set_reference_mode(mode: str) -> None:
    """Select the reference profile used by generate_voice."""
    global _ACTIVE_REFERENCE_MODE
    _reference_profile(mode)
    _ACTIVE_REFERENCE_MODE = mode


def _audio_array(audio) -> np.ndarray:
    if isinstance(audio, torch.Tensor):
        audio = audio.detach().cpu().numpy()
    array = np.asarray(audio)
    array = np.squeeze(array)
    if array.ndim != 1:
        raise GenerationError(f"IndicF5 returned unsupported audio shape {array.shape}; expected mono audio.")
    if array.size == 0:
        raise GenerationError("IndicF5 returned empty audio.")
    if np.issubdtype(array.dtype, np.integer):
        numeric = array.astype(np.float32)
        max_sample = float(np.max(np.abs(numeric)))
        if max_sample > 1.0:
            if max_sample <= 32_768.0:
                scale = 32_768.0
            else:
                info = np.iinfo(array.dtype)
                scale = float(max(abs(info.min), info.max))
            numeric /= scale
        array = numeric
    else:
        array = array.astype(np.float32, copy=False)
    if not np.isfinite(array).all():
        raise GenerationError("IndicF5 returned non-finite audio samples.")
    return np.clip(array, -1.0, 1.0)


def _run_inference(model, profile: ReferenceProfile, text: str):
    """Run IndicF5's inference pipeline without its lossy pydub post-processing."""
    from f5_tts.infer.utils_infer import infer_process

    if _MODEL_DEVICE is None:
        raise GenerationError("IndicF5 execution device was not initialized.")
    audio, sample_rate, _ = infer_process(
        str(profile.audio_path),
        profile.transcript,
        text,
        model.ema_model,
        model.vocoder,
        mel_spec_type="vocos",
        speed=getattr(model.config, "speed", 1.0),
        device=_MODEL_DEVICE,
    )
    return audio, sample_rate


def generate_voice(text: str, output_path: str) -> None:
    """Generate one WAV file using the selected reference profile."""
    destination = _resolved_path(Path(output_path))
    profile = _validate_request(text, _ACTIVE_REFERENCE_MODE, destination)
    LOGGER.info("Reference mode: %s", profile.mode)
    LOGGER.info("Target text: %s", text)
    model = _load_model()
    LOGGER.info("Generation start")
    started = time.monotonic()
    try:
        with torch.inference_mode():
            audio, sample_rate = _run_inference(model, profile, text)
        samples = _audio_array(audio)
        sf.write(destination, samples, sample_rate, subtype="PCM_16")
    except GenerationError:
        raise
    except Exception as exc:
        raise GenerationError(f"IndicF5 generation or WAV writing failed: {exc}") from exc
    elapsed = time.monotonic() - started
    LOGGER.info("Generation complete")
    LOGGER.info("Output path: %s", destination)
    LOGGER.info("Approximate generation time: %.2f seconds", elapsed)
def _automatic_output_path() -> Path:
    return BASE_DIR / "outputs" / f"output_{uuid4().hex}.wav"



def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate local Hindi/Hinglish speech with IndicF5.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--text", help="Exact target text to synthesize.")
    group.add_argument(
        "--generate-tests",
        action="store_true",
        help="Generate the five required evaluation phrases under outputs/.",
    )
    parser.add_argument(
        "--reference",
        choices=_ALLOWED_REFERENCE_MODES,
        default=REFERENCE_MODE,
        help="Reference profile to use (default: %(default)s).",
    )
    parser.add_argument(
        "--output",
        help="Output WAV path for --text; defaults to a unique path under outputs/.",
    )
    return parser


def _run(args: argparse.Namespace) -> None:
    set_reference_mode(args.reference)
    if args.generate_tests:
        if args.output:
            raise GenerationError("--output can only be used with --text, not --generate-tests.")
        for index, phrase in enumerate(_TEST_PHRASES, start=1):
            output_path = BASE_DIR / "outputs" / f"test_{index:02d}.wav"
            generate_voice(phrase, str(output_path))
        return

    output_path = _output_path(args.output)
    generate_voice(args.text, str(output_path))


def main(argv: list[str] | None = None) -> int:
    _configure_logging()
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        _run(args)
    except GenerationError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
