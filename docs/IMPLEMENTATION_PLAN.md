# IndicF5 Voice-Cloning Proof of Concept: Implementation Handoff

## 1. Objective and current state

Build a local Python 3.12 proof of concept that uses a consented 20–60 second recording of the user's spouse, plus its exact transcript, to synthesize new Hindi and Hinglish WAV files in the same voice with AI4Bharat IndicF5.

This proof of concept is now the only active milestone. It supersedes the previous intake-assistant implementation order until voice similarity, intelligibility, code-switching, and local runtime feasibility pass the manual gate in this document. Do not build FastAPI, a frontend, Whisper, Qwen, Pipecat, LiveKit, SIP, a consultation workflow, a database, RAG, model training, or telephony during this phase.

The repository currently has no application code or model assets. `new.txt` is the source request; `AGENTS.md` remains authoritative for repository-wide privacy and scope rules. Reference recordings, transcripts containing private speech, generated audio, Hugging Face credentials, model weights, and caches must remain outside Git.

## 2. Verified upstream facts and decisions

The implementation must verify signatures again against the revision actually installed. The current official guidance establishes:

- Official source: [AI4Bharat/IndicF5](https://github.com/AI4Bharat/IndicF5).
- Official model: [ai4bharat/IndicF5](https://huggingface.co/ai4bharat/IndicF5).
- The model repository is gated; the user must accept its access terms and authenticate locally before the first download.
- The official repository demonstrates Python 3.10, but this project uses Python 3.12 after compatibility verification. Prefer 3.12 over 3.14 because the IndicF5/PyTorch audio stack has broader wheel and dependency support on 3.12. Install IndicF5 with `pip install git+https://github.com/ai4bharat/IndicF5.git`.
- The official API loads `AutoModel.from_pretrained("ai4bharat/IndicF5", trust_remote_code=True)` and invokes the model with target text, `ref_audio_path`, and `ref_text`.
- Official output examples save float audio at 24,000 Hz with `soundfile`.
- IndicF5 lists Hindi among its 11 supported languages. It does not list English or Hinglish as separately supported languages. English-reference and Hinglish code-switching quality are experiments, not promises.
- Loading gated custom code and weights is a trust boundary. Pin the validated IndicF5 source commit and model revision in the finished setup rather than tracking moving `main`.

Use CUDA automatically when `torch.cuda.is_available()` is true and the installed IndicF5 revision supports the selected placement path. Otherwise use CPU and state that generation may be slow. Do not silently substitute a cloud service or another TTS model. Native Windows dependency compatibility is unknown; attempt the documented Windows setup first, then record the concrete blocker and use WSL2 only if required.

## 3. Target layout

Create this isolated subproject:

```text
voice-clone-poc/
  app.py
  requirements.txt
  README.md
  evaluation.md
  samples/
    spouse_hindi.wav       # local, optional, ignored
    spouse_english.wav     # local, optional, ignored
    spouse_hinglish.wav    # local, default, ignored
  outputs/                 # generated WAV files, ignored
```

Also update the repository `.gitignore` so the three private reference recordings, all generated output audio, local virtual environments, Hugging Face/model caches, and credentials cannot be committed. Keep empty `samples/` and `outputs/` directories with safe placeholder files only if Git requires them. Do not add a real recording, transcript, generated voice file, access token, or model weight to the repository.

## 4. Runtime and configuration contract

### Reference profiles

`app.py` must define these stable control constants:

```python
REFERENCE_MODE = "hinglish"

REFERENCE_TEXT = """<replace this with the exact words spoken in spouse_hinglish.wav>"""

HINDI_REFERENCE_TEXT = """<replace with the exact Hindi reference transcript>"""
ENGLISH_REFERENCE_TEXT = """<replace with the exact English reference transcript>"""
```

Private exact transcript overrides belong in the ignored local file `reference_texts.local.json`, keyed by mode. This keeps the tracked implementation usable without committing a person's transcript. The Hinglish override is required by the current request; Hindi and English remain placeholders until their own consented recordings and exact transcripts exist.

Map the only allowed modes—`hindi`, `english`, and `hinglish`—to their matching audio path and transcript. `REFERENCE_TEXT` is the Hinglish fallback required by the request; it must not be renamed away. The Hinglish profile is the default for Hinglish targets. Each mode is independently usable only after its own recording and exact transcript are present.

Pass the selected transcript to IndicF5 byte-for-byte as authored in the tracked constant or ignored local override. Do not trim, transliterate, translate, punctuate, case-fold, spell-correct, or otherwise normalize it automatically. Treat an unchanged placeholder as missing, not as a valid non-empty transcript.

Reference recording guidance in the README:

- one consented speaker;
- approximately 20–60 seconds;
- natural speech matching the profile language;
- minimal background noise;
- no music;
- no clipping;
- as little room echo as practical;
- transcript exactly matches every spoken word, including code-switching and disfluencies intentionally retained.

Do not implement audio cleanup in this milestone. A poor source recording should fail manual quality review, not be silently transformed.

### Model lifecycle and device reporting

Use one lazy, process-local model instance. Validate CLI inputs before loading or downloading the model. The first valid generation may load it; subsequent generations in the same process must reuse it.

At startup/model load, print or log:

- `CUDA available: True|False`;
- GPU name when CUDA is available, otherwise an explicit CPU message;
- selected execution device;
- model ID and pinned revision;
- `Model loaded successfully` only after loading actually completes.

If device placement is controlled inside the installed IndicF5 custom code, follow that revision's documented API rather than calling an unsupported `.to(...)`. Confirm actual parameter/device placement after load and fail clearly if CUDA was selected but the model is not usable there.

### Generation API

Implement this public function exactly:

```python
def generate_voice(text: str, output_path: str) -> None:
    ...
```

It uses the currently selected reference profile, invokes the already-loaded IndicF5 model, converts `int16` output to normalized `float32` only when needed, and writes a stable WAV file at 24 kHz. If the pinned model revision requires another sampling rate, use that rate and update this plan and README with evidence; never relabel samples with the wrong rate.

The function must not return before the WAV is fully written. It must not overwrite a reference recording. An explicit output path may overwrite an existing generated output only when that path was deliberately supplied; automatic names must be collision-resistant.

## 5. CLI contract

Required custom-generation form:

```powershell
python app.py --text "Aap currently koi medicines le rahe hain?"
```

Full form:

```powershell
python app.py --text "Aap currently koi medicines le rahe hain?" --reference hinglish --output outputs/custom.wav
```

CLI behavior:

- `--text` accepts one non-empty target utterance.
- `--reference` accepts only `hindi`, `english`, or `hinglish` and defaults to `REFERENCE_MODE`.
- `--output` is optional. When omitted, create a collision-resistant `.wav` name under `outputs/`.
- Resolve bundled paths relative to `app.py`, not the caller's current directory.
- Create the output parent directory when absent.
- Return a nonzero exit code and a concise actionable error for invalid input, missing references, placeholder/empty transcripts, access/authentication failure, model-load failure, generation failure, or write failure.
- Do not catch `KeyboardInterrupt` as an ordinary generation error.

Support one explicit batch command for the required evaluation set:

```powershell
python app.py --generate-tests --reference hinglish
```

`--generate-tests` and `--text` are mutually exclusive. The batch command generates these exact files and target strings:

| Output | Target text |
| --- | --- |
| `outputs/test_01.wav` | `Namaste, aapko kya problem ho rahi hai?` |
| `outputs/test_02.wav` | `Okay ma'am, aap mujhe batayiye ki aapko ye problem kitne time se ho rahi hai.` |
| `outputs/test_03.wav` | `Aap currently koi medicines le rahe hain?` |
| `outputs/test_04.wav` | `Aap Kapiva ka product kitne time se use kar rahe hain?` |
| `outputs/test_05.wav` | `Okay, aur aapko diabetes, blood pressure ya thyroid ki koi problem hai?` |

Load the model once for the whole batch. Fail the command if any requested output fails; identify the failed phrase and leave already completed files visible rather than claiming the whole batch succeeded.

## 6. Validation and logging

Run these checks in order before inference:

1. Target text is present and not whitespace-only.
2. Reference mode is one of the three allowed values.
3. Selected reference transcript is neither empty nor an unchanged placeholder.
4. Selected reference audio exists and is a regular readable file.
5. Explicit output does not resolve to any configured reference file.
6. Output parent exists or can be created.
7. Model loads successfully and is callable.

Use actionable errors naming the selected mode and expected path, but never print the reference transcript or inspect/log the private audio content. Basic WAV readability may be checked before model load; do not normalize or rewrite the source.

For each generation, log to the console:

- selected reference mode;
- target text, as explicitly required for this local POC;
- generation start;
- generation complete;
- resolved output path;
- elapsed generation time measured with a monotonic clock.

Do not log the reference transcript, audio samples, access tokens, environment dumps, or model-cache paths. The README must warn that target text appears in console logs and should not contain real patient data during this POC.

## 7. Ordered implementation tasks

Complete tasks in order. Do not claim a task or the quality gate complete without running its acceptance checks.

### P01 — Record environment and install the official stack

Record Windows version, RAM, GPU model/VRAM, NVIDIA driver, CUDA compatibility, and free disk space before downloading weights. Create `voice-clone-poc/` and a Python 3.12 virtual environment. Start from the official IndicF5 Git installation method. Install compatible PyTorch, NumPy, SoundFile, Transformers, IndicF5, and its declared dependencies.

After a real successful install, pin exact compatible versions plus the IndicF5 Git commit in `requirements.txt`; do not invent pins in advance. Document the tested PowerShell setup. Include Hugging Face model-access acceptance and local authentication steps without embedding a token. If PyTorch needs a CUDA-specific index URL, document the exact tested command separately from the requirements install.

Acceptance:

- the activated environment reports Python 3.12;
- imports for `torch`, `numpy`, `soundfile`, `transformers`, and IndicF5 dependencies succeed;
- CUDA availability and GPU name are recorded;
- a clean reinstall command is documented;
- no private/model artifact is tracked.

### P02 — Implement reference configuration and validation

Add the three reference profiles, exact transcript placeholders, ignored local transcript overrides, path resolution, CLI parsing, validation, automatic output naming, and concise errors. Keep reference text unchanged from its source constant or local override through the model call.

Acceptance:

- `python app.py --help` documents custom and batch modes;
- empty text, unknown mode, missing audio, placeholder transcript, and unsafe output/reference collision each fail before model loading;
- omitted output yields a unique path under `outputs/`;
- commands work when launched both inside `voice-clone-poc/` and from the repository root.

### P03 — Integrate and smoke-test IndicF5

Load `ai4bharat/IndicF5` once with the pinned official API and `trust_remote_code=True`. Implement device reporting, `generate_voice`, dtype handling, 24 kHz WAV writing, monotonic timing, and logging.

This task requires one consented reference WAV and its exact transcript to be supplied locally. First generate a short synthetic target with the selected profile. Inspect the resulting file metadata and listen to it; successful file creation alone does not establish voice quality.

Acceptance:

- the model-load success message is emitted only after a usable load;
- two generations in one process use one model load;
- output is a readable, non-empty mono WAV at the actual documented sample rate;
- CUDA is used when available and supported by the pinned stack, otherwise CPU use is explicit;
- no reference transcript or audio content appears in logs;
- the spoken result is intelligible in a manual listen.

### P04 — Generate the five-phrase comparison set

Run the exact batch through the Hinglish reference to create `test_01.wav` through `test_05.wav`. If Hindi and English references are available, rerun the same five targets into separate local comparison directories or filenames without overwriting the Hinglish baseline.

Acceptance:

- all five required Hinglish-reference outputs are readable WAV files;
- each file audibly corresponds to its requested phrase;
- model weights are loaded once per batch;
- measured generation time is recorded per phrase;
- generated files remain ignored by Git.

### P05 — Evaluate the quality gate

Create `evaluation.md` with this 1–5 manual-rating table:

| Test | Voice similarity | Hindi pronunciation | English pronunciation | Hinglish naturalness | Notes |
| ---- | ---------------- | ------------------- | --------------------- | -------------------- | ----- |
| `test_01` |  |  |  |  |  |
| `test_02` |  |  |  |  |  |
| `test_03` |  |  |  |  |  |
| `test_04` |  |  |  |  |  |
| `test_05` |  |  |  |  |  |

The consented speaker and user should rate each output. Notes must explicitly cover voice resemblance, Hindi pronunciation, English words inside Hindi, `Kapiva`, medicine names, numbers/dosage where tested, natural pauses, speaking speed, artifacts, and instability. Leave ratings blank until a person has listened; never fabricate subjective scores.

The gate passes only when all five unseen sentences:

- sound reasonably similar to the consented speaker by manual review;
- remain understandable;
- pronounce English words inside Hinglish acceptably;
- generate entirely locally after the one-time model download;
- produce repeatable readable WAV output.

Record failures exactly. Do not tune against or edit the five target strings merely to make the gate pass. Reference choice, recording quality, punctuation, and model limitations may be compared, but every comparison must identify its reference mode.

Write `voice-clone-poc/README.md` only after commands have been exercised. Cover prerequisites, Python 3.12, virtual-environment setup, tested installation, model access/authentication, CUDA/GPU notes, CPU limitations, placement and quality of reference audio, exact transcript replacement, all CLI forms, batch generation, output locations, troubleshooting, the Colab notebook, and known Hindi/Hinglish/English limitations.


State prominently that cloning or generating a person's voice requires that speaker's informed consent and that generated clips can be mistaken for real speech. Keep generated clips private and do not use them to deceive, impersonate, authenticate, or contact third parties.

Acceptance:

- every documented command matches an exercised command or is clearly labeled conditional;
- setup starts from a clean Python 3.12 environment;
- README does not claim English/Hinglish support beyond observed results;
- README explains deletion of references, outputs, model caches, and local credentials.

## 8. Verification checklist

Use PowerShell-friendly commands. Exact install commands and pins are outputs of P01, not assumptions in this planning-only repository.

```powershell
cd voice-clone-poc
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python --version
python -m pip install --upgrade pip
# Install the verified PyTorch build for this workstation.
pip install -r requirements.txt
python app.py --help
python app.py --text "Aap currently koi medicines le rahe hain?"
python app.py --generate-tests --reference hinglish
```

For the real-model smoke test, record:

- installed IndicF5 source commit and Hugging Face model revision;
- Python, PyTorch, and CUDA versions;
- selected device and GPU;
- reference mode, source duration, channels, sample rate, and encoding—never its transcript/content;
- output channels, sample rate, frame count, and encoding;
- cold model-load time and per-generation elapsed time;
- manual intelligibility result and all five evaluation ratings.

Validation failures can be exercised without model access. Real generation and subjective similarity cannot be verified until the user places a consented local sample, supplies its exact transcript, accepts the gated model terms, and the weights load on the workstation. Mark those checks blocked rather than replacing the model or fabricating output.

## 9. Deferred intake-assistant phase

Only after P05 passes should planning resume for:

```text
Whisper STT
  -> deterministic consultation questionnaire
  -> local Qwen extraction
  -> cloned IndicF5 TTS
  -> browser streaming and interruption handling
```

That later phase must preserve the original project boundaries: English/Hindi/Hinglish intake, 15 required questions, structured JSON plus readable summary, no diagnosis or prescribing, explicit confirmation of important values, and reviewed predefined safety questions. Passing this POC proves only voice-cloning feasibility; it does not prove latency, streaming behavior, medical safety, or full consultation readiness.

## 10. Implementing-model instruction

Read `AGENTS.md`, this plan, and any existing progress file. Execute the earliest unfinished `Pxx` task whose prerequisites are available. Keep the POC inside `voice-clone-poc/`; do not scaffold the deferred assistant. Never download unspecified models, add private assets, normalize the reference transcript, replace IndicF5 with a fake, or report unrun checks as passed. End each task with changed behavior, exact commands and observed results, blocked checks, and the next task ID.
