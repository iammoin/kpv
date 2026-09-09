# Repository Guidelines

## Project Scope

Build a local, personal-use proof of concept for cloning a consenting speaker's voice with AI4Bharat IndicF5. Given a clean 20–60 second reference WAV and its exact transcript, generate five unseen Hindi/Hinglish utterances as stable local WAV files and evaluate voice similarity, intelligibility, pronunciation, pacing, and code-switching manually.

This voice-cloning feasibility gate is the only active milestone. Do not yet add Whisper, Qwen, FastAPI, a frontend, LiveKit, Pipecat, SIP, a consultation workflow, a database, RAG, model training, telephony, diagnosis, or prescribing. The later goal remains a self-hosted English/Hindi/Hinglish pre-consultation intake assistant, but implementation resumes only after the voice-quality gate in `docs/IMPLEMENTATION_PLAN.md` passes.

## Project Structure & Module Organization

Keep the proof of concept isolated:

- `voice-clone-poc/app.py`: reference configuration, validation, model lifecycle, generation function, and CLI.
- `voice-clone-poc/requirements.txt`: versions verified on the actual workstation, including a pinned IndicF5 source commit.
- `voice-clone-poc/samples/`: local consented reference WAV files; contents are ignored by Git.
- `voice-clone-poc/outputs/`: locally generated WAV files; contents are ignored by Git.
- `voice-clone-poc/README.md`: exercised installation, authentication, CUDA, usage, and cleanup instructions.
- `voice-clone-poc/evaluation.md`: blank and completed manual 1–5 quality ratings.
- `docs/IMPLEMENTATION_PLAN.md`: authoritative ordered tasks and acceptance gates.

Use only `hindi`, `english`, and `hinglish` reference modes, with Hinglish as the default for Hinglish targets. Keep each reference audio paired with its own exact transcript. Never normalize, translate, transliterate, trim, spell-correct, or otherwise alter reference text before passing it to IndicF5.

Use the official `ai4bharat/IndicF5` model and recommended `AutoModel` custom-code API. Load the model lazily and at most once per process. Prefer CUDA automatically when available and supported by the pinned stack; otherwise report explicit CPU use. Save output at the model's actual sampling rate, expected to be 24 kHz.

## Build, Test, and Development Commands

No runnable application or verified dependency lock exists yet. Use Python 3.12 and PowerShell-friendly commands. Python 3.12 is preferred over 3.14 because the IndicF5/PyTorch audio stack has broader wheel and dependency support on 3.12. Start from the official IndicF5 Git installation method, then pin only versions and revisions that successfully install and run on this workstation. Do not guess dependency versions or describe unexecuted commands as working.

The Hugging Face model is gated. Document acceptance of its access terms and local authentication, but never store a token in the repository. Validate inputs before model loading so missing audio or transcript placeholders do not trigger a large download. If native Windows installation fails, record the exact failure before documenting WSL2 as a fallback.

Once implemented, the required smoke surfaces are `python app.py --help`, one custom `--text` generation, and the five-file `--generate-tests --reference hinglish` batch described in the implementation plan.

## Coding Style & Naming Conventions

Use four-space indentation, type hints, `snake_case` functions/modules, and `PascalCase` classes. Keep the requested public signature `generate_voice(text: str, output_path: str) -> None`. Resolve bundled paths relative to `app.py`, not the caller's current directory. Use concise actionable exceptions and nonzero CLI exits; do not catch `KeyboardInterrupt` as a normal generation failure.

Keep configuration direct and boring. Preserve `REFERENCE_MODE = "hinglish"` and the required Hinglish `REFERENCE_TEXT` constant, with separate Hindi and English transcript constants. Treat unchanged transcript placeholders as invalid. Use a monotonic clock for elapsed generation time and collision-resistant automatic output names.

## Testing Guidelines

Validation checks must cover empty target text, unsupported reference mode, missing/unreadable reference audio, empty or placeholder transcript, unsafe output/reference collisions, output-directory creation, model-load failure, and write failure. These checks must fail before model inference where possible.

Real-model verification requires the consented local reference recording and exact transcript. Confirm that two generations in one process load the model once; each output is a readable, non-empty WAV at the documented rate; CUDA is actually used when selected; and all five required phrases audibly match their requested text. File creation alone is not proof of voice quality.

Manual evaluation uses a 1–5 scale for voice similarity, Hindi pronunciation, English pronunciation, and Hinglish naturalness. Notes must cover `Kapiva`, medicine names, numbers/dosage where tested, pauses, pacing, artifacts, and instability. Never fabricate listening results or subjective scores. Add permanent automated tests only for durable behavior with a plausible regression risk; otherwise use focused CLI smoke checks.

## Commit & Pull Request Guidelines

There is no commit history or established convention. Use concise imperative subjects, such as `Add IndicF5 generation CLI`. PRs should explain observable behavior, reference relevant issues, list exact validation performed, state the model/source revisions used, and report blocked real-model or manual-listening checks honestly. Never attach private recordings, transcripts, generated voice clips, credentials, model weights, or caches.

## Privacy, Consent & Scope Boundaries

Keep credentials, Hugging Face tokens, reference recordings, exact private transcripts, generated voice files, model weights, caches, and patient information out of Git. Ignore these artifacts before creating them. Do not log the reference transcript, audio samples, tokens, environment dumps, or model-cache paths. The local POC may log target text as required, so use only synthetic/non-patient target phrases.

Voice cloning and generation require the recorded speaker's informed consent. Generated clips can be mistaken for real speech: keep them private and never use them to deceive, impersonate, authenticate, or contact third parties. Loading `trust_remote_code=True` is a code-execution trust boundary; use only the official repository and pin the reviewed source and model revisions.
