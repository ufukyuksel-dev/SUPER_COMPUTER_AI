#!/usr/bin/env python3
"""Render the SUPER_COMPUTER_AI motion promo (MP4 + GIF) with Pillow and ffmpeg.

Every frame is drawn from a pure function of time, so the output is reproducible.

    python3 tools/promo-video/render.py                 # docs/assets/promo.mp4 + promo.gif
    python3 tools/promo-video/render.py --preview 9.0   # write one frame as PNG

Requirements: Python 3.9+, Pillow, ffmpeg on PATH. Fonts: Helvetica Neue / Menlo on macOS,
DejaVu on Linux, otherwise Pillow's built-in font.
"""
from __future__ import annotations

import argparse
import math
import random
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 1920, 1080
FPS = 30
DURATION = 25.5
REPO_URL = "github.com/ufukyuksel-dev/SUPER_COMPUTER_AI"

BG = (8, 11, 24)
TEXT = (236, 239, 246)
DIM = (128, 138, 160)
CYAN = (34, 211, 238)
VIOLET = (167, 139, 250)
PINK = (244, 114, 182)
GREEN = (52, 211, 153)
AMBER = (251, 191, 36)
BLUE = (96, 165, 250)
ORANGE = (251, 146, 60)

ROOT = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------- fonts

def _font(candidates: list[tuple[str, int]], size: int) -> ImageFont.FreeTypeFont:
    for path, index in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size, index=index)
    return ImageFont.load_default(size)


def sans(size: int, weight: str = "bold") -> ImageFont.FreeTypeFont:
    mac = {"bold": 1, "regular": 0, "light": 7, "medium": 10, "thin": 12}[weight]
    linux = "DejaVuSans-Bold.ttf" if weight in ("bold", "medium") else "DejaVuSans.ttf"
    return _font([("/System/Library/Fonts/HelveticaNeue.ttc", mac),
                  (f"/usr/share/fonts/truetype/dejavu/{linux}", 0)], size)


def mono(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    linux = "DejaVuSansMono-Bold.ttf" if bold else "DejaVuSansMono.ttf"
    return _font([("/System/Library/Fonts/Menlo.ttc", 1 if bold else 0),
                  (f"/usr/share/fonts/truetype/dejavu/{linux}", 0)], size)


# ---------------------------------------------------------------- easing / helpers

def clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def prog(t: float, start: float, dur: float) -> float:
    return clamp((t - start) / dur)


def ease_out(x: float) -> float:
    return 1 - (1 - x) ** 3


def ease_in_out(x: float) -> float:
    return 4 * x ** 3 if x < 0.5 else 1 - (-2 * x + 2) ** 3 / 2


def ease_back(x: float) -> float:
    c1, c3 = 1.70158, 2.70158
    return 1 + c3 * (x - 1) ** 3 + c1 * (x - 1) ** 2


def rgba(color: tuple[int, int, int], alpha: float) -> tuple[int, int, int, int]:
    return (*color, int(255 * clamp(alpha)))


def fade_layer(layer: Image.Image, opacity: float) -> Image.Image:
    if opacity >= 1:
        return layer
    alpha = layer.getchannel("A").point(lambda v: int(v * clamp(opacity)))
    layer.putalpha(alpha)
    return layer


def text_center(draw: ImageDraw.ImageDraw, xy, text, font, fill) -> None:
    draw.text(xy, text, font=font, fill=fill, anchor="mm")


def scene_opacity(t: float, start: float, end: float, fade: float = 0.45) -> float:
    if t < start or t > end:
        return 0.0
    return min(ease_out(prog(t, start, fade)), ease_out(clamp((end - t) / fade)))


_GLOW_CACHE: dict = {}


def glow(color, radius: int) -> Image.Image:
    key = (color, radius)
    if key not in _GLOW_CACHE:
        size = radius * 2
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.ellipse((radius * 0.55, radius * 0.55, size - radius * 0.55, size - radius * 0.55),
                  fill=rgba(color, 0.9))
        _GLOW_CACHE[key] = img.filter(ImageFilter.GaussianBlur(radius * 0.28))
    return _GLOW_CACHE[key]


def paste_glow(canvas: Image.Image, center, color, radius: int, alpha: float) -> None:
    g = glow(color, radius)
    if alpha < 1:
        g = fade_layer(g.copy(), alpha)
    canvas.alpha_composite(g, (int(center[0] - radius), int(center[1] - radius)))


# ---------------------------------------------------------------- background

_rng = random.Random(7)
PARTICLES = [(_rng.uniform(0, W), _rng.uniform(0, H), _rng.uniform(-14, 14), _rng.uniform(-9, 9),
              _rng.uniform(1.2, 3.2), _rng.choice([CYAN, VIOLET, PINK, BLUE])) for _ in range(90)]


def make_base() -> Image.Image:
    base = Image.new("RGBA", (W, H), (*BG, 255))
    d = ImageDraw.Draw(base)
    for y in range(0, H, 4):  # vertical gradient
        k = y / H
        d.rectangle((0, y, W, y + 4), fill=(int(8 + 10 * k), int(11 + 4 * k), int(24 + 22 * k), 255))
    for x in range(0, W + 1, 60):
        for y in range(0, H + 1, 60):
            d.point((x, y), fill=(40, 50, 80, 255))
    vign = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    paste_glow(vign, (W * 0.2, H * 0.15), VIOLET, 700, 0.10)
    paste_glow(vign, (W * 0.85, H * 0.9), CYAN, 700, 0.08)
    base.alpha_composite(vign)
    return base


def draw_particles(canvas: Image.Image, t: float) -> None:
    d = ImageDraw.Draw(canvas)
    for x0, y0, vx, vy, r, color in PARTICLES:
        x = (x0 + vx * t) % W
        y = (y0 + vy * t) % H
        tw = 0.35 + 0.35 * math.sin(t * 1.7 + x0)
        d.ellipse((x - r, y - r, x + r, y + r), fill=rgba(color, tw))


# ---------------------------------------------------------------- scenes

def scene_title(t: float) -> Image.Image:
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    title = "SUPER_COMPUTER_AI"
    n = int(len(title) * ease_out(prog(t, 0.3, 1.4)))
    shown = title[:n]
    font = sans(128)
    full_w = d.textlength(title, font=font)
    x0 = (W - full_w) / 2
    paste_glow(layer, (W / 2, H / 2 - 40), VIOLET, 520, 0.22 * prog(t, 0.2, 1.0))
    d.text((x0, H / 2 - 40), shown, font=font, fill=TEXT, anchor="lm")
    if n < len(title) or int(t * 2.5) % 2 == 0:
        cx = x0 + d.textlength(shown, font=font) + 10
        d.rectangle((cx, H / 2 - 100, cx + 14, H / 2 + 20), fill=CYAN)
    p = ease_out(prog(t, 1.9, 0.8))
    text_center(d, (W / 2, H / 2 + 80 + 30 * (1 - p)),
                "One home for your AI agent's superpowers", sans(52, "light"), rgba(TEXT, p))
    p2 = ease_out(prog(t, 2.5, 0.8))
    text_center(d, (W / 2, H / 2 + 160), "skills  ·  MCP servers  ·  agent roles  ·  instructions",
                sans(34, "regular"), rgba(CYAN, p2))
    return layer


NODES = [("23", "Skills", "workflows the agent follows", CYAN, -148),
         ("6", "MCP servers", "tools the agent can call", VIOLET, -32),
         ("5", "Agent roles", "architect · researcher · evaluator", PINK, 32),
         ("1", "Installer", "one command, journaled, reversible", GREEN, 148)]


def scene_core(t: float, t0: float) -> Image.Image:
    lt = t - t0
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    cx, cy = W / 2, H / 2 + 30
    text_center(d, (W / 2, 110), "Everything that makes an agent capable, in one repo",
                sans(50, "medium"), rgba(TEXT, ease_out(prog(lt, 0.0, 0.6))))

    # expanding pulse rings
    for k in range(3):
        ph = ((lt * 0.6) + k / 3) % 1
        r = 110 + 260 * ph
        d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=rgba(CYAN, 0.35 * (1 - ph)), width=3)

    orbit = 360
    for i, (num, label, sub, color, ang) in enumerate(NODES):
        appear = prog(lt, 0.5 + i * 0.35, 0.7)
        if appear <= 0:
            continue
        a = math.radians(ang + lt * 4)
        nx, ny = cx + orbit * 1.35 * math.cos(a), cy + orbit * 0.72 * math.sin(a)
        # connector drawn from core outward
        lp = ease_out(appear)
        ex, ey = cx + (nx - cx) * lp, cy + (ny - cy) * lp
        d.line((cx, cy, ex, ey), fill=rgba(color, 0.55), width=4)
        # travelling data dot
        dp = (lt * 0.9 + i * 0.25) % 1
        dx, dy = cx + (ex - cx) * dp, cy + (ey - cy) * dp
        d.ellipse((dx - 7, dy - 7, dx + 7, dy + 7), fill=rgba(color, 0.95 * appear))
        s = ease_back(appear)
        r = 100 * s
        paste_glow(layer, (nx, ny), color, int(150 * max(s, 0.2)), 0.35 * appear)
        d.ellipse((nx - r, ny - r, nx + r, ny + r), fill=(14, 18, 36, 255), outline=rgba(color, 1), width=5)
        count = int(round(int(num) * ease_out(prog(lt, 0.7 + i * 0.35, 1.0))))
        if appear > 0.3:
            text_center(d, (nx, ny - 8), str(count), sans(int(66 * s)), rgba(color, appear))
            text_center(d, (nx, ny + 40), label, sans(22, "medium"), rgba(TEXT, appear))
            text_center(d, (nx, ny + r + 30), sub, sans(24, "regular"), rgba(DIM, appear))

    # core
    pulse = 1 + 0.05 * math.sin(lt * 5)
    r = 110 * pulse * ease_back(prog(lt, 0.0, 0.8))
    paste_glow(layer, (cx, cy), VIOLET, 300, 0.55)
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(28, 22, 62, 255), outline=rgba(VIOLET, 1), width=6)
    text_center(d, (cx, cy - 10), "AI", sans(int(84 * pulse)), TEXT)
    text_center(d, (cx, cy + 50), "core", sans(24, "light"), rgba(VIOLET, 1))
    return layer


