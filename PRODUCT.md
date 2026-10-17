# Luminaria

## Platform
web, packaged for Windows desktop

## Stack
User-selected plain HTML/JavaScript with local Markdown assets; Python API and LangGraph execution, SQLite history. Windows desktop host and installer. No frontend build toolchain.

## Users and purpose
Aaron's local coding, reasoning, research, document creation, vision and computer-use workspace. Other users can install the packaged app and configure their own model and tools.

## Constraints
Use the existing local Qwen model, llama.cpp, llama-swap and installed browser/Windows tools. Start with one model. Full history persists; compaction is a lossy working-context summary, never deletion. Auto reads/search/screenshots; approval for writes, commands, network and GUI actions; always ask for deletes/sends/installs. Credentials are not supplied. Automatic task routing waits until multiple models are justified.

## Brand commitments
Luminaria is the selected product name. The task sidebar, central conversation and workspace inspector support a local Windows workflow. Appearance offers Light, Dark and Follow system: black on white or white on black by default. A persistent shared accent can apply across both modes, with optional per-mode accents and separate per-mode customization of surfaces, text, states and spatial colors. The UI and 3D renderer consume the same semantic appearance tokens.

Appearance saves through the profile preferences API. A browser-local cache applies before first paint; that cache belongs to this PC/browser origin, not to an individual profile. Custom colors can produce low contrast; settings display contrast warnings rather than guaranteeing accessible combinations.

The persistent spatial workspace represents recorded execution events and explicitly labeled model-provided steps. Its reactive entity and regional lattice remain separate visual layers. Activity outline, evidence details and keyboard controls provide a usable alternative to spatial selection. Preview fixtures demonstrate presentation only; native WebView2, model execution and installation require their own acceptance evidence.

## Packaging
Windows installer/uninstaller and opt-in GitHub Release update checks. Signing certificate and public release repository are not yet configured. Do not claim signed or publicly published builds.

## Release commitment
Publish source to the user's GitHub after naming and UI review. Maintain versioned releases, release notes, installer plus SHA256SUMS.txt, and configure the desktop updater to the selected repository. Exclude credentials, personal history, local machine configuration, model weights and personal test artifacts. Public publishing is pending, not completed.
