# Build-Along and Video Series Guide

This book is designed as one continuous build, not 34 disconnected demos. The companion repository at <https://github.com/IAgentic-LLC/multimodal-agents> is the executable source of truth. Each chapter is also one recordable episode: begin from the preceding checkpoint, type the focused implementation, run it, inspect the evidence, break one assumption, run the verifier, and stop only at a reproducible checkpoint.

## Prepare once

From a clean checkout:

```powershell
git clone https://github.com/IAgentic-LLC/multimodal-agents
cd multimodal-agents
uv sync
uv run pytest -q
cd frontend
npm ci
npm run build
npx playwright test
cd ..
uv run python scripts/verify_course.py
```

The deterministic path uses fixtures and retained artifacts and must work without paid credentials. A live provider exercise is an additional experiment, never a substitute for the reproducible path. Keep keys in environment variables, never in code, screenshots, terminal history shown on camera, or committed artifacts.

## Use the same episode shape every time

1. **Orient:** state the failure or capability this episode addresses and show the previous checkpoint.
2. **Inspect:** open only the files named in the chapter's Follow along section.
3. **Type:** enter the focused listing in small compilable steps; explain the invariant each step creates.
4. **Run:** execute the smallest demonstrator before adding UI polish or provider calls.
5. **Observe:** inspect the actual JSON, trace, image region, interval, metric, database row, or browser state.
6. **Break:** change one input or inject one failure so the safety boundary is visible.
7. **Verify:** run `uv run python scripts/verify_chapter.py N` and explain what it checks.
8. **Checkpoint:** show the retained artifact and preview what the next episode consumes.

Never hide a setup step behind “and now it works.” If a service needs Docker, start it on screen and verify health. If a live call needs Gemini, Auth0, Qdrant, PostgreSQL, or Oracle Cloud, first complete the deterministic path, then label the live run and its cost/privacy implications.

## The 34-episode path

### Episode 01: The Frame Behind This

**Build:** Capture synchronized camera, microphone, and monotonic timing evidence.

**Type and explain:** `frontend/src/App.tsx`, `frontend/src/capture.ts`, `src/multimodal_agents/capture.py`, `src/multimodal_agents/server.py`.

**Run:**

```powershell
uv run multimodal-capture
```

**Verify:**

```powershell
uv run python scripts/verify_chapter.py 1
```

**On-screen proof:** Point at an object, speak, and inspect the paired frame, audio interval, and JSONL event.

**Retain:** `runs/gate-1`. **Environment:** Local browser; camera and microphone permission.

### Episode 02: An Evidence Event

**Build:** Define and validate the evidence-event contract.

**Type and explain:** `src/multimodal_agents/evidence.py`, `src/multimodal_agents/capture.py`.

**Run:**

```powershell
uv run pytest -q tests/test_vertical_slice.py
```

**Verify:**

```powershell
uv run python scripts/verify_chapter.py 2
```

**On-screen proof:** Reject malformed regions and time ranges before they enter world state.

**Retain:** `runs/gate-0 and runs/gate-1`. **Environment:** Deterministic local replay.

### Episode 03: Keep Each Modality Honest

**Build:** Separate provider output from normalized observations.

**Type and explain:** `src/multimodal_agents/gemini.py`, `src/multimodal_agents/run_grounding.py`.

**Run:**

```powershell
uv run python -m multimodal_agents.run_grounding
```

**Verify:**

```powershell
uv run python scripts/verify_chapter.py 3
```

**On-screen proof:** Compare raw provider evidence with the normalized event.

**Retain:** `runs/gate-2`. **Environment:** Live Gemini run requires GOOGLE_API_KEY; retained replay does not.

### Episode 04: Build the First World State

**Build:** Reduce immutable evidence events into queryable world state.

**Type and explain:** `src/multimodal_agents/memory.py`, `src/multimodal_agents/world_state.py`.

**Run:**

```powershell
uv run pytest -q tests/test_vertical_slice.py
```

