# Multimodal Agents

Companion code for *Building Production Multimodal AI Agents* (Book 6 of the
Production AI Agent Engineering series).

The repository follows the book from synchronized camera-and-voice capture to
visual grounding, video, screen agents, document understanding, Qdrant-backed
multimodal retrieval, cited RAG, event memory, sensors, policy gates,
observability, PostgreSQL row-level tenant isolation, Auth0 organizations, and
the IAgentic Multimodal Studio.

The `runs/` tree retains the manifests, measurements, provider traces, and
release results cited in the manuscript. Secrets and private raw recordings do
not belong in version control.

Repository: <https://github.com/IAgentic-LLC/multimodal-agents>

## Start from a clean checkout

Python 3.12 or later is required. Install `uv`, then run:

```powershell
git clone https://github.com/IAgentic-LLC/multimodal-agents
cd multimodal-agents
uv sync
uv run pytest -q
```

Build and test the React and TypeScript Studio:

```powershell
cd frontend
npm ci
npm run build
npm run test:e2e
```

The Playwright configuration starts and stops the local Python application
automatically, so the UI suite does not depend on a server left running by a
previous session.

The authoring workspace has an additional manuscript-render audit:

```powershell
cd frontend
npm run test:book
```

That command intentionally requires the sibling `multimodal-agents-book`
checkout and its rendered HTML. It validates every chapter's opening evidence
figure, alternative text, source resolution, and desktop/mobile overflow. It
is separate from the public companion-repository suite so a clean code-only
checkout remains self-contained.

The deterministic suite requires no provider key. Live experiments use the
reader's own service accounts and environment variables; no credentials are
embedded in the code or retained artifacts.

Verify one chapter while reading:

```powershell
uv run python scripts/verify_chapter.py 18
```

Validate the complete book-to-code build-along contract:

```powershell
uv run python scripts/verify_course.py
```

`course_manifest.json` is the canonical episode map for the book and a future
YouTube playlist. It names what each episode builds, the exact files to type,
the smallest runnable demonstration, the deterministic verifier, retained
evidence, environment requirements, and the on-screen result. The manuscript's
34 “Follow along” sections are checked against this manifest so instructions
cannot silently drift away from working code.

The command runs the chapter's deterministic tests and validates its retained
JSON, JSONL, media, and trace artifacts. See `REPRODUCING.md` in the e-book for
the complete chapter-to-gate and live-service matrix.

## Gate 1: consented browser evidence capture

Run from a clean checkout with Python 3.12 or later:

```powershell
$env:PYTHONPATH = "src"
python -m multimodal_agents.server
```

Open `http://127.0.0.1:8000`, grant camera and microphone access, then hold
the record button while saying a reference such as, "Remember where I put
this." The app saves one JPEG frame, one Opus/WebM voice interval, and one
JSONL manifest entry under `runs/local-captures/`.

Captured media is local evidence, is ignored by version control, and must not
be committed.

## Production-shaped services

The repository includes Docker definitions for PostgreSQL, the API, the
Studio, Qdrant, and document-processing dependencies. See `deploy/` and the
service-specific Compose files for the exact commands and required variables.
Production authentication fails closed; the local identity harness must be
explicitly enabled and must never be used as a deployment default.
