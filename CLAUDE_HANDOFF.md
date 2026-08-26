# Privo - Automatic Claude Handoff

Generated: 2026-08-26 15:54:21

---

## Current Git State

Branch:
main

Current Commit:
f8f3e4c

## Recent Commits

f8f3e4c claude integrations... dfc5cdc Update project handoff status cb282a7 week 1 is completed f21a7ea Merge branch 'main' of https://github.com/Durvali0907/Privo a0256e8 directory structure

## Uncommitted Changes

 M CLAUDE_HANDOFF.md  M handoff.ps1

---

## Project Context

The following is the current project documentation:

# Project Status

## Project
Privo â€” Privacy Intelligence Android Application (CEP Academic Project, Mumbai University BSc.IT Sem 5, NEP 2020)

## Current Goal
Bring the frontend in sync with Week 2 backend metadata work, then move into Week 3: Detection Engine planning and implementation.

## Completed
- **Week 1 (full stack):** Communication pipeline â€” React frontend uploads image â†’ FastAPI receives it â†’ Trigger Engine validates â†’ Session Manager creates session with default settings â†’ structured JSON response returns to React.
- **Week 2 (backend only):** Real privacy intelligence added.
  - `MetadataExtractor` â€” calls ExifTool via subprocess, writes temp files, parses JSON output into a typed `RawMetadata` model.
  - `MetadataVault` â€” classifies raw metadata into `MetadataFinding` objects across 5 exposure categories: Location, Identity, Activity, Contact, Travel.
  - Schemas + `/analyze` endpoint extended with `MetadataSummary` and `MetadataFindingSchema`.
- Backend folder restructured from flat `app/engine/` to staged `app/pipeline/` with subfolders per stage (`intake/`, `extraction/`, `detection/`, `classification/`, `analysis/`, `visualisation/`, `protection/`, `export/`, `memory/`); all imports updated to `app.pipeline.*`.

## Currently Working On
- **Decision point:** update `src/types/analysis.ts` to mirror the new backend metadata schemas *or* start Week 3 detection engine planning.
- Frontend does not yet display/consume Week 2 metadata data.

## Files Changed
**Backend:** `app/core/config.py`, `app/core/logging.py`, `app/pipeline/intake/trigger.py`, `app/pipeline/intake/session.py`, `app/pipeline/extraction/` (MetadataExtractor), `app/pipeline/classification/` (MetadataVault), `app/schemas/analysis.py`, `app/api/analyze.py`, `app/api/router.py`, `app/main.py`

**Frontend (Week 1 only, not yet updated for Week 2):** `src/types/analysis.ts`, `src/lib/api.ts`, `src/features/upload/useUpload.ts`, `src/features/upload/UploadZone.tsx`, `src/App.tsx`, `src/main.tsx`, `src/styles/index.css`

## Current Problems / Errors
- None outstanding â€” Week 2 backend is stable.
- Frontend `analysis.ts` types are structurally behind the backend schema (a gap to close, not a bug).

## Important Decisions
- **Stack:** React Native (Expo managed workflow) + FastAPI/Python backend. Native Android app is the primary frontend from Phase 1 â€” PWA approach was considered and abandoned per professor guidance.
- **Camera flow (frozen):** viewfinder â†’ freeze frame â†’ Detection Engine â†’ risk/heatmap â†’ apply protection â†’ save. Once saved, original protections are irreversible; reopening only allows *additional* protections.
- **Data retention (frozen):** raw/unprotected frames exist only in-memory during the session; only the final protected image is ever written to disk/Memory Engine/Gallery.
- **Backend stays stateless** â€” all persistence (images + metadata) lives on-device via `expo-file-system` + `expo-sqlite`.
- **Indian document detection:** OCR + regex pattern matching, not specialized models (ethical/feasibility reasoning â€” no real ID training data available).
- **Development pace:** one file at a time, explicit approval before progressing, no premature abstraction, no empty placeholder folders.
- **ExifTool `-n` flag** returns numeric types (float/int), not strings â€” schemas must match exactly.
- **`extraction_success`** reflects whether ExifTool ran cleanly, not whether any fields were found â€” the four outcome cases (success w/ fields, success w/ zero fields, parse error, subprocess failure) must not be conflated.
- **Shared threshold is two** â€” a component/utility only moves to a shared folder once two or more features need it.

## Next Steps
1. Update `src/types/analysis.ts` to mirror the Week 2 backend metadata schemas.
2. Begin Week 3: Detection Engine planning (MVP priorities: Face Detection, OCR, QR Detection).
3. Continue staged pipeline build: detection â†’ classification â†’ signal correlation â†’ exposure analysis â†’ risk scoring â†’ heatmap/protection UI.

## Notes for the Next Claude Chat
- Durvali is a solo third-year BSc.IT student, intermediate Python, learning FastAPI and React/TypeScript/React Native while building. **Explain everything** â€” every import, function, and inter-module dependency â€” before generating code.
- Work **one file at a time** with explicit approval before moving on. Never batch-generate files or pre-build future weeks' modules.
- The frozen architecture (Trigger Engine â†’ Session Manager â†’ ... â†’ Session Termination, 22 official modules) should not be redesigned without a strong technical reason.
- Backend pipeline folder is `app/pipeline/<stage>/`, **not** `app/engine/` â€” renamed before Week 2 work began.
- Proactively catch and flag your own mistakes before presenting files; Durvali reviews code carefully and expects the "why" behind decisions, not just conclusions.
- Never leak internal errors via `detail=str(exc)` in API responses; always check silent-failure return values (e.g. `SessionManager.update_metadata_findings()`) and log warnings rather than discarding them.
- Privo is explicitly **not** an OCR tool, face-detection tool, metadata remover, cybercrime predictor, attacker simulator, OSINT tool, or social media monitor â€” it's an evidence-based Privacy Intelligence Assistant. Output language must stay evidence-based and explainable (e.g. "This image may expose your location," never "Someone may stalk you").

---

## Instructions for the Next Claude Session

This project is being continued from another Claude session/account.

Before making changes:

1. Read this entire handoff file.
2. Inspect the current project files.
3. Check the recent Git commits.
4. Understand what has already been implemented.
5. Do not undo existing work.
6. Continue from the current project state.
7. Follow the project's existing architecture and coding rules.
8. Work one file at a time.
9. Explain the reasoning before generating code.
10. Wait for explicit approval before moving to another file.

IMPORTANT:

The Git repository is the source of truth for the actual code.

PROJECT_STATUS.md contains the stable project context.

This handoff file combines the Git state and project context
so another Claude account can understand the project quickly.

