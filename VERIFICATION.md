# Verification ledger

## Current revision
Implementation in progress. Do not treat planned scope as completed functionality.

Implemented, awaiting this revision's integration checks: categorized settings, persistent themes, profile separation, benchmark endpoint, skills library, chat fork/archive/trash, composer Add menu, dictation, selectable voices, audio-reactive background.

External prerequisites: publisher Google OAuth configuration; code-signing certificate; public update release channel.

Desktop installer rebuild and real-model acceptance results will be recorded after execution.


## October 16, 2026 — consolidated desktop build
- Windows installer 0.2.0 compiled successfully and installed under Desktop/Luminaria/App.
- App bootstrap/settings report version 0.2.0 and data path App/data.
- All eight registered models and their projectors exist under App/models (12 files, 106.41 GiB total); inventory count and byte total preserved during same-volume move.
- Real installed Qwen chat returned exactly "Luminaria is ready."; authenticated chat completion returned HTTP 200 after fixing the client key refresh.
- Graphite & Ivory defaults and the granular palette editor were inspected in the installed UI. API palette persistence and invalid-color rejection passed.
- Model-management controls and Add GGUF form render in the installed app. Updated JavaScript passed syntax checks.
- Full access startup latch, tool exposure and prompt descriptions passed isolated-process checks; current user's mode remains Review actions.
- Historical chat databases were copied with matching SHA-256 hashes. Older histories and run exports remain recoverable.
- Superseded generated files were archived, not deleted: automatic approval review blocked recursive cleanup without a more specific reason.
- Not a completion claim for the master specification: OAuth/provider sign-in, final 3D/voice refinement, SQLite benchmark migration and broader end-to-end verification remain outstanding.
