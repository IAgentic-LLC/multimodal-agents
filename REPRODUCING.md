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

The pinned Gemini SDK is installed by `uv sync` because the deterministic
suite imports the same provider adapters used by live runs. Tests do not call
Gemini and require no provider key; only the explicit live-run commands make
network requests.

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
| 10 | `uv run python -m multimodal_agents.run_temporal` |
| 11 | `uv run python -m multimodal_agents.run_video_sampling` |
| 12 | `uv run python scripts/verify_chapter.py 12` |
| 13–17 | `cd frontend && npx playwright test tests/capture.spec.ts` |
| 18 | `uv run python -m multimodal_agents.run_document_layout` |
| 19 | `uv run python -m multimodal_agents.run_qdrant_search` |
| 20 | `uv run python -m multimodal_agents.run_cross_modal_search` |
| 21 | `uv run python -m multimodal_agents.run_hybrid_search` |
| 22 | `uv run python -m multimodal_agents.run_multimodal_rag` |
| 23 | `uv run python -m multimodal_agents.run_event_store` |
| 24 | `uv run python -m multimodal_agents.run_memory_queries` |
| 25 | `uv run python -m multimodal_agents.run_acoustic_events` |
| 26 | `uv run python -m multimodal_agents.run_sensor_world` |
| 27 | `uv run python -m multimodal_agents.run_contradictions` |
| 28 | `uv run python -m multimodal_agents.run_policy_gate` |
| 29 | `uv run python -m multimodal_agents.run_sandbox` |
| 30 | `uv run python -m multimodal_agents.run_evaluation` |
| 31 | `uv run python -m multimodal_agents.run_failure_injection` |
| 32 | `uv run python -m multimodal_agents.run_runtime_observability` |
| 33 | `cd frontend && npx playwright test --grep "studio coordinates"` |
| 34 | `uv run python -m multimodal_agents.run_production_controls` |
| 35 | `uv run python scripts/run_release_gate.py` |
| 36 | `uv run python scripts/smoke_multi_agent_live.py` |
| 37 | `uv run python src/multimodal_agents/run_opensearch_index.py --reset` |
| 38 | `uv run pytest tests/test_tenant_filters.py -q` |

| Chapters | Gates | New live-run dependency |
|---|---|---|
| 1–4 | 0–2 | Camera, microphone, and Gemini where stated |
| 5–8 | 3–6 | Gemini for new perception runs |
| 10–13 | 7–10 | FFmpeg and Gemini for new video runs |
| 14–17 | 11–14 | Chromium through Playwright |
| 18–22 | 15–20 | Tika, Qdrant, and Gemini embeddings where stated |
| 23–28 | 21–26 | Deterministic local fixtures |
| 29–33 | 27–31 | Docker for the production-shaped stack |
| 34–35 | 32–34 | Oracle Cloud and Auth0 for new live evidence |
| 36 | 35 | Deterministic local orchestration; remote A2A is optional |
| 37 | 37 | Local OpenSearch and Gemini embeddings for the capstone's hybrid index |
| 38 | 38 | Deployed Studio and `GEMINI_API_KEY` for the live agent-driven demo |

Run the full deterministic and browser regression suite with:

```bash
uv run pytest -q
cd frontend
npm run build
npm run test:e2e
```

`npm run test:e2e` starts the local application server itself and excludes
the manuscript-only review audit. In the author's combined book-and-code
workspace, render the book to HTML and run `npm run test:book` to check all 38
chapter figures at desktop and mobile sizes.

The checked-in `runs/gate-*` artifacts reproduce the reported observations
without the author's private credentials. A reader's live provider result is a
new experiment and should not overwrite the retained book artifact.
