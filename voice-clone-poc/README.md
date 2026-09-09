# IndicF5 Voice-Cloning Proof of Concept

Local proof of concept for generating Hindi/Hinglish speech from a consented speaker reference recording with AI4Bharat IndicF5.

## Current status

The Python 3.12 environment, pinned dependency installation, core imports, validation CLI, gated model access, and one real CPU generation have been verified. `outputs/test_01.wav` was created successfully; manual listening and quality evaluation are still pending.

## Verified runtime

- OS: Microsoft Windows NT 10.0.26200.0
- Python: 3.12.10 (64-bit)
- System memory: approximately 8 GiB
- GPU: Intel Iris Xe Graphics; no NVIDIA CUDA device detected
- PyTorch: 2.14.0+cpu
- CUDA available: False
- IndicF5 source commit: `13f7c4d627cc10111aea8fe9c0039462cacacdc7`
- Hugging Face model revision to use: `ba85abedf18dc479a447eaa0eccbd76ab78a47d5`

CPU generation may be slow. The model repository is gated. Accept the model terms at [ai4bharat/IndicF5](https://huggingface.co/ai4bharat/IndicF5), then authenticate locally without putting a token in this repository:

```powershell
.\.venv\Scripts\hf.exe auth login
```

Never put the token in this repository or share it in chat.

## Setup (PowerShell)

```powershell
cd voice-clone-poc
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

From the repository root, the equivalent `uv` setup is:

```powershell
uv venv --python 3.12 --seed voice-clone-poc/.venv
voice-clone-poc/.venv/Scripts/python.exe -m pip install -r voice-clone-poc/requirements.txt
```

These commands install the environment without downloading the gated model weights.

## Reference audio

Place the first reference recording at:

```text
samples/spouse_hinglish.wav
```

Then create the ignored local file `reference_texts.local.json` with the exact words spoken in that file:

```json
{
  "hinglish": "<exact words spoken in spouse_hinglish.wav>"
}
```

The tracked `REFERENCE_TEXT` constant in `app.py` intentionally remains a placeholder so a private transcript cannot be committed. Do not normalize, translate, transliterate, or otherwise alter the transcript.

Optional profiles use `samples/spouse_hindi.wav` and `samples/spouse_english.wav`, with `hindi` and `english` transcript overrides in the same ignored JSON file.

## Generation

From `voice-clone-poc/` with the environment activated:

```powershell
python app.py --text "Aap currently koi medicines le rahe hain?"
python app.py --text "Aap currently koi medicines le rahe hain?" --reference hinglish --output outputs/custom.wav
python app.py --generate-tests --reference hinglish
```

The batch command writes `outputs/test_01.wav` through `outputs/test_05.wav`. The model is gated and downloads only when the first valid generation is attempted.

On Windows, the app uses a SoundFile-backed `torchaudio.load` fallback to avoid local TorchCodec/FFmpeg DLL loading failures, and calls IndicF5's official inference function directly so the generated waveform is not passed through the model wrapper's lossy post-processing. Linux/Colab uses the normal torchaudio path.

For a hosted GPU workflow, open [`IndicF5_voice_clone_colab.ipynb`](IndicF5_voice_clone_colab.ipynb). The notebook clones this repository, authenticates interactively, uploads the private WAV, writes the private transcript only into the current runtime, and downloads generated WAV files without committing private data.

An earlier wrapper-based CPU run produced a 0.66-second two-level waveform that sounded like a beep; it was not accepted as a valid speech result. The direct inference path above is the current retry and must be manually listened to before batch generation.

## Consent and privacy

Use voice cloning only with the recorded speaker's informed consent. Keep recordings, exact transcripts, generated audio, credentials, model weights, and caches private. Generated clips can be mistaken for real speech; never use them to deceive, impersonate, authenticate, or contact third parties.
