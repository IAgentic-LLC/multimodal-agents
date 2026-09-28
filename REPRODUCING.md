# Reproducing the book

Install the pinned environments from a clean checkout:

```bash
uv sync
cd frontend
npm ci
cd ..
```

Verify the chapter currently being read:

```bash
uv run python scripts/verify_chapter.py CHAPTER_NUMBER
```

The verifier runs mapped deterministic tests, rejects missing or empty
retained artifacts, and parses every JSON and JSONL record. It does not call a
paid provider or overwrite evidence.

Install the pinned Gemini SDK only when repeating provider-backed runs:

```bash
uv sync --all-extras
```

## Chapter command map

The stable command for every chapter is `uv run python
scripts/verify_chapter.py N`. The additional command below recreates the main
local artifact or starts the live path where one exists.

| Ch | Additional command |
|---:|---|
| 1 | `uv run multimodal-capture` |
| 2 | `uv run python scripts/verify_chapter.py 2` |
| 3 | `uv run python -m multimodal_agents.run_grounding` |
| 4 | `uv run python scripts/verify_chapter.py 4` |
| 5 | `uv run python -m multimodal_agents.run_geometry` |
| 6 | `uv run python -m multimodal_agents.run_image_grounding` |
| 7 | `uv run python -m multimodal_agents.run_scene_reading` |
| 8 | `uv run python -m multimodal_agents.run_visual_robustness` |
| 9 | `uv run python -m multimodal_agents.run_temporal` |
| 10 | `uv run python -m multimodal_agents.run_video_sampling` |
| 11 | `uv run python scripts/verify_chapter.py 11` |
| 12–16 | `cd frontend && npx playwright test tests/capture.spec.ts` |
| 17 | `uv run python -m multimodal_agents.run_document_layout` |
| 18 | `uv run python -m multimodal_agents.run_qdrant_search` |
| 19 | `uv run python -m multimodal_agents.run_cross_modal_search` |
| 20 | `uv run python -m multimodal_agents.run_hybrid_search` |
| 21 | `uv run python -m multimodal_agents.run_multimodal_rag` |
| 22 | `uv run python -m multimodal_agents.run_event_store` |
| 23 | `uv run python -m multimodal_agents.run_memory_queries` |
| 24 | `uv run python -m multimodal_agents.run_acoustic_events` |
| 25 | `uv run python -m multimodal_agents.run_sensor_world` |
| 26 | `uv run python -m multimodal_agents.run_contradictions` |
| 27 | `uv run python -m multimodal_agents.run_policy_gate` |
| 28 | `uv run python -m multimodal_agents.run_sandbox` |
| 29 | `uv run python -m multimodal_agents.run_evaluation` |
| 30 | `uv run python -m multimodal_agents.run_failure_injection` |
| 31 | `uv run python -m multimodal_agents.run_runtime_observability` |
| 32 | `cd frontend && npx playwright test --grep "studio coordinates"` |
| 33 | `uv run python -m multimodal_agents.run_production_controls` |
| 34 | `uv run python scripts/run_release_gate.py` |

| Chapters | Gates | New live-run dependency |
|---|---|---|
| 1–4 | 0–2 | Camera, microphone, and Gemini where stated |
| 5–8 | 3–6 | Gemini for new perception runs |
| 9–12 | 7–10 | FFmpeg and Gemini for new video runs |
| 13–16 | 11–14 | Chromium through Playwright |
| 17–21 | 15–20 | Tika, Qdrant, and Gemini embeddings where stated |
| 22–27 | 21–26 | Deterministic local fixtures |
| 28–32 | 27–31 | Docker for the production-shaped stack |
| 33–34 | 32–34 | Oracle Cloud and Auth0 for new live evidence |

Run the full deterministic and browser regression suite with:

```bash
uv run pytest -q
cd frontend
npm run build
npm run test:e2e
```

`npm run test:e2e` starts the local application server itself and excludes
the manuscript-only review audit. In the author's combined book-and-code
workspace, render the book to HTML and run `npm run test:book` to check all 34
chapter figures at desktop and mobile sizes.

The checked-in `runs/gate-*` artifacts reproduce the reported observations
without the author's private credentials. A reader's live provider result is a
new experiment and should not overwrite the retained book artifact.