**Verify:**

```powershell
uv run python scripts/verify_chapter.py 4
```

**On-screen proof:** Ask for the latest supported object location without mutating source evidence.

**Retain:** `runs/gate-0`. **Environment:** Deterministic local replay.

### Episode 05: Pixels Are Not Objects

**Build:** Convert safely among pixel, normalized, and display coordinates.

**Type and explain:** `src/multimodal_agents/geometry.py`, `src/multimodal_agents/run_geometry.py`, `frontend/src/geometry.ts`.

**Run:**

```powershell
uv run python -m multimodal_agents.run_geometry
```

**Verify:**

```powershell
uv run python scripts/verify_chapter.py 5
```

**On-screen proof:** Map a model region onto a resized UI without shifting the overlay.

**Retain:** `runs/gate-3/coordinate-results.json`. **Environment:** Deterministic local run.

### Episode 06: Ground the Claim

**Build:** Require claims to carry regions and source evidence.

**Type and explain:** `src/multimodal_agents/image_grounding.py`, `src/multimodal_agents/run_image_grounding.py`.

**Run:**

```powershell
uv run python -m multimodal_agents.run_image_grounding
```

**Verify:**

```powershell
uv run python scripts/verify_chapter.py 6
```

**On-screen proof:** Draw the cited region and distinguish observation from inference.

**Retain:** `runs/gate-4`. **Environment:** Live Gemini run requires GOOGLE_API_KEY; retained replay does not.

### Episode 07: Read the Scene

**Build:** Extract a structured scene graph from visual evidence.

**Type and explain:** `src/multimodal_agents/scene_reading.py`, `src/multimodal_agents/run_scene_reading.py`, `frontend/src/OpeningEvidenceLabs.tsx`.

**Run:**

```powershell
uv run python -m multimodal_agents.run_scene_reading
```

**Verify:**

```powershell
uv run python scripts/verify_chapter.py 7
```

**On-screen proof:** Inspect objects, relations, confidence, and provenance together.

**Retain:** `runs/gate-5`. **Environment:** Live Gemini run requires GOOGLE_API_KEY; retained replay does not.

### Episode 08: Test What the Agent Sees

**Build:** Evaluate vision under blur, darkness, compression, and low resolution.

**Type and explain:** `src/multimodal_agents/visual_robustness.py`, `src/multimodal_agents/run_visual_robustness.py`.

**Run:**

```powershell
uv run python -m multimodal_agents.run_visual_robustness
```

**Verify:**

```powershell
uv run python scripts/verify_chapter.py 8
```

**On-screen proof:** Compare the robustness matrix rather than trusting one clean image.

**Retain:** `runs/gate-6`. **Environment:** Live Gemini run optional; fixtures and tests are deterministic.

### Episode 09: An Image Has No Before

**Build:** Represent ordered observations and change events.

**Type and explain:** `src/multimodal_agents/temporal.py`, `src/multimodal_agents/run_temporal.py`.

**Run:**

```powershell
uv run python -m multimodal_agents.run_temporal
```

**Verify:**

```powershell
uv run python scripts/verify_chapter.py 9
```

**On-screen proof:** Show what changed between two frames and preserve event time.

**Retain:** `runs/gate-7`. **Environment:** Deterministic fixtures.

### Episode 10: Sample What Matters

**Build:** Compare uniform and change-aware video sampling.

**Type and explain:** `src/multimodal_agents/sampling.py`, `src/multimodal_agents/run_video_sampling.py`.

**Run:**

```powershell
uv run python -m multimodal_agents.run_video_sampling
```

**Verify:**

```powershell
uv run python scripts/verify_chapter.py 10
```

**On-screen proof:** Recover a short event that uniform sampling misses.

**Retain:** `runs/gate-8`. **Environment:** Local FFmpeg plus optional Gemini.

### Episode 11: Find the Moment

**Build:** Retrieve evidence intervals instead of isolated frames.

