# Spatial design evidence boundary

Source review: web/appearance.js, palettes.js, preferences.js, style.css, spatial.css, core.js and spatial-ui.js. DESIGN.md and its sidecar describe these implementations.

The current appearance contract is Light, Dark and Follow system, persistent shared accent, optional per-mode accent and separate per-mode customization of UI and spatial roles. The prepaint cache is PC/browser-local; profile preferences hydrate later. Low-contrast custom choices warn rather than being blocked.

The entity and regional lattice render separately. Recorded activity supplies graph nodes, edges and status; model-provided steps and reasoning are labeled. Names and statuses are visible through DOM node labels, activity outline and evidence details. Keyboard selection, Enter inspection, Escape return and WebGL fallback are implemented paths. Compact details provide a return to the outline. Queued messages remain explicit in the conversation controls.

Browser review captures are expected at .impeccable/review/spatial-light.png, spatial-dark.png, spatial-accent.png, spatial-compact.png and spatial-fallback.png. They use mocked API fixtures and are presentation evidence only. The main browser pass refreshed and inspected all five captures after the framing, labels and compact-transition fixes. The final bounded design review cleared those fixes; native acceptance remains pending.

Not established here: native WebView2 rendering, real model-driven end-to-end event execution, microphone/speaker acceptance, GPU completion timings, installation/update behavior or release readiness. A source path or fixture screenshot does not establish those outcomes.

Superseded documentation corrected: graphite/ivory-only branding, removed custom palette claims, acid-mint-only rules, temporary Studio name and the retired decorative-only filament description. No code, test, build or release files were changed by this documentation pass.