CARDS = [("Google Ads", "campaigns · budgets · reports", BLUE),
         ("Meta Ads", "Facebook & Instagram campaigns", VIOLET),
         ("TikTok Ads", "app campaigns & creatives", PINK),
         ("Premiere Pro", "280+ video-editing tools", ORANGE),
         ("Android ADB", "screens · taps · UI review", GREEN),
         ("Jev Browser", "agents that browse the web", CYAN)]


def scene_cards(t: float, t0: float) -> Image.Image:
    lt = t - t0
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    p = ease_out(prog(lt, 0, 0.6))
    text_center(d, (W / 2, 130), "Real tools. Real accounts.", sans(66), rgba(TEXT, p))
    text_center(d, (W / 2, 205), "MCP servers that plug straight into Claude Code and Codex",
                sans(32, "light"), rgba(DIM, p))
    cw, ch, gap = 520, 230, 50
    gx = (W - (3 * cw + 2 * gap)) / 2
    gy = 300
    for i, (name, sub, color) in enumerate(CARDS):
        a = prog(lt, 0.35 + i * 0.22, 0.7)
        if a <= 0:
            continue
        e = ease_back(a)
        col, row = i % 3, i // 3
        x = gx + col * (cw + gap)
        y = gy + row * (ch + gap) + 90 * (1 - e)
        hover = 6 * math.sin(lt * 2.2 + i)
        y += hover * a
        paste_glow(layer, (x + cw / 2, y + ch / 2), color, 300, 0.16 * a)
        d.rounded_rectangle((x, y, x + cw, y + ch), radius=28, fill=(16, 21, 42, int(245 * a)),
                            outline=rgba(color, a), width=3)
        d.rounded_rectangle((x, y, x + 12, y + ch), radius=6, fill=rgba(color, a))
        # icon dot + status
        d.ellipse((x + 50, y + 52, x + 86, y + 88), fill=rgba(color, a))
        d.text((x + 108, y + 70), name, font=sans(46), fill=rgba(TEXT, a), anchor="lm")
        d.text((x + 50, y + 140), sub, font=sans(28, "regular"), fill=rgba(DIM, a), anchor="lm")
        live = prog(lt, 1.4 + i * 0.22, 0.4)
        if live > 0:
            blink = 0.6 + 0.4 * math.sin(lt * 6 + i)
            d.ellipse((x + 50, y + 180, x + 66, y + 196), fill=rgba(GREEN, live * blink))
            d.text((x + 80, y + 188), "connected", font=mono(22), fill=rgba(GREEN, live), anchor="lm")
    return layer