**Type and explain:** `src/multimodal_agents/temporal_retrieval.py`, `src/multimodal_agents/evaluate_video_intervals.py`.

**Run:**

```powershell
uv run pytest -q tests/test_temporal_retrieval.py
```

**Verify:**

```powershell
uv run python scripts/verify_chapter.py 11
```

**On-screen proof:** Return start/end timestamps and score temporal overlap.

**Retain:** `runs/gate-9`. **Environment:** Deterministic local replay.

### Episode 12: Resolve This While the World Moves

**Build:** Join speech references to the correct live visual context.

**Type and explain:** `frontend/src/LiveSessionLab.tsx`, `frontend/src/liveSession.ts`, `src/multimodal_agents/temporal.py`.

**Run:**

```powershell
cd frontend; npx playwright test --grep "live session"
```

**Verify:**

```powershell
uv run python scripts/verify_chapter.py 12
```

**On-screen proof:** Resolve â€˜thisâ€™ against event time rather than the newest frame.

**Retain:** `runs/gate-10`. **Environment:** Browser simulation; camera optional.

### Episode 13: See the Screen, Read the Interface

**Build:** Capture screen state as visual and structured evidence.

**Type and explain:** `frontend/src/ScreenStateLab.tsx`, `src/multimodal_agents/screen_fusion.py`.

**Run:**

```powershell
cd frontend; npx playwright test --grep "screen state"
```

**Verify:**

```powershell
uv run python scripts/verify_chapter.py 13
```

**On-screen proof:** Inspect the screenshot and accessibility-derived state side by side.

**Retain:** `runs/gate-11`. **Environment:** Deterministic browser fixture.

### Episode 14: Prefer Structure When It Exists

**Build:** Fuse pixels with DOM or accessibility evidence and preserve disagreements.

**Type and explain:** `frontend/src/FusionLab.tsx`, `src/multimodal_agents/screen_fusion.py`.

**Run:**

```powershell
cd frontend; npx playwright test --grep "fusion"
```

**Verify:**

```powershell
uv run python scripts/verify_chapter.py 14
```

**On-screen proof:** Prefer a stable structured selector while retaining visual confirmation.

**Retain:** `runs/gate-12`. **Environment:** Deterministic browser fixture.

### Episode 15: Turn Observations into Actions

**Build:** Create typed proposals, risk checks, and confirmation boundaries.

**Type and explain:** `src/multimodal_agents/safe_actions.py`, `frontend/src/SafeActionLab.tsx`.

**Run:**

```powershell
uv run pytest -q tests/test_safe_actions.py
```

**Verify:**

```powershell
uv run python scripts/verify_chapter.py 15
```

**On-screen proof:** Allow a read action and block a high-impact action without confirmation.

**Retain:** `runs/gate-13`. **Environment:** Deterministic simulation; no external mutation.

### Episode 16: Build a Safe Screen Agent

**Build:** Join perception, planning, policy, action, and postcondition checks.

**Type and explain:** `src/multimodal_agents/screen_agent.py`, `frontend/src/ScreenAgentLab.tsx`.

**Run:**

```powershell
uv run pytest -q tests/test_screen_agent.py
```

**Verify:**

```powershell
uv run python scripts/verify_chapter.py 16
```

**On-screen proof:** Execute a reversible action and prove its postcondition.

**Retain:** `runs/gate-14`. **Environment:** Deterministic sandbox.

### Episode 17: A Page Is More Than Its Text

**Build:** Extract text, tables, figures, captions, and layout relations.

**Type and explain:** `src/multimodal_agents/run_document_layout.py`, `frontend/src/DocumentLayoutLab.tsx`.

**Run:**

```powershell
uv run python -m multimodal_agents.run_document_layout
```

**Verify:**

```powershell
uv run python scripts/verify_chapter.py 17
```

**On-screen proof:** Retrieve a figure with its caption and supporting paragraph.

**Retain:** `runs/gate-15`. **Environment:** Deterministic generated document.

