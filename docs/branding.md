# Brand assets

`web/brand/luminaria.svg` is the centered vector master. Its visible alpha-weighted center is 400,400 on an 800-square canvas, so the sign-in scene rotates around the symbol's optical center. The silhouette is preserved. The bottom backlight is a stationary scene layer.

The PNG and multi-resolution Windows ICO are generated from that master. `social-cover.svg` is the matching static GitHub/README header; JPEG and PNG derivatives remain available for social previews. The warm ivory and green-black palette follows the previous cover. `sign-in-toroidal.svg` supplies animated lattice pathways behind the symbol. Motion respects the operating system's reduced-motion preference.

Regenerate vectors with `python scripts/build-brand-vectors.py` (requires fontTools and Windows Segoe UI). Add `--export` to generate PNG, JPEG and ICO derivatives (also requires Pillow and resvg-py). The vectors contain paths, not embedded raster images; cover lettering is outlined for consistent display.

`web/brand-preview.html` compares the two directions without performing authentication. Production sign-in uses the same centered assets in `brand-gate.css`; existing authentication logic is retained. JavaScript syntax, SVG rendering/markup and alpha-centroid checks passed. Native visual acceptance is separate from these checks.
