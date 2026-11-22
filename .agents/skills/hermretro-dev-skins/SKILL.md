---
name: hermretro-dev-skins
description: Making an emulator skin (a Chromatic device finish) for hermretro's player. Use to add, change or remove a skin: one folder in player/skins/.
---

# Emulator skins

A skin is one folder, `player/skins/<id>/`. The folder's name is the skin's id: lower-case letters, digits and
dashes, not one of the engine's own finishes (such as `cloud` or `codex`). It holds two files:

- `skin.webp` (or `skin.png`): the handheld, square, **1946×1946**, transparent around the device. The player draws
  the game and its touch controls over it at fixed places, so keep the outline, screen, D-pad, A/B and Select/Start
  exactly where they are in the shipped skins: copy one of their folders (`hermes-white/` repaints easily) and
  change only the finish.
- `skin.json` (optional; every field optional):

```json
{ "name": "Sunset", "edition": "Hermes Edition", "background": "#2b1a12", "ink": "#ffe9d6", "order": 5 }
```

`name` is the label in the Build player's finish menu (`edition · name` in the full player's colour rail);
`background` is the page behind the handheld and the menu swatch, `ink` the text on it (both `#rrggbb`); `order`
places it (lower first, then the id; default 100). The first skin is the one every player starts in.

That is all: the backend (`backend/player/skins.py`) reads the folders, the full player shows the skin first in its
colour rail, and the `player` RPC hands it to the Build page's menu. No code or page rebuild.

**Size.** Every file ships to every user: encode a WebP of about 100 to 200 KB, for example
`cwebp -q 90 -m 6 -sharp_yuv -alpha_q 100 in.png -o skin.webp`.

**Check it.** `python -m unittest tests.backend.player.test_skins` (every folder must be a usable skin holding only
those files), then open the Emulator page and pick it in the colour rail, and in a Build conversation's player switch on
Chromatic and pick it from the finish menu. A skin that cannot be used is left out with a `hermretro: skin …
skipped` warning in the gateway log.