### Episode 18: Search Beyond Text

**Build:** Index multimodal records locally and in Qdrant.

**Type and explain:** `src/multimodal_agents/run_multimodal_embeddings.py`, `src/multimodal_agents/run_qdrant_search.py`, `frontend/src/SearchIndexLab.tsx`, `deploy/qdrant/docker-compose.yml`.

**Run:**

```powershell
docker compose -f deploy/qdrant/docker-compose.yml up -d; uv sync --extra gemini; uv run python -m multimodal_agents.run_qdrant_search runs/local/qdrant-search.json
```

**Verify:**

```powershell
uv run python scripts/verify_chapter.py 18
```

**On-screen proof:** Search the same records through the reference index and Qdrant.

**Retain:** `runs/gate-16 and runs/gate-17`. **Environment:** Docker and local Qdrant; live embedding requires GEMINI_API_KEY.

### Episode 19: Cross-Modal Search

**Build:** Use text to retrieve images and images to retrieve related evidence.

**Type and explain:** `src/multimodal_agents/run_cross_modal_search.py`, `frontend/src/CrossModalSearchLab.tsx`.

**Run:**

```powershell
uv run python -m multimodal_agents.run_cross_modal_search
```

**Verify:**

```powershell
uv run python scripts/verify_chapter.py 19
```

**On-screen proof:** Issue a text query and inspect the ranked visual evidence.

**Retain:** `runs/gate-18`. **Environment:** Live Gemini run requires GOOGLE_API_KEY; retained replay does not.

### Episode 20: Hybrid Retrieval and Reranking

**Build:** Fuse lexical, vector, and metadata signals with explainable scores.

**Type and explain:** `src/multimodal_agents/hybrid_search.py`, `src/multimodal_agents/run_hybrid_search.py`, `frontend/src/HybridRetrievalLab.tsx`.

**Run:**

```powershell
uv run python -m multimodal_agents.run_hybrid_search
```

**Verify:**

```powershell
uv run python scripts/verify_chapter.py 20
```

**On-screen proof:** Explain why the reranker promoted one evidence item.

**Retain:** `runs/gate-19`. **Environment:** Deterministic local run.

### Episode 21: Multimodal RAG with Citations

**Build:** Assemble bounded evidence packages and modality-specific citations.

**Type and explain:** `src/multimodal_agents/evidence_package.py`, `src/multimodal_agents/run_multimodal_rag.py`, `frontend/src/EvidencePackageLab.tsx`.

**Run:**

```powershell
uv run python -m multimodal_agents.run_multimodal_rag
```

**Verify:**

```powershell
uv run python scripts/verify_chapter.py 21
```

**On-screen proof:** Trace every answer claim to a page, region, or time interval.

**Retain:** `runs/gate-20`. **Environment:** Deterministic evidence assembly; provider generation optional.

### Episode 22: Memory Is an Event Store

**Build:** Persist append-only multimodal events and materialize state.

**Type and explain:** `src/multimodal_agents/event_store.py`, `src/multimodal_agents/run_event_store.py`, `frontend/src/EventMemoryLab.tsx`.

**Run:**

```powershell
uv run python -m multimodal_agents.run_event_store
```

**Verify:**

```powershell
uv run python scripts/verify_chapter.py 22
```

**On-screen proof:** Rebuild current state from immutable events.

**Retain:** `runs/gate-21`. **Environment:** Deterministic local store.

### Episode 23: Ask the Past

**Build:** Query memory by entity, time, modality, and evidence relation.

**Type and explain:** `src/multimodal_agents/memory_queries.py`, `src/multimodal_agents/run_memory_queries.py`, `frontend/src/MemoryQueryLab.tsx`.

**Run:**

```powershell
uv run python -m multimodal_agents.run_memory_queries
```

**Verify:**

```powershell
uv run python scripts/verify_chapter.py 23
```

**On-screen proof:** Find what was on screen when a deployment failed.

**Retain:** `runs/gate-22`. **Environment:** Deterministic local replay.

