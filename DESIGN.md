---
name: Luminaria
description: A local AI desktop with graphite and warm ivory, plus a branded light appearance.
colors:
  bg: "#141A17"
  sidebar: "#101612"
  panel: "#181F1A"
  raised: "#1B231F"
  hover: "#212B26"
  line: "#2C3831"
  text: "#F4F4F0"
  muted: "#C5CBC5"
  dim: "#A6B0A8"
  accent: "#EAE6D9"
  danger: "#FF6B5E"
  warning: "#E3C886"
typography:
  display:
    fontFamily: "'Segoe UI',system-ui,sans-serif"
    fontSize: "clamp(36px,4vw,58px)"
    fontWeight: 500
    lineHeight: 1.15
    letterSpacing: "-.035em"
  body:
    fontFamily: "'Segoe UI',system-ui,sans-serif"
    fontSize: "14px"
    lineHeight: 1.55
  label:
    fontFamily: "'Segoe UI',system-ui,sans-serif"
    fontSize: "12px"
  code:
    fontFamily: "Consolas,'Cascadia Code',monospace"
    fontSize: "12px"
    lineHeight: 1.55
rounded:
  control: "7px"
  icon: "6px"
  send: "8px"
  voice: "10px"
  card: "12px"
  composer: "14px"
spacing:
  tight: "8px"
  control: "12px"
  panel: "16px"
  section: "18px"
components:
  button-primary:
    backgroundColor: "{colors.accent}"
    textColor: "{colors.bg}"
    rounded: "{rounded.control}"
    padding: "8px 13px"
  button-secondary:
    backgroundColor: "{colors.raised}"
    textColor: "{colors.text}"
    rounded: "{rounded.control}"
    padding: "8px 13px"
  field:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.text}"
    rounded: "{rounded.control}"
    padding: "10px 12px"
  task-navigation:
    textColor: "{colors.muted}"
    rounded: "{rounded.control}"
    padding: "10px 11px"
  attachment-chip:
    backgroundColor: "{colors.hover}"
    textColor: "{colors.text}"
    rounded: "5px"
    padding: "3px 7px"
  user-message:
    backgroundColor: "{colors.raised}"
    textColor: "{colors.text}"
    rounded: "{rounded.card}"
    padding: "18px 20px"
  composer:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.text}"
    rounded: "{rounded.composer}"
  voice-bar:
    backgroundColor: "{colors.raised}"
    textColor: "{colors.text}"
    rounded: "{rounded.voice}"
    padding: "10px 12px"
---

# Design System: Studio

## Overview

**Creative North Star: "A local agent's conversation, evidence and pending actions visible together."**

The user-pinned Codex-like workspace uses forestry graphite structural surfaces, acid mint actions, restrained controls and spacious conversation text. A full-window perspective filament field gives depth behind translucent panels while leaving the working interface readable.

Studio is the temporary visible brand; the final user-selected name is undecided. This records the implemented plain HTML/JavaScript interface, with locally served libraries and no CDN dependencies, intended for the native Windows WebView2 wrapper. It does not certify installation, voice quality, backend reliability or release readiness.

**Key Characteristics:**
- Conversation, task history and workspace evidence share one window.
- Acid mint identifies primary actions and selected states.
- Perspective filaments remain behind the working surfaces.
- Voice is explicitly enabled by the user.

## Colors

### Primary

Acid mint is the user-pinned accent: send, primary buttons, selected icons, focused controls and active voice state. Warning and danger colors distinguish offline or attention states from failures and denied actions.

### Neutral

Forestry graphite is the user-pinned background. Panel, raised and hover tones separate editing surfaces and interaction states. Text, muted and dim roles establish hierarchy; thin green-gray lines divide task rows, panels and tabs. Values above reflect the final CSS cascade, including overrides later in the stylesheet.

**The Working Surface Rule.** Keep decorative light behind legible, sufficiently opaque working surfaces.

## Typography

Segoe UI with local system fallbacks carries the interface; Consolas with Cascadia Code fallback carries code and numeric context values. No font download is required. The display role is the welcome prompt. Working text stays compact: body text uses the body token, conversation prose has a roomier line-height (1.8), and metadata ranges from 9px to 12px. Sheet titles use 25px and weight 550. The final welcome heading rule overrides earlier mobile heading sizes; do not document the obsolete sizes as current.

## Layout

The full-height desktop grid has a 238px task sidebar, flexible conversation with a 360px minimum track, and a 300px inspector. At 1600px and wider, the default grid uses 260px and 330px side tracks. The collapsed-inspector rule retains its own 238px sidebar track. Conversation content is capped at 780px; the composer and approvals at 800px; the welcome section at 650px. The composer anchors below the independently scrolling conversation and can itself scroll with a 60vh maximum height.

