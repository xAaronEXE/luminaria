---
name: Luminaria
description: A local Windows AI workspace with shared semantic appearance for conversation and spatial activity.
colors:
  light-bg: "#FFFFFF"
  light-sidebar: "#F7F7F5"
  light-panel: "#FCFCFB"
  light-raised: "#F0F0ED"
  light-hover: "#E6E6E2"
  light-line: "#D5D5D0"
  light-control-line: "#85857F"
  light-text: "#0A0A0A"
  light-muted: "#3A3A37"
  light-dim: "#575753"
  light-success: "#1C6A38"
  light-warning: "#7A5200"
  light-danger: "#A3242C"
  light-info: "#1D4D94"
  light-entity: "#0A0A0A"
  light-lattice: "#7A7A75"
  light-pathway: "#4E4E4A"
  light-particle: "#000000"
  light-glow: "#1A1A1A"
  dark-bg: "#000000"
  dark-sidebar: "#050505"
  dark-panel: "#0A0A0A"
  dark-raised: "#141414"
  dark-hover: "#1D1D1D"
  dark-line: "#2A2A2A"
  dark-control-line: "#5C5C5C"
  dark-text: "#F5F5F2"
  dark-muted: "#C2C2BD"
  dark-dim: "#9E9E99"
  dark-success: "#86D9A3"
  dark-warning: "#EBC57E"
  dark-danger: "#F59D94"
  dark-info: "#9CC0F2"
  dark-entity: "#F5F5F2"
  dark-lattice: "#8A8A86"
  dark-pathway: "#B4B4AF"
  dark-particle: "#FFFFFF"
  dark-glow: "#ECECE7"
typography:
  display:
    fontFamily: "Segoe UI, system-ui, sans-serif"
    fontSize: "clamp(36px,4vw,58px)"
    fontWeight: 500
    lineHeight: 1.15
    letterSpacing: "-.035em"
  body:
    fontFamily: "Segoe UI, system-ui, sans-serif"
    fontSize: "14px"
    lineHeight: 1.55
  label:
    fontFamily: "Segoe UI, system-ui, sans-serif"
    fontSize: "12px"
  code:
    fontFamily: "Consolas, Cascadia Code, monospace"
    fontSize: "12px"
    lineHeight: 1.55
rounded:
  control: "7px"
  card: "12px"
  composer: "14px"
spacing:
  tight: "8px"
  control: "12px"
  panel: "16px"
  section: "18px"
components:
  button-secondary:
    backgroundColor: "{colors.light-raised}"
    textColor: "{colors.light-text}"
    rounded: "{rounded.control}"
    padding: "8px 13px"
  field:
    backgroundColor: "{colors.light-panel}"
    textColor: "{colors.light-text}"
    rounded: "{rounded.control}"
    padding: "10px 12px"
---
# Design System: Luminaria

## Overview

**Creative North Star: "Conversation and recorded work, visible together."**

Luminaria keeps conversation, task history, workspace evidence and pending actions visible together. Black and white establish the default working surface; a shared accent and independent mode overrides let users personalize both interface and spatial activity without changing their semantic roles.

This is a source-grounded record of the plain HTML/JavaScript interface, served by a Python API and hosted in Windows WebView2. It describes implemented visual behavior, not native acceptance or release readiness.

**Key Characteristics:**
- Light, Dark and Follow system share one semantic appearance contract.
- The reactive entity and regional activity lattice are separate persistent layers.
- Recorded activity remains inspectable through text, keyboard controls and evidence.
- Local assets and system fonts support the plain HTML/JavaScript desktop interface.

## Colors

### Primary

With no chosen accent, primary controls use the resolved mode's text color. A shared user accent applies to both modes; a per-mode accent takes precedence. Accent controls selection, focus, progress and active spatial nodes. Black or white button text is selected by measured contrast. Hover, soft fills and selection fills are derived by mixing the accent with the current background or mode endpoint.

### Neutral

The frontmatter records both default mode palettes from `web/appearance.js`. Light is the default. Follow system resolves the operating-system color preference and responds to changes. Surface, border and text roles remain distinct; customization overrides each mode independently. State colors retain their semantic purpose. Entity, particle, lattice, pathway and glow roles customize the 3D workspace independently.

**The Shared Appearance Rule.** Apply resolved semantic tokens to CSS and the renderer together; do not hard-code a separate spatial palette.

Settings warn about selected contrast failures. They permit custom colors and do not enforce universal contrast. Profile preferences persist appearance through the API; the prepaint localStorage cache is shared by the browser origin on this PC and is not profile-isolated.

## Typography

