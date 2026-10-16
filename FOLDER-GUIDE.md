# Luminaria on this PC

- **App/** — installed desktop executable and its **data/** folder. Chats, memory,
  settings, voices, outputs and profile databases stay here. Previous installation
  data is preserved separately in **App/previous-install-data/**.
- **release/** — latest Windows installer and SHA-256 checksum.
- **web/** and **backend/** — actual application source.
- **skills/** — bundled assistant workflows.
- **docs/specifications/** — master specification, scope, API and brand notes.
- **tests/** — verification tools.
- **auth-service/** — future hosted identity service.
- **runtime/** — local build/runtime dependencies; excluded from Git.
- **.build/** — generated packaging intermediates; safe to regenerate after builds stop.
- **data/** — development evidence and isolated publisher credentials, not active desktop chats; excluded from Git.
- **archive/** — superseded previews, local setup scripts, naming notes and installers;
  preserved for recovery, excluded from Git.

The active desktop app reads App/data. Installed model weights are in **App/models/**. Inference and execution dependencies
are in **runtime/local-ai/**. Neither is included in Git.
PRODUCT.md and DESIGN.md stay at the repository root for design tooling.