### Episode 24: Audio Beyond Speech

**Build:** Detect and localize non-speech acoustic events.

**Type and explain:** `src/multimodal_agents/acoustic_events.py`, `src/multimodal_agents/run_acoustic_events.py`, `frontend/src/AcousticEventLab.tsx`.

**Run:**

```powershell
uv run python -m multimodal_agents.run_acoustic_events
```

**Verify:**

```powershell
uv run python scripts/verify_chapter.py 24
```

**On-screen proof:** Localize an alarm interval without transcribing it as speech.

**Retain:** `runs/gate-23`. **Environment:** Deterministic synthesized audio.

### Episode 25: Sensors and World State

**Build:** Normalize timestamped sensor readings into shared world state.

**Type and explain:** `src/multimodal_agents/sensor_world.py`, `src/multimodal_agents/run_sensor_world.py`, `frontend/src/SensorWorldLab.tsx`.

**Run:**

```powershell
uv run python -m multimodal_agents.run_sensor_world
```

**Verify:**

```powershell
uv run python scripts/verify_chapter.py 25
```

**On-screen proof:** Correlate a temperature rise with camera and audio evidence.

**Retain:** `runs/gate-24`. **Environment:** Deterministic sensor simulation.

### Episode 26: When Modalities Disagree

**Build:** Represent contradictions without silently overwriting evidence.

**Type and explain:** `src/multimodal_agents/contradictions.py`, `src/multimodal_agents/run_contradictions.py`, `frontend/src/ContradictionLab.tsx`.

**Run:**

```powershell
uv run python -m multimodal_agents.run_contradictions
```

**Verify:**

```powershell
uv run python scripts/verify_chapter.py 26
```

**On-screen proof:** Escalate when camera and sensor disagree about the door.

**Retain:** `runs/gate-25`. **Environment:** Deterministic scenarios.

### Episode 27: Evidence Before Action

**Build:** Gate actions on provenance, freshness, corroboration, and risk.

**Type and explain:** `src/multimodal_agents/policy_gate.py`, `src/multimodal_agents/run_policy_gate.py`, `frontend/src/PolicyGateLab.tsx`.

**Run:**

```powershell
uv run python -m multimodal_agents.run_policy_gate
```

**Verify:**

```powershell
uv run python scripts/verify_chapter.py 27
```

**On-screen proof:** Show the exact missing evidence that blocks an action.

**Retain:** `runs/gate-26`. **Environment:** Deterministic policy simulation.

### Episode 28: Build the Multimodal Sandbox

**Build:** Replay time-aligned world scenarios with known ground truth.

**Type and explain:** `src/multimodal_agents/sandbox.py`, `src/multimodal_agents/run_sandbox.py`, `frontend/src/SandboxLab.tsx`.

**Run:**

```powershell
uv run python -m multimodal_agents.run_sandbox
```

**Verify:**

```powershell
uv run python scripts/verify_chapter.py 28
```

**On-screen proof:** Replay the same scenario and obtain the same evidence timeline.

**Retain:** `runs/gate-27`. **Environment:** Deterministic simulator.

### Episode 29: Evaluate Every Boundary

**Build:** Score perception, retrieval, grounding, policy, and outcomes separately.

**Type and explain:** `src/multimodal_agents/evaluation.py`, `src/multimodal_agents/run_evaluation.py`, `frontend/src/EvaluationLab.tsx`.

**Run:**

```powershell
uv run python -m multimodal_agents.run_evaluation
```

**Verify:**

```powershell
uv run python scripts/verify_chapter.py 29
```

**On-screen proof:** Locate the failing boundary instead of hiding it in one aggregate score.

**Retain:** `runs/gate-28`. **Environment:** Deterministic benchmark.

### Episode 30: Break It Deliberately

**Build:** Inject stale, missing, delayed, corrupted, and contradictory evidence.

