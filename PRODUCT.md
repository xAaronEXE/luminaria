# Local AI Studio

## Platform
web, packaged for Windows desktop

## Stack
User-selected plain HTML/JavaScript with local Markdown assets; Python API and LangGraph execution, SQLite history. Windows desktop host and installer. No frontend build toolchain.

## Users and purpose
Aaron's local coding, reasoning, research, document creation, vision and computer-use workspace. Other users can install the packaged app and configure their own model and tools.

## Constraints
Use the existing local Qwen model, llama.cpp, llama-swap and installed browser/Windows tools. Start with one model. Full history persists; compaction is a lossy working-context summary, never deletion. Auto reads/search/screenshots; approval for writes, commands, network and GUI actions; always ask for deletes/sends/installs. Credentials are not supplied. Automatic task routing waits until multiple models are justified.

## Brand commitments
Codex-inspired task sidebar, central conversation and workspace inspector. Acid mint #B7FF2E and forestry graphite #141A17.

## Packaging
Windows installer/uninstaller and opt-in GitHub Release update checks. Signing certificate and public release repository are not yet configured. Do not claim signed or publicly published builds.

## Release commitment
Publish source to the user's GitHub after naming and UI review. Maintain versioned releases, release notes, installer plus SHA256SUMS.txt, and configure the desktop updater to the selected repository. Exclude credentials, personal history, local machine configuration, model weights and personal test artifacts. Public publishing is pending, not completed.