TERM_LINES = [
    ("cmd", "python3 scripts/install.py --bundle ads --mcp"),
    ("ok", "23 skills linked into Claude Code & Codex"),
    ("ok", "MCP servers registered (config kept byte for byte)"),
    ("ok", "journal written - rollback any time"),
    ("gap", ""),
    ("ask", "list my Google Ads campaigns"),
    ("ans", "campaigns listed with status, budget and bidding"),
    ("ask", "open a random website with Jev and read the title"),
    ("ans", "\"Dragon Group - Wikipedia\""),
]


def scene_terminal(t: float, t0: float) -> Image.Image:
    lt = t - t0
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    p = ease_out(prog(lt, 0, 0.6))
    text_center(d, (W / 2, 110), "Install once. Then just ask.", sans(66), rgba(TEXT, p))
    x, y, w, h = 260, 190 + 40 * (1 - p), W - 520, 800
    paste_glow(layer, (W / 2, y + h / 2), CYAN, 700, 0.10 * p)
    d.rounded_rectangle((x, y, x + w, y + h), radius=24, fill=(10, 13, 26, int(250 * p)),
                        outline=rgba((60, 72, 110), p), width=2)
    d.rounded_rectangle((x, y, x + w, y + 64), radius=24, fill=rgba((24, 29, 52), p))
    d.rectangle((x, y + 40, x + w, y + 64), fill=rgba((24, 29, 52), p))
    for k, c in enumerate([(255, 95, 86), (255, 189, 46), (39, 201, 63)]):
        d.ellipse((x + 30 + k * 36, y + 22, x + 50 + k * 36, y + 42), fill=rgba(c, p))
    text_center(d, (x + w / 2, y + 32), "claude  —  SUPER_COMPUTER_AI", mono(22), rgba(DIM, p))

    f, fb = mono(32), mono(32, bold=True)
    cursor_t = 0.5
    ly = y + 120
    for kind, txt in TERM_LINES:
        if kind == "gap":
            ly += 30
            cursor_t += 0.35
            continue
        typing = kind in ("cmd", "ask")
        dur = len(txt) * 0.024 if typing else 0.0
        if lt < cursor_t:
            break
        if typing:
            n = int(len(txt) * clamp((lt - cursor_t) / dur))
            prefix, pcol = ("$ ", GREEN) if kind == "cmd" else ("> ", VIOLET)
            d.text((x + 50, ly), prefix, font=fb, fill=pcol)
            d.text((x + 50 + d.textlength(prefix, font=fb), ly), txt[:n], font=f, fill=TEXT)
            if n < len(txt) and int(lt * 6) % 2 == 0:
                cx = x + 50 + d.textlength(prefix, font=fb) + d.textlength(txt[:n], font=f)
                d.rectangle((cx + 2, ly + 2, cx + 20, ly + 38), fill=CYAN)
            cursor_t += dur + 0.35
        else:
            a = ease_out(clamp((lt - cursor_t) / 0.3))
            mark, col = ("✓ ", GREEN) if kind == "ok" else ("◆ ", AMBER)
            d.text((x + 90, ly), mark, font=fb, fill=rgba(col, a))
            d.text((x + 90 + d.textlength(mark, font=fb), ly), txt, font=f,
                   fill=rgba(TEXT if kind == "ans" else DIM, a))
            cursor_t += 0.4
        ly += 62
    return layer


