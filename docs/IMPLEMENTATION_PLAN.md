# Voice Intake Assistant: Implementation Handoff

## 1. Objective and current state

Build a personal-use, self-hosted pre-consultation intake assistant for English, Hindi, and Hinglish. It asks predefined questions, accepts natural replies and corrections, avoids repeating answered questions, and exports structured JSON plus a readable summary. It does not diagnose or prescribe.

The repository currently contains only `AGENTS.md`. All paths and commands below are implementation targets, not existing capabilities. Leave `AGENTS.md` unchanged. This plan authorizes implementation work, not deployment or contacting patients.

First milestone: a cooperative five-minute Hindi/Hinglish session resolves 15 required question slots and produces a faithful summary while supporting interruptions. Five minutes is a benchmark, not a timeout: never rush a speaker or mark missing answers complete to meet it.

## 2. Decisions and boundaries

| Area | MVP decision |
| --- | --- |
| Backend | Python 3.11, FastAPI, Pydantic v2 |
| Persistence | SQLite, SQLAlchemy 2, Alembic; one local user and one active voice session |
| Browser | React, TypeScript, Vite; text mode first |
| Streaming | Pipecat SmallWebRTCTransport; local browser microphone and speaker |
| STT | Local faster-whisper, multilingual model; model size selected by benchmark |
| LLM | Local Qwen through Ollama, schema-constrained extraction; model ID configurable |
| TTS | Benchmark local Indic Parler-TTS for English/Hindi; Hinglish quality is an acceptance gate |
| Workflow | Versioned YAML, deterministic transitions, templated prompts |
| Summary | Deterministic rendering of validated state for the MVP |
| Tooling | uv, Ruff, pytest; npm, TypeScript, ESLint, Vitest, Playwright |

Use no paid/cloud inference fallback. No fine-tuning, RAG, vector database, multi-agent orchestration, telephony, clinician dashboard, or public hosting in this milestone. LLM question rephrasing and narrative summaries can follow only after deterministic behavior works.

Hardware is unknown. Record OS, RAM, GPU/VRAM, disk budget, and intended browser in `docs/runtime.md` before downloading models. Do not promise real-time CPU performance. Implement fake adapters and text mode while model deployment is unresolved. If native Windows dependencies fail, document the concrete issue and evaluate WSL2 rather than silently changing the runtime.

## 3. Target layout

```text
backend/pyproject.toml
backend/uv.lock
backend/src/intake/
  main.py                 # FastAPI application factory
  config.py               # environment validation
  api/                    # HTTP routes and WebRTC signaling
  domain/                 # schemas, workflow engine, summary renderer
  services/               # turn processing and session lifecycle
  adapters/               # Ollama, STT, TTS, fake implementations
  storage/                # SQLAlchemy models and repositories
  voice/                  # Pipecat pipeline and cancellation
backend/alembic/
frontend/src/
workflows/general_intake.v1.yaml
tests/unit/
tests/integration/
tests/fixtures/           # synthetic text and optional synthetic audio
tests/evaluation/
docs/runtime.md
docs/evaluation.md
docs/PROGRESS.md
.env.example
README.md
```

Keep domain code independent of FastAPI, Pipecat, and inference libraries. Keep optional heavy speech dependencies out of the default unit-test installation.

## 4. Data and workflow contracts

### Session and answer state

Define Pydantic contracts before adapters:

- `Session`: UUID, workflow ID/version, locale preference (`en`, `hi`, `hinglish`), timezone, timestamps, revision, status, current question ID, pending confirmation, answers.
- Session status: `created`, `active`, `paused`, `completed`, `stopped`, `needs_human_review`.
- `Answer`: field ID, typed value, raw text, source turn IDs, status, confirmation requirement, confirmation turn ID.
- Answer status: `unanswered`, `captured`, `confirmed`, `unknown`, `declined`, `not_applicable`. Missing is never equivalent to a negative answer.
- `Turn`: client-generated UUID, sequence, final transcript, processing status, timestamps. Interim transcripts are display-only.
- `ExtractionProposal`: allowed field updates with supporting source text and ambiguity flags. It cannot change workflow order, session status, or rules.
- `IntakeSummary`: schema/workflow versions, session ID, symptoms, duration, severity, measurements, medications, allergies, conditions, prior treatment, important negatives, unanswered questions, unconfirmed values, follow-up items, explicit reported safety flags, completion status.

Represent measurements with value, unit, and original text. Medication entries have separately nullable name, strength, dose, frequency, and last-taken fields. Never infer a dose or frequency from a product strength. Keep reported names intact; no automatic brand substitution.