**Type and explain:** `src/multimodal_agents/failure_injection.py`, `src/multimodal_agents/run_failure_injection.py`, `frontend/src/FailureLab.tsx`.

**Run:**

```powershell
uv run python -m multimodal_agents.run_failure_injection
```

**Verify:**

```powershell
uv run python scripts/verify_chapter.py 30
```

**On-screen proof:** Prove the runtime degrades safely under each injected failure.

**Retain:** `runs/gate-29`. **Environment:** Deterministic fault injection.

### Episode 31: Design the Runtime

**Build:** Add bounded queues, tracing, metrics, and backpressure.

**Type and explain:** `src/multimodal_agents/runtime_observability.py`, `src/multimodal_agents/run_runtime_observability.py`, `frontend/src/RuntimeLab.tsx`.

**Run:**

```powershell
uv run python -m multimodal_agents.run_runtime_observability
```

**Verify:**

```powershell
uv run python scripts/verify_chapter.py 31
```

**On-screen proof:** Observe queue depth, dropped work, latency, and trace linkage.

**Retain:** `runs/gate-30`. **Environment:** Deterministic load simulation.

### Episode 32: Build IAgentic Multimodal Studio

**Build:** Assemble the React and TypeScript operator experience.

**Type and explain:** `frontend/src/MultimodalStudio.tsx`, `frontend/src/styles.css`, `frontend/src/types.ts`.

**Run:**

```powershell
cd frontend; npm run build; npx playwright test --grep "studio coordinates"; cd ..
```

**Verify:**

```powershell
uv run python scripts/verify_chapter.py 32
```

**On-screen proof:** Follow evidence from timeline to source, decision, and action.

**Retain:** `runs/gate-31/studio-ui-result.json`. **Environment:** Local browser.

### Episode 33: Deploy Without Losing the Evidence

**Build:** Run production-shaped services with health, security, and persistence controls.

**Type and explain:** `src/multimodal_agents/production_controls.py`, `src/multimodal_agents/run_production_controls.py`, `deploy/oci/docker-compose.yml`, `deploy/api/Dockerfile`.

**Run:**

```powershell
docker compose -f deploy/oci/docker-compose.yml up -d
```

**Verify:**

```powershell
uv run python scripts/verify_chapter.py 33
```

**On-screen proof:** Restart services and show that evidence persists and health checks recover.

**Retain:** `runs/gate-32 and runs/gate-33`. **Environment:** Docker locally; Oracle Cloud deployment optional.

### Episode 34: Release with Tenant Boundaries

**Build:** Enforce Auth0 organization identity and PostgreSQL row-level isolation.

**Type and explain:** `src/multimodal_agents/identity.py`, `src/multimodal_agents/studio_api.py`, `scripts/run_release_gate.py`, `deploy/postgres/init.sh`.

**Run:**

```powershell
uv run python scripts/run_release_gate.py
```

**Verify:**

```powershell
uv run python scripts/verify_chapter.py 34
```

**On-screen proof:** Prove two tenants can read their own evidence and cannot read each otherâ€™s rows.

**Retain:** `runs/gate-34`. **Environment:** Offline release replay by default; --live requires two Auth0 organization tokens and PostgreSQL.

## Recording and editing checklist

- Start each terminal session from the repository root and show `git status --short`.
- Increase editor and terminal font size; keep secrets and personal paths off screen.
- Prefer one concept per commit-sized segment, although publishing commits remains a separate decision.
- Show failed tests when they teach the boundary, then show the exact change that makes them pass.
- Put commands and file paths in the video description directly from `course_manifest.json`.
- Link the episode to its book chapter, source files, retained gate, and next episode.
- End with the verifier output and the artifact viewers should have locally.
- Re-run `uv run python scripts/verify_course.py` before recording or releasing a playlist.

## Definition of done

An episode is complete only when a viewer can start from the previous checkpoint, type the demonstrated code, run the same command, observe the stated result, pass the chapter verifier, and locate the retained evidence. A polished explanation without that chain is not a completed build-along lesson.