def scene_outro(t: float, t0: float) -> Image.Image:
    lt = t - t0
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    cx, cy = W / 2, H / 2 - 150
    s = ease_back(prog(lt, 0, 0.8))
    pulse = 1 + 0.04 * math.sin(lt * 4)
    paste_glow(layer, (cx, cy), VIOLET, 380, 0.5 * s)
    for k, color in enumerate([CYAN, VIOLET, PINK]):
        ang = lt * (40 + 25 * k) + k * 120
        r = (120 + 22 * k) * s
        box = (cx - r, cy - r, cx + r, cy + r)
        d.arc(box, ang, ang + 230, fill=rgba(color, 0.9), width=6)
    r = 90 * s * pulse
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(28, 22, 62, 255), outline=rgba(VIOLET, 1), width=5)
    text_center(d, (cx, cy), "AI", sans(int(76 * max(s, 0.1))), TEXT)

    p = ease_out(prog(lt, 0.5, 0.7))
    text_center(d, (W / 2, H / 2 + 80 + 20 * (1 - p)), "Build your own super AI.", sans(84), rgba(TEXT, p))
    p = ease_out(prog(lt, 1.0, 0.7))
    badges = [("Claude Code", VIOLET), ("Codex", CYAN), ("MIT licensed", GREEN)]
    bf = sans(34, "medium")
    widths = [d.textlength(b, font=bf) + 70 for b, _ in badges]
    bx = (W - (sum(widths) + 30 * (len(badges) - 1))) / 2
    by = H / 2 + 190
    for (label, color), bw in zip(badges, widths):
        d.rounded_rectangle((bx, by, bx + bw, by + 66), radius=33, fill=rgba((18, 22, 44), p),
                            outline=rgba(color, p), width=3)
        text_center(d, (bx + bw / 2, by + 33), label, bf, rgba(color, p))
        bx += bw + 30
    p = ease_out(prog(lt, 1.6, 0.7))
    text_center(d, (W / 2, H / 2 + 340), REPO_URL, mono(40, bold=True), rgba(TEXT, p))
    text_center(d, (W / 2, H / 2 + 395), "open source  ·  no secrets in the repo  ·  one-command install",
                sans(28, "light"), rgba(DIM, p))
    return layer


SCENES = [  # (start, end, renderer)
    (0.0, 4.0, lambda t: scene_title(t)),
    (3.8, 9.0, lambda t: scene_core(t, 3.8)),
    (8.8, 13.2, lambda t: scene_cards(t, 8.8)),
    (13.0, 21.0, lambda t: scene_terminal(t, 13.0)),
    (20.8, DURATION + 1, lambda t: scene_outro(t, 20.8)),
]


def render_frame(t: float, base: Image.Image) -> Image.Image:
    canvas = base.copy()
    draw_particles(canvas, t)
    for start, end, fn in SCENES:
        o = scene_opacity(t, start, end)
        if o > 0:
            canvas.alpha_composite(fade_layer(fn(t), o))
    fade_in = ease_out(prog(t, 0, 0.4))
    if fade_in < 1:
        canvas = Image.blend(Image.new("RGBA", (W, H), (*BG, 255)), canvas, fade_in)
    return canvas.convert("RGB")


# ---------------------------------------------------------------- output

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out-dir", type=Path, default=ROOT / "docs" / "assets")
    ap.add_argument("--preview", type=float, help="write a single PNG frame at this second and exit")
    ap.add_argument("--gif-width", type=int, default=800)
    args = ap.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    base = make_base()

    if args.preview is not None:
        out = args.out_dir / f"preview-{args.preview:.1f}.png"
        render_frame(args.preview, base).save(out)
        print(out)
        return 0

    mp4 = args.out_dir / "promo.mp4"
    gif = args.out_dir / "promo.gif"
    ff = subprocess.Popen(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
         "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "slow", "-crf", "20",
         "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(mp4)],
        stdin=subprocess.PIPE)
    total = int(DURATION * FPS)
    for i in range(total):
        ff.stdin.write(render_frame(i / FPS, base).tobytes())
        if i % FPS == 0:
            print(f"\rframe {i}/{total}", end="", file=sys.stderr, flush=True)
    ff.stdin.close()
    if ff.wait() != 0:
        print("\nffmpeg failed", file=sys.stderr)
        return 1
    print(f"\n{mp4}", file=sys.stderr)

    vf = (f"fps=12,scale={args.gif_width}:-1:flags=lanczos,split[a][b];"
          "[a]palettegen=max_colors=96:stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=4")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(mp4), "-vf", vf, str(gif)], check=True)
    print(gif, file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