Store original relative dates. Normalize only with an explicit session date/timezone and clear meaning; ambiguous `kal` needs clarification. Explicitly distinguish `none`, `unknown`, and an empty collection awaiting an answer.

### Initial questionnaire

Use these 15 proposed slots as an engineering fixture. Exact patient-facing wording and safety rules need review by the intended clinician before real use; the coding model must not invent medical thresholds or triage protocols.

| ID | Collected information |
| --- | --- |
| `chief_complaint` | Main reason for consultation |
| `onset_duration` | Start time and duration |
| `progression` | Improving, worsening, unchanged, or uncertain |
| `severity_impact` | Patient's description and effect on usual activity |
| `temperature` | Measured value/unit, not measured, or unknown |
| `associated_symptoms` | Other reported symptoms |
| `existing_conditions` | Known conditions or explicit none |
| `current_medications` | Names and details actually reported |
| `allergies` | Allergies/reactions, explicit none, or unknown |
| `previous_treatment` | Treatments already tried and reported response |
| `blood_pressure` | Reading if available; no measurement request required |
| `oxygen_saturation` | Reading if available; no measurement request required |
| `breathing_concern` | Clinician-reviewed predefined safety question |
| `chest_discomfort` | Clinician-reviewed predefined safety question |
| `fainting_confusion` | Clinician-reviewed predefined safety question |

Consent and language selection precede these slots. Each YAML question includes stable ID, localized prompts, field type, required flag, confirmation rule, skip condition, and retry limit. Unknown/declined responses resolve a slot for navigation but remain listed as unavailable in the summary. Completion requires every required slot to be resolved and no unresolved confirmation; it does not imply every clinical fact is known.

### Turn algorithm

1. Reject duplicate turn IDs; reject stale revisions; serialize updates per session.
2. Pass only final transcript, permitted fields, current answers, and pending question to extraction.
3. Validate the proposal; keep supporting text and reject unsupported fields/values.
4. Apply explicit corrections with provenance; reconfirm changed important values.
5. Capture answers volunteered for future questions; do not ask those questions again.
6. Evaluate configured safety rules before ordinary progression. A flagged session uses a fixed reviewed message and `needs_human_review`; no LLM-generated medical advice.
7. Confirm medications, dosage, allergies, temperature, BP, and SpO2 before treating them as confirmed. One short confirmation may group related values; ambiguous replies cannot confirm unrelated fields.
8. Otherwise select the earliest unresolved applicable slot. Ask one concise question at a time.
9. After two unsuccessful clarifications, offer unknown/skip or text entry; do not loop indefinitely.
10. Persist state and turn result atomically, then render the next prompt or final summary.

Malformed model output gets at most one repair attempt. Timeouts or another failure leave answers unchanged and return a retryable message. User transcript content is data, including instructions to ignore the questionnaire.

## 5. Ordered implementation tasks

Complete one task at a time. Each task must leave runnable code, relevant tests, and a short entry in `docs/PROGRESS.md`. Do not start dependent tasks with a failing prerequisite.

### T01 — Scaffold and repeatable checks

Create the target Python package, Vite application, dependency lockfiles, `.gitignore`, `.env.example`, and README. Configure Ruff, pytest discovery for root `tests/`, TypeScript, ESLint, Vitest, and Playwright. Add `/health` and an empty session screen. Ignore `.env`, local SQLite files, recordings, transcripts, model caches, and generated evaluation outputs.

Acceptance: clean dependency installation, health endpoint test, frontend build, and lint checks pass. README contains tested PowerShell-friendly commands. Pin compatible dependency versions using actual installation results, not guessed version numbers.

### T02 — Contracts and workflow validation

Implement schemas and the 15-slot YAML with English, Hindi, and Hinglish prompts. Mark clinical wording as draft. Validate unique IDs, prompt availability, allowed field types, and referenced skip conditions at startup. Add synthetic fixtures with explicit expected normalized answers.

Acceptance: invalid workflows fail with actionable errors; summary schema distinguishes unknown, negative, and unconfirmed answers; all three prompt variants load.

### T03 — Pure questionnaire engine

Implement a pure state transition function accepting state plus a validated extraction proposal and returning new state plus the next action. Use table-driven synthetic proposals; no LLM dependency. Implement confirmation, corrections, skip/unknown, completion, stop, and configured safety interruption.

Acceptance: deterministic tests cover out-of-order answers, no repeated answered questions, correction invalidating confirmation, explicit negatives, ambiguous confirmation, exhausted retries, and incomplete sessions. `Dolo 650 le raha hoon` must not create an invented dosing frequency.

