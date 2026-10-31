# Luminaria

![Luminaria — Intelligence, on your terms.](web/brand/social-cover.svg)

**Luminaria is a private AI workspace for Windows that runs on your own PC.** Chat with local language models, let an assistant read and write files, run code, research the web and use your other apps, and keep your history, memory and files on your own machine. No subscription, no cloud model required.

> **Development build, not a public stable release.** Installers are not code-signed yet, so Windows SmartScreen may warn on first run. See [VERIFICATION.md](VERIFICATION.md) for what has been checked, and the [master specification](docs/specifications/MASTER-SPEC.md) for the intended product. A feature being visible in the interface does not mean it has been verified.

## Who it is for

- People who want a capable AI assistant without sending their files and conversations to someone else's servers.
- Builders and tinkerers who run models locally and want a proper desktop app around them instead of a terminal.
- Anyone who wants an assistant that can actually do work (edit files, run commands, research, draft documents) under controls they set.

You need a Windows PC. A graphics card with 8 GB or more of memory makes local models far more pleasant, but Luminaria rates every model against your own hardware so you can see what will and will not run well before you download it.

## What it does

### Chat and get work done
- **A real assistant, not just a chat box.** It can read, search, create and edit files in your working folder, run PowerShell and Python or JavaScript code, fetch and read web pages and PDFs, and search the web.
- **Plans and progress.** For multi-step jobs the assistant shows its plan, keeps it current as it works, and records every action it takes so you can see exactly what happened.
- **Pinned working brief.** Goals, constraints and decisions for each task stay in view and survive long conversations.
- **Long conversations that stay usable.** When a chat grows, older turns are summarised for the model while the full original history stays on disk and can be searched and recalled.
- **Attach what you are working on.** Images, PDFs, Word documents, text and code, or a whole folder.
- **Scheduled prompts** that run on a timer while Luminaria is open.

### You choose how much it may do
- **Ask me first** (default): reads and searches run on their own, while changes, commands and network use wait for your approval.
- **Hands-free**: everything runs without asking, using your Windows permissions.
- **Whole PC**: lets the assistant's file tools reach any drive, not just the working folder. One button, **Grant full access**, turns on all of it.
- Even in the widest mode, Luminaria's own settings and credentials, program files, Windows and credential folders (such as `.ssh`) stay off limits to the assistant, and web fetch never opens private or local network addresses.
- This is **not an operating-system sandbox**. Anything it is allowed to do runs with your Windows account permissions.

### Local models, matched to your PC
- **Model library** with a curated catalogue plus any GGUF model you add yourself, in multiple quantizations.
- **Per-PC fit ratings**, from green (runs well) through yellow and orange to red (too large), based on your graphics memory and system memory, with a recommended context size and load settings.
- **Benchmark each quantization** on your own machine. Speed, first-token time and a quality check are saved and shown next to every quantization.
- **Auto mode** can route each request to the most suitable installed model, and you can restrict which models it may choose from.
- **Hardware and tuning** controls for expert users, with automatic detection by default.
- Vision models, an abliterated ("unbound") model section clearly labelled, and disk-space checks before large downloads.

### Memory, skills and connectors
- **Persistent memory** you control: facts and preferences the assistant may carry between tasks, each with its source.
- **Skills**: reusable workflows (documents, research, code review, planning and more) that the assistant loads when a task calls for them.
- **Marketplace** (Settings › Marketplace): browse and install free skills from public GitHub repositories and connectors from the official MCP Registry. Connectors run third-party code on your PC, so each install asks for confirmation first.
- **Integrations** for services such as GitHub, Gmail, Google Drive and Calendar and Slack, each added with its own sign-in. Their tools follow your permission settings.
- **Browser and Windows desktop tools** the assistant can discover and use when you allow them.

### Voice and look
- Voice input and spoken replies, with a safe-graphics mode for older machines.
- A glass interface with a living orb, light and dark themes, colour palettes and adjustable motion.

### Accounts, profiles and sync
- **Local profiles** keep separate chats, memory, settings and files for each person using the PC.
- Optional **sign-in** (Google, GitHub, Discord) opens in your default browser, and **cloud sync** can carry your account data between devices while the AI itself keeps running on your desktop.
- **Insights** shows how you use tools, skills and models, on this PC.

## Privacy and security

- The backend listens on loopback only and checks the host, origin and a per-session token on every request.
- Your history, memory and files stay in the app's `data` and `Files` folders on your PC.
- Secrets such as integration tokens are encrypted for your Windows account.
- Updates are checked against a published SHA-256 before the installer is opened, and only after you confirm.
- Skills and connectors from outside sources are untrusted. Read what you install.

## Run from source

Use Python 3.14 on Windows. In a virtual environment, install `requirements-build.txt`, then run:

```
python desktop.py
```

Model weights and inference executables are not included. Install a model from the Model library or point Settings at a compatible local endpoint.

## Build and release

Run `build.ps1` from the configured Python environment. It produces the program with PyInstaller and the installer with Inno Setup, and `publish-release.ps1` publishes a GitHub release with checksums.

Required build inputs, excluded from Git on purpose: `runtime/llama-swap.exe`, the model runtime at `runtime/local-ai/runtime-vulkan/` (run `scripts/fetch-model-runtime.ps1` to fetch the checksum-pinned archive), and the Inno Setup compiler at `runtime/inno/ISCC.exe`.

The installer's AppId stays stable so upgrades work. The installed app keeps its data in a `data/` folder inside its installation directory; see [FOLDER-GUIDE.md](FOLDER-GUIDE.md). Design notes are in [DESIGN.md](DESIGN.md) and [PRODUCT.md](PRODUCT.md), and each release has notes in [docs/release-notes](docs/release-notes).

## Status

Luminaria is in active development by Desselle Solution Software. Google sign-in depends on publisher configuration that is not complete, public update distribution is not set up, and installers are not yet code-signed. The repository excludes local histories, credentials, model weights, generated installers and machine configuration.
