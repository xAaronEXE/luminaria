# Brand assets

The Lumen orb is the Luminaria mark.

- `web/brand/luminaria.svg` is the vector master. `luminaria.png` and the multi-resolution Windows icon `luminaria.ico` are made from it. The installer, the program file, the window and the taskbar all use `luminaria.ico`.
- `web/brand/social-cover.svg` is the header image used in the README. `social-cover.png` and `social-cover.jpg` are copies for social previews.
- The sign-in screen draws the live orb in code (see `web/gate.css`), so it needs no image files.

When the mark changes, replace the master and regenerate the PNG and ICO, then rebuild. Windows caches icons, so an old icon can keep showing in File Explorer until the icon cache is refreshed.
