# promo-video

Renders the project's motion promo ([docs/assets/promo.mp4](../../docs/assets/promo.mp4) and the README GIF)
entirely from code: every frame is a pure function of time, drawn with Pillow and encoded with ffmpeg.

```sh
python3 tools/promo-video/render.py                # writes docs/assets/promo.mp4 and promo.gif
python3 tools/promo-video/render.py --preview 9.0  # one PNG frame at t=9s, for quick iteration
```

Requirements: Python 3.9+, Pillow, `ffmpeg` on `PATH`. Fonts: Helvetica Neue / Menlo on macOS, DejaVu on Linux.

Scenes (25.5 s, 1920×1080, 30 fps): title → AI core with skills / MCP servers / agent roles / installer → MCP
server cards → terminal install and example requests → call to action. Edit the text constants (`NODES`,
`CARDS`, `TERM_LINES`) when the catalog changes.