At 1180px and below, the inspector becomes an optional right overlay and the sidebar narrows to 210px. At 720px and below, the task sidebar becomes an optional 250px overlay, the main area fills the width, the header becomes 58px high and forms use one column. The voice row wraps at 800px. The final welcome margin starts at clamp(32px,8vh,90px), with no extra top padding. Sidebars can scroll to preserve access to bottom controls.

## Elevation & Depth

Most controls use tonal layering and thin borders. Sheets, compact overlays and toasts use shadows; the sheet casts -12px 0 48px #0005 and the toast uses 0 8px 30px #0006. The main surface overlays the filament field with graphite at .65 opacity, side panels at .89 and the top bar at .8. The composer region has a graphite gradient approaching .97 opacity.

The local WebGL field renders actual perspective-projected lines and points across the window. It is decorative, pointer-transparent and hidden from accessibility APIs. Rendering is throttled to approximately 20 fps, device pixel ratio is capped at 2, and the drawing buffer is capped at 3840 by 2160 while preserving aspect ratio. Typing and streamed tokens briefly increase energy. Hidden documents skip drawing; reduced-motion preference starts paused, and a sidebar control stores a pause preference. CSS reduced-motion rules also remove animations, transitions and smooth scrolling. WebGL unavailability removes the field; context loss hides it and its motion control. The obsolete small draggable core markup is removed by core.js.

## Shapes

Controls use small rounded corners; larger message and approval containers use the card radius, with a slightly rounder composer. Dots and the profile symbol are circular. Icons are locally defined, thin-stroke SVGs, generally 18px with smaller contextual variants. Local mark.svg supplies the temporary brand symbol.

## Components

### Buttons and fields

Primary buttons use accent over graphite; secondary buttons use raised surfaces. Hover shifts secondary surfaces to hover and primary buttons to #C9FF67. Disabled buttons reduce opacity to .4 and show a not-allowed cursor. Focus-visible uses a 2px accent outline with a 4px offset; search and the reasoning toggle have focus-within treatment. Standard inputs use panel surfaces and a thin line border.

### Navigation and inspector

Task rows truncate long titles. Active rows use the raised surface and an accent icon; hover raises contrast. Inspector tabs expose selection with aria-selected and a 2px accent underline. Files, Activity and Context occupy the same pane. Empty and offline states use explicit text rather than implied success.

### Conversation and composer

User messages are raised rounded blocks; assistant responses remain on the main surface. Tool details and reasoning expand in disclosure controls. Markdown code blocks scroll horizontally and offer copy controls. Attachment chips include removal controls. Send swaps to stop during active execution. Pending approvals appear above the composer, with the action details and explicit approval controls visible. The context meter turns warning-colored as defined by runtime state; compaction markers remain distinct from messages.

### Sheets and feedback

Model library, memory, tools, skills, schedules and settings use a right-side modal sheet. Escape and the close button dismiss it; app.js contains focus trapping and restoration. Toasts expose status and an error variant. Benchmark and capability descriptions reflect supplied records; the visual design makes no claim that a model or integration has been validated.

### Voice

The Voice button starts inactive. After readiness and microphone access, it changes to Mic on and reveals a bordered voice bar with Listening, Transcribing, Thinking, Preparing speech, Speaking, interruption, failure or approval-review text. Interrupt and End voice remain explicit controls. A chat change ends the voice session. Voice uses the normal task route and does not grant tool approval. These are implemented UI states, not claims of successful microphone or speech-model testing.

## Do's and Don'ts

### Do
- Preserve the user-pinned graphite and acid mint identity.
- Keep conversation, evidence and approval controls readable over the filament field.
- Preserve visible keyboard focus and reduced-motion behavior.
- Label unavailable, pending and failed states explicitly.

### Don't
- Treat Studio as the approved final product name.
- Add CDN or remote font dependencies to this local interface.
- Replace the full-window filaments with the retired small draggable core.
- Claim voice, model, installer or integration testing from visual review alone.

Source snapshot: web/style.css, web/index.html, web/app.js, web/core.js and web/voice.js. Review captures are .impeccable/review/desktop.png, compact.png and user-3840.png; they are visual references, not runtime acceptance evidence.

## Appearance revision, 2026-10-16
Only Dark / Graphite and Light / Ivory are exposed. Custom palette controls are superseded. `web/preferences.js` defines both semantic token sets. Voice mode morphs a neural lattice into a torus; microphone and output FFT magnitudes drive deformation. Activity pulses represent observed application states, not hidden model thoughts. Reduced-motion and the motion preference suppress spatial animation.