Segoe UI with system fallbacks carries interface text; Consolas with Cascadia Code fallback carries code. No downloaded fonts are required. The welcome prompt uses the display token. Conversation prose uses 14px with 1.8 line height; compact conversation uses 13px. Sheet titles use 25px and weight 550. Interface labels mostly use 11–12px; small supporting metadata exists at 9–10px and should not become the default for new working text. Spatial node labels use 11px, with a truncated title and visible status.

## Layout

The desktop grid uses a 238px sidebar, flexible conversation with a 360px minimum track, and 300px inspector. At 1600px it uses 260px and 330px side tracks. The collapsed-inspector layout retains its own 238px sidebar. Conversation content is capped at 780px, composer and approvals at 800px, and welcome content at 650px. The composer can scroll up to 60vh.

At 1180px the sidebar narrows to 210px and the inspector becomes an optional overlay. At 720px the sidebar becomes an optional 250px overlay and forms become one column. Spatial controls adapt at 900px. The overview measures the actual main panel, header and composer boundaries; it does not rely on the initial CSS inset for final placement. Details and outline share compact space, with a Back to activity outline control. Labels prioritize selected, focused and active/problem nodes, avoid overlap where possible, and show at most 16 nodes; the outline remains the complete textual selection route for the displayed scene.

## Elevation & Depth

Thin borders and tonal surfaces establish structure. The main panel mixes background at 82%, sidebar mixes sidebar at 96%, inspector uses background at 94%, and topbar uses background at 90%. Sheets, menus and toasts use the resolved shadow token; the voice bar is flat in the final cascade.

WebGL renders regional lattice clouds, recorded nodes and curved pathways separately from the toroidal reactive entity. Status changes affect shape and color; transient pathway packets correspond to eligible observed activity. Audio magnitude drives entity deformation when supplied. The renderer targets 30 frames/s normally and 60 during conversation, adapts quality, caps pixel ratio at 1.5 before quality scaling and drawing width at 3840px. Diagnostics report draw submissions rather than GPU completion or model speed. Hidden pages skip drawing. Motion preference and system reduced motion suppress animation; static dirty updates can still render. WebGL failure exposes the activity outline.

**The Evidence Rule.** Animation describes observed execution and supplied audio; it never claims access to hidden thoughts.

## Shapes

Small rounded controls use the control radius; user messages and spatial panels use the card radius; the composer uses the composer radius. Send is 38px square with a 12px radius in the final cascade. Icons are local thin-stroke SVGs. Spatial node point shapes supplement status colors, while DOM labels expose names and states.

## Components

### Buttons and fields

Primary buttons use accent and its computed black/white contrast text. Secondary buttons use raised surfaces, shifting to hover on pointer interaction. Standard field borders use control-line, distinct from structural dividers. Focus-visible uses a 2px accent outline with 3px offset; the spatial canvas target places its ring inward. Disabled buttons dim and use a not-allowed cursor.

### Navigation, chips and conversation

Task rows truncate long titles, raise the selected surface and accent the selected icon. Inspector tabs pair aria-selected with an accent underline. Attachment chips have removal controls; queued messages use raised, wrapped chips. Assistant text remains on the conversation surface, user messages are raised blocks. Pending approval details remain explicit above the composer.

### Appearance settings

Three mode buttons expose pressed state. Shared and per-mode accent controls precede grouped per-mode color fields. Reset actions distinguish the current mode from all appearance. Changes apply immediately, save after a short debounce, and show saving, saved or failure feedback. Contrast warnings are live status content. Motion and metrics use a separate save action.

### Spatial workspace

Task overview keeps recorded execution separate from the conversation, with return, follow activity, focus, outline and refresh controls. Arrow keys select recorded nodes, Enter opens evidence, and Escape returns focus to the prior control. DOM labels and outline buttons open the same details. Tool evidence includes arguments, output and Activity navigation; supplied plans and reasoning are labeled model-provided. Empty and failure states use text. The main conversation becomes inert while overview is open; the composer remains outside that region.

### Voice and fallback

Voice state, interrupt and end controls remain explicit. Conversation keeps transcript and approval controls readable while the entity reacts. Compact layout can hide the entity caption. With unavailable WebGL, textual activity selection remains available. These are implemented UI paths, not successful native microphone or speech-model acceptance claims.

## Do's and Don'ts

### Do
- Do route interface and 3D colors through the same appearance tokens.
- Do preserve readable evidence, explicit state labels and keyboard focus.
- Do honor reduced motion and retain the activity outline when WebGL is unavailable.
- Do distinguish recorded execution from model-provided plans and reasoning.

### Don't
- Don't restore the superseded graphite/ivory-only palette or temporary Studio branding.
- Don't present spatial animation as hidden model thoughts or proof of model correctness.
- Don't claim native, voice, installer or model acceptance from mocked browser previews.