### T04 — Persistence and text API

Add migrations and session/turn persistence. Implement `POST /api/sessions`, `GET /api/sessions/{id}`, `POST /api/sessions/{id}/turns`, `POST /api/sessions/{id}/stop`, `GET /api/sessions/{id}/summary`, and `DELETE /api/sessions/{id}`. Return revision, next action, question ID, and completion state on turn responses. Use a fake extractor for integration tests.

Acceptance: a complete scripted session survives process restart; duplicate turn replay returns its prior result; conflicting revisions return 409; deletion removes associated records; missing sessions return 404. Persist turn results and revisions in a single transaction.

### T05 — Functional text interface

Build start/consent, language selection, transcript, text reply, unknown/skip, stop, progress, and result screens. Provide JSON download and readable summary. Show captured/unconfirmed values accurately. Store session identifiers only as needed; do not put transcripts in browser persistent storage.

Acceptance: Playwright completes a fake session and exports JSON; reload resumes; a stopped session is visibly incomplete; declined consent creates no intake session.

### T06 — Local extraction model

Implement an asynchronous Ollama adapter with schema-constrained output, configurable model ID, timeout, bounded repair, and cancellation. Add a strict extraction prompt and fake adapter with the same interface. Model responses propose facts only; the engine chooses actions. Keep summary rendering deterministic.

Acceptance: synthetic English/Hindi/Hinglish fixtures pass the evaluation script; malformed JSON, invented fields, prompt injection, and unavailable model tests preserve state. Record exact model ID, quantization, prompt version, latency, and observed accuracy. Do not claim fake-adapter results establish real model quality.

### T07 — Hardware and speech feasibility gate

Record runtime information and choose a multilingual faster-whisper configuration. Benchmark local TTS using Indic Parler-TTS with short English, Hindi, and mixed-language prompts, medicine names, and numbers. Read model license/runtime requirements before selecting weights. Test all three services together for memory pressure. Cache synthesized fixed questionnaire prompts to reduce latency.

Acceptance: `docs/runtime.md` records installation commands, model revisions, peak memory, cold/warm timings, audio formats, and known pronunciation failures. If Hinglish synthesis or latency fails, document the blocker and benchmark another local model; keep text mode working and do not label voice complete. Avoid automatic large downloads on application startup.

### T08 — Browser audio transport

Integrate Pipecat SmallWebRTC signaling into FastAPI and its matching browser client. Add microphone permission, connect/disconnect, mute, visible connection state, and audio playback. Use a fake speech pipeline first. Expose local session-bound signaling; release resources on disconnect.

Acceptance: browser sends microphone audio and receives test speech; permission denial and disconnect are recoverable; repeated connects do not leak tasks or audio devices. Document localhost/secure-context requirements and supported browser.

### T09 — Connect the voice turn loop

Wire audio to VAD, STT, the same turn service used by text mode, and TTS. Resample explicitly at adapter boundaries. Whisper is utterance-based here: do not claim native streaming recognition. Display interim text separately if supported; only finalized utterances mutate the engine. Serialize turns and keep inference off the API event loop.

Acceptance: spoken English, Hindi, and Hinglish produce summaries through the shared engine; silence does not create answers; model errors permit retry/text entry; independent sessions cannot share state.

### T10 — Interruptions and recovery

On detected user speech, stop playback, clear queued audio, and cancel or invalidate pending generation using an output-generation ID. Reject late audio/results from older generations. Retain the unanswered question if its playback was interrupted; use the user's final reply to decide whether it was answered. Resume paused sessions from persisted state.

Acceptance: interruption during TTS, during inference, and during confirmation produces no overlapping stale audio or duplicate state update. Disconnect during processing and rapid stop/reconnect leave a consistent session. Record observed interruption latency.

### T11 — Evaluate and package the milestone

Create at least 30 synthetic text cases (10 per language mode) and 12 consented or synthetic audio conversations (4 per mode). Include accents, code-switching, background noise, medication names, numbers, negation, corrections, uncertainty, and interruptions. Add at least three five-minute cooperative end-to-end runs.

Acceptance: publish the evaluation report below; fix failing cases before marking the milestone complete. Add setup/troubleshooting instructions, data deletion instructions, and a manual smoke-test checklist. No recordings or patient data enter Git. Report untested environments honestly.

## 6. Verification commands and release gates

T01 must make these commands work from the repository root; adjust this document if a verified tool requires a different invocation:

```powershell
uv sync --project backend --extra dev
uv run --project backend ruff check backend tests
uv run --project backend ruff format --check backend tests
uv run --project backend pytest tests/unit tests/integration
uv run --project backend uvicorn intake.main:app --reload --host 127.0.0.1
npm --prefix frontend ci
npm --prefix frontend run lint
npm --prefix frontend run test -- --run
npm --prefix frontend run build
npm --prefix frontend run test:e2e
```

Document any browser installation prerequisite and configure Playwright's web servers. Ordinary tests must run without downloaded models, audio devices, or network inference. Put real-model/audio evaluation behind a separate documented command.

Proposed engineering targets, to be measured on declared hardware:

- 100% schema-valid exported summaries and no invented facts in the curated fixture set.
- At least 95% correct annotated field values across text evaluation; report counts and results by language. Exclude unavailable values from the accuracy denominator and report them separately.
- Every critical value in the test set is either explicitly confirmed or visibly unconfirmed; no silent guess is accepted.
- Every configured positive safety fixture interrupts ordinary intake. This verifies configured behavior, not clinical sensitivity.
- All 15 slots resolved in the three cooperative milestone runs; report unknown/declined counts independently.
- Target warmed end-of-speech to first assistant audio: p95 at most 3 seconds; target speech onset to playback stop: p95 at most 500 ms. These are provisional performance goals, not measured guarantees.
- Report STT word/character error rates and critical-token errors separately. Hindi script variants may distort word error rate; extraction accuracy and manual listening remain necessary.

Use monotonic timing and report sample sizes. A failed hardware or pronunciation gate means voice remains incomplete even if automated tests pass.

## 7. Local privacy and clinical configuration

Bind services to loopback by default and configure explicit local CORS origins. No recording by default. Show consent before microphone capture; persist the minimum session data needed for resume and export. Avoid transcript/model-prompt content in logs. Provide explicit session deletion; document that exported files/backups require separate removal.

Store red-flag wording, triggers, and fixed responses in reviewed configuration. Draft fixtures may support development, but the app must indicate that clinical configuration is unreviewed until that review is recorded. Do not infer numeric emergency thresholds, claim medical validation, or ask the coding model to invent emergency advice. Real-patient use requires review of this content; it does not block engineering with synthetic data.

## 8. Instructions for the implementing model

Read `AGENTS.md`, this document, and `docs/PROGRESS.md` if present. Inspect the actual repository before editing. Execute the earliest unfinished task whose prerequisites pass. Prefer small functions and direct adapters over generic frameworks. Do not implement later phases as speculative scaffolding.

For each task, record status (`pending`, `in_progress`, `done`, `blocked`), changed files, exact checks and results, unresolved issues, and the next task. A task is done only when its acceptance checks pass. Do not replace real dependencies with stubs and call an integration complete. If hardware is unavailable, continue independent tasks and state exactly which real-model checks remain blocked.

Suggested handoff prompt:

> Implement the next unfinished task in docs/IMPLEMENTATION_PLAN.md. Follow AGENTS.md and inspect docs/PROGRESS.md first. Complete its deliverables and acceptance checks, then update the progress file. Keep the deterministic engine authoritative. Use fake adapters only where the plan permits them. Do not deploy, download unspecified large models, change the selected architecture, or claim unrun checks passed. End with changed behavior, validation results, blockers, and the next task ID.

## 9. Later phases

After the MVP passes: improve confidence-driven retries and medical vocabulary evaluation; evaluate alternative Indic STT/TTS models; consider LLM prompt rephrasing with semantic safeguards. Telephony follows as a separate project using the existing engine. Fine-tuning is considered only after a consented evaluation set identifies repeatable errors that simpler changes cannot fix.

## 10. Primary implementation references

Verify SDK signatures against the pinned versions during implementation; these references informed the architecture, not a tested dependency matrix.

- [Pipecat SmallWebRTC transport](https://docs.pipecat.ai/api-reference/server/services/transport/small-webrtc): local peer-to-peer transport and optional ICE configuration.
- [Pipecat browser voice UI](https://docs.pipecat.ai/client/guides/building-a-voice-ui): matching browser client integration.
- [faster-whisper](https://github.com/SYSTRAN/faster-whisper): local inference and CPU/GPU quantization options.
- [Ollama structured outputs](https://docs.ollama.com/capabilities/structured-outputs): schema-constrained local extraction.
- [Indic Parler-TTS model card](https://huggingface.co/ai4bharat/indic-parler-tts): English/Hindi support; mixed-language quality still needs measurement.
