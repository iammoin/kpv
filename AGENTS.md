# Repository Guidelines

## Project Scope

Build a personal-use, self-hosted voice assistant for pre-consultation intake in English, Hindi, and Hinglish. Collect information and produce structured JSON plus a readable summary; do not diagnose or prescribe. The first milestone is a five-minute conversation completing 15 required questions, handling interruptions, and extracting answers without model training.

## Project Structure & Module Organization

The repository is currently uninitialized application scaffolding: no source code, tests, or build configuration exists. Use these proposed directories when implementation begins:

- `backend/`: FastAPI APIs, session state, questionnaire engine, and model adapters.
- `workflows/`: versioned question definitions, required fields, and predefined red-flag questions.
- `frontend/`: browser microphone, playback, and session interface.
- `tests/`: unit tests, integration tests, and synthetic multilingual conversations.
- `docs/`: architecture, local setup, and evaluation procedures.

Keep STT, LLM, TTS, and streaming integrations separate from questionnaire logic. Start with SQLite or PostgreSQL, a Whisper-family STT model, a local open-weight LLM, and local TTS. Select LiveKit Agents or Pipecat before implementing streaming.

## Build, Test, and Development Commands

No runnable build, development, or test commands exist yet. When adding scaffolding, document exact installation, server startup, model setup, and test commands in `README.md`. Provide `.env.example` with placeholder configuration. Do not describe planned commands as working commands.

## Coding Style & Naming Conventions

Use four-space indentation, type hints, and `snake_case` for Python functions and modules; use `PascalCase` for classes. Prefer explicit validation models for intake data. Keep questionnaire field identifiers stable and separate translated prompts from control logic. Configure formatting and linting with the initial scaffold.

## Testing Guidelines

Use pytest for backend tests once configured; name files `test_*.py`. Test state transitions, previously answered questions, interrupted turns, unanswered fields, and JSON validation. Include synthetic English, Hindi, and Hinglish replies covering medication names and numeric values. Confirm important values before finalizing them. No coverage threshold is established yet.

## Commit & Pull Request Guidelines

There is no commit history or established convention. Use concise imperative subjects, such as `Add questionnaire state transitions`. PRs should explain behavior, reference relevant issues, and report validation performed. Include screenshots for UI changes and synthetic input/output examples for intake changes.

## Privacy & Scope Boundaries

Keep credentials, recordings, transcripts, patient information, and model weights out of Git. Use synthetic fixtures. Keep diagnosis, prescribing, model training, and telephony outside the initial MVP.
