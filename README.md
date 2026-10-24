# Luminaria

![Luminaria — Intelligence, on your terms.](web/brand/social-cover.svg)

A Windows desktop interface for local AI, built with plain HTML/JavaScript, a Python backend, SQLite and llama.cpp/llama-swap.

**Development build — not a public stable release.** See [master specification](docs/specifications/MASTER-SPEC.md) for the intended product and [VERIFICATION.md](VERIFICATION.md) for current evidence. UI availability alone does not establish that a feature is verified.

## Run from source

Use Python 3.14 on Windows and install `requirements-build.txt` in a virtual environment. Run `python desktop.py`. Model weights and inference executables are not included. Configure a compatible local inference endpoint and register GGUF models in Settings.

The backend binds to loopback. Default file tools are confined to the app files folder. Shell, code execution and computer integrations are disabled by default; when enabled, they require approvals and run with your Windows account permissions. This is not an OS sandbox.

## Build

Run `build.ps1` from the configured Python environment. Required build inputs: `runtime/llama-swap.exe`, the model runtime at `runtime/local-ai/runtime-vulkan/` (run `scripts/fetch-model-runtime.ps1` to fetch the checksum-pinned archive), and Inno Setup compiler at `runtime/inno/ISCC.exe`. These binaries are intentionally excluded from Git.

The internal executable and installer AppId remain stable across the Luminaria rename to support upgrades. The installed app keeps its data in a `data/` folder inside its installation directory. On this PC the app, data and model library live in `Desktop/Luminaria/App`. See [FOLDER-GUIDE.md](FOLDER-GUIDE.md).

## Accounts and releases

Local profiles use separate data stores. Google OAuth, public update distribution and code signing are not configured yet. Google sign-in is unavailable until the publisher configuration and complete authentication flow are tested.

The repository excludes local histories, credentials, model weights, generated installers and machine configuration. Private development hosting does not automatically provide a public desktop update channel.
