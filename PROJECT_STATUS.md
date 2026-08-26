# Project Status

## Project
Privo — Privacy Intelligence Android Application (CEP Academic Project, Mumbai University BSc.IT Sem 5, NEP 2020)

## Current Goal
Bring the frontend in sync with Week 2 backend metadata work, then move into Week 3: Detection Engine planning and implementation.

## Completed
- **Week 1 (full stack):** Communication pipeline — React frontend uploads image → FastAPI receives it → Trigger Engine validates → Session Manager creates session with default settings → structured JSON response returns to React.
- **Week 2 (backend only):** Real privacy intelligence added.
  - `MetadataExtractor` — calls ExifTool via subprocess, writes temp files, parses JSON output into a typed `RawMetadata` model.
  - `MetadataVault` — classifies raw metadata into `MetadataFinding` objects across 5 exposure categories: Location, Identity, Activity, Contact, Travel.
  - Schemas + `/analyze` endpoint extended with `MetadataSummary` and `MetadataFindingSchema`.
- Backend folder restructured from flat `app/engine/` to staged `app/pipeline/` with subfolders per stage (`intake/`, `extraction/`, `detection/`, `classification/`, `analysis/`, `visualisation/`, `protection/`, `export/`, `memory/`); all imports updated to `app.pipeline.*`.

## Currently Working On
- **Decision point:** update `src/types/analysis.ts` to mirror the new backend metadata schemas *or* start Week 3 detection engine planning.
- Frontend does not yet display/consume Week 2 metadata data.

## Files Changed
**Backend:** `app/core/config.py`, `app/core/logging.py`, `app/pipeline/intake/trigger.py`, `app/pipeline/intake/session.py`, `app/pipeline/extraction/` (MetadataExtractor), `app/pipeline/classification/` (MetadataVault), `app/schemas/analysis.py`, `app/api/analyze.py`, `app/api/router.py`, `app/main.py`

**Frontend (Week 1 only, not yet updated for Week 2):** `src/types/analysis.ts`, `src/lib/api.ts`, `src/features/upload/useUpload.ts`, `src/features/upload/UploadZone.tsx`, `src/App.tsx`, `src/main.tsx`, `src/styles/index.css`

## Current Problems / Errors
- None outstanding — Week 2 backend is stable.
- Frontend `analysis.ts` types are structurally behind the backend schema (a gap to close, not a bug).

## Important Decisions
- **Stack:** React Native (Expo managed workflow) + FastAPI/Python backend. Native Android app is the primary frontend from Phase 1 — PWA approach was considered and abandoned per professor guidance.
- **Camera flow (frozen):** viewfinder → freeze frame → Detection Engine → risk/heatmap → apply protection → save. Once saved, original protections are irreversible; reopening only allows *additional* protections.
- **Data retention (frozen):** raw/unprotected frames exist only in-memory during the session; only the final protected image is ever written to disk/Memory Engine/Gallery.
- **Backend stays stateless** — all persistence (images + metadata) lives on-device via `expo-file-system` + `expo-sqlite`.
- **Indian document detection:** OCR + regex pattern matching, not specialized models (ethical/feasibility reasoning — no real ID training data available).
- **Development pace:** one file at a time, explicit approval before progressing, no premature abstraction, no empty placeholder folders.
- **ExifTool `-n` flag** returns numeric types (float/int), not strings — schemas must match exactly.
- **`extraction_success`** reflects whether ExifTool ran cleanly, not whether any fields were found — the four outcome cases (success w/ fields, success w/ zero fields, parse error, subprocess failure) must not be conflated.
- **Shared threshold is two** — a component/utility only moves to a shared folder once two or more features need it.

## Next Steps
1. Update `src/types/analysis.ts` to mirror the Week 2 backend metadata schemas.
2. Begin Week 3: Detection Engine planning (MVP priorities: Face Detection, OCR, QR Detection).
3. Continue staged pipeline build: detection → classification → signal correlation → exposure analysis → risk scoring → heatmap/protection UI.

## Notes for the Next Claude Chat
- Durvali is a solo third-year BSc.IT student, intermediate Python, learning FastAPI and React/TypeScript/React Native while building. **Explain everything** — every import, function, and inter-module dependency — before generating code.
- Work **one file at a time** with explicit approval before moving on. Never batch-generate files or pre-build future weeks' modules.
- The frozen architecture (Trigger Engine → Session Manager → ... → Session Termination, 22 official modules) should not be redesigned without a strong technical reason.
- Backend pipeline folder is `app/pipeline/<stage>/`, **not** `app/engine/` — renamed before Week 2 work began.
- Proactively catch and flag your own mistakes before presenting files; Durvali reviews code carefully and expects the "why" behind decisions, not just conclusions.
- Never leak internal errors via `detail=str(exc)` in API responses; always check silent-failure return values (e.g. `SessionManager.update_metadata_findings()`) and log warnings rather than discarding them.
- Privo is explicitly **not** an OCR tool, face-detection tool, metadata remover, cybercrime predictor, attacker simulator, OSINT tool, or social media monitor — it's an evidence-based Privacy Intelligence Assistant. Output language must stay evidence-based and explainable (e.g. "This image may expose your location," never "Someone may stalk you").