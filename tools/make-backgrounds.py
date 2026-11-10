#!/usr/bin/env python3
"""Deus Vult backgrounds: a dark CRT field in one of the site's phosphors.

For one phosphor of phosphors.toml, writes into a theme folder (default
build/deus-vult-<phosphor>/) backgrounds/*.png at 3840x2160 (16:9),
unlock.png (the 800x188 boot/login logo) and the Omarchy 4.5 motion: an intro
for each still in backgrounds/intros/ (a CRT powering on and drawing the
still, ending on it) and a looping video background, all 2560x1440 at 24 fps.
Each frame is drawn as an SVG and rendered with rsvg-convert; stills are
stripped with ImageMagick, videos encoded with ffmpeg (x264). The text needs
the JetBrainsMono Nerd Font (Omarchy's default font) installed:

    tools/make-backgrounds.py green-screen                 # everything
    tools/make-backgrounds.py amber-monochrome --only 1-cross --svg /tmp/svg
    tools/make-backgrounds.py blue-phosphor --only intro-3-boot --at 2.5 --svg /tmp/f

tools/build.py runs it as part of a whole theme. The pieces are those of the
Deus Vult README banner generator (deusvult-site brand/banner/make-banner.py):
the radial field, 13x13 Jerusalem cross, ANSI Shadow figlet font
(tools/ansi-shadow.flf), glow and scanlines. Content stays inside a safe area:
clear of the bar at the top, and inside the middle 16:10 and 21:9 crops.
Standard library only, apart from the three renderers.
"""

import argparse
import math
import os
import shutil
import subprocess
import sys
import tempfile
import tomllib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from xml.sax.saxutils import escape

W, H = 3840, 2160
ROOT = Path(__file__).resolve().parent.parent
PHOSPHORS = tomllib.loads((ROOT / "phosphors.toml").read_text(encoding="utf-8"))["phosphor"]
# The phosphor being drawn, set by use(): the ramp of the site's --crt-50 ..
# --crt-500 and the paler steps and field colours of phosphors.toml.
BRIGHT = GREEN = BODY = MUTED = DIM = DEEP = LIGHT = PALE = ""
FIELD: list[str] = []
PHOSPHOR = ""  # e.g. P1 GREEN, for the boot screen


def use(key: str) -> None:
    global BRIGHT, GREEN, BODY, MUTED, DIM, DEEP, LIGHT, PALE, FIELD, PHOSPHOR
    p = PHOSPHORS[key]
    BRIGHT, GREEN, BODY, MUTED, DIM, DEEP = p["ramp"]
    LIGHT, PALE, FIELD = p["light"], p["pale"], p["field"]
    PHOSPHOR = f'{p["code"]} {p["colour"]}'.upper()


FONT = "JetBrainsMono Nerd Font Mono, JetBrainsMono NF, monospace"
CROSS = [  # deusvult-site packages/crt/src/art.ts CROSS, # = one pixel
    "....#####....",
    "..#...#...#..",
    ".###..#..###.",
    "..#...#...#..",
    "#.....#.....#",
    "#.....#.....#",
    "#############",
    "#.....#.....#",
    "#.....#.....#",
    "..#...#...#..",
    ".###..#..###.",
    "..#...#...#..",
    "....#####....",
]


def load_flf(path: Path) -> dict[str, list[str]]:
    """Glyphs of printable ASCII from a FIGlet font, hardblanks as spaces."""
    lines = path.read_text(encoding="utf-8").split("\n")
    header = lines[0].split()
    hardblank, height, comments = header[0][-1], int(header[1]), int(header[5])
    body = lines[1 + comments :]
    glyphs = {}
    for i, code in enumerate(range(32, 127)):
        rows = body[i * height : (i + 1) * height]
        end = rows[-1].rstrip()[-1]
        glyphs[chr(code)] = [r.rstrip().rstrip(end).replace(hardblank, " ") for r in rows]
    return glyphs


def figlet(text: str, glyphs: dict[str, list[str]]) -> list[str]:
    """Full-width figlet rows (ANSI Shadow sets no smushing), blank rows dropped."""
    height = len(glyphs[" "])
    rows = ["".join(glyphs[c][r] for c in text) for r in range(height)]
    while rows and not rows[-1].strip():
        rows.pop()
    return rows


def f(v: float) -> str:
    return f"{v:.1f}"


# Motion. A drawing takes t, seconds into its video, or None for the still;
# every intro has finished at its end, so its last frame is the still.
def span(t: float | None, a: float, b: float) -> float:
    """Progress 0..1 of t through [a, b]; 1 for the still."""
    if t is None:
        return 1.0
    return min(1.0, max(0.0, (t - a) / (b - a)))


def smooth(p: float) -> float:
    return p * p * (3 - 2 * p)


def typed(text: str, p: float) -> str:
    """Text with the first p of it showing; the rest keeps its place, unseen."""
    k = round(len(text) * p)
    rest = f'<tspan fill-opacity="0">{escape(text[k:])}</tspan>' if k < len(text) else ""
    return escape(text[:k]) + rest


def appear(t: float | None, at: float, settle: float = 0.3) -> str | None:
    """Attributes of a pixel lit at `at`: None (unlit) before, a pale flash, then nothing extra."""
    if t is not None and t < at:
        return None
    if t is not None and t < at + settle:
        return f' fill="{PALE}"'
    return ""


def defs(center_y: str = "45%") -> list[str]:
    """Field, scanlines, vignette and glow filters shared by every variant."""
    return [
        "<defs>",
        '<filter id="glow-sm" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation="8" result="b"/>'
        '<feMerge><feMergeNode in="b"/><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>',
        f'<radialGradient id="bg" cx="50%" cy="{center_y}" r="80%"><stop offset="0" stop-color="{FIELD[0]}"/>'
        f'<stop offset="0.55" stop-color="{FIELD[1]}"/><stop offset="1" stop-color="{FIELD[3]}"/></radialGradient>',
        # 6 px a line: halves cleanly to 1080p and to 2/3 for 1440p.
        '<pattern id="scan" width="6" height="6" patternUnits="userSpaceOnUse">'
        '<rect width="6" height="3" fill="#000" opacity="0.3"/></pattern>',
        '<radialGradient id="vignette" cx="50%" cy="50%" r="75%"><stop offset="0.55" stop-color="#000" stop-opacity="0"/>'
        '<stop offset="1" stop-color="#000" stop-opacity="0.65"/></radialGradient>',
        '<filter id="glow" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation="22" result="b"/>'
        '<feMerge><feMergeNode in="b"/><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>',
        '<filter id="halo" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="120"/></filter>',
        '<filter id="soft" x="-10%" y="-50%" width="120%" height="200%"><feGaussianBlur stdDeviation="4" result="b"/>'
        '<feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>',
        "</defs>",
    ]


def frame(body: list[str], center_y: str = "45%", t: float | None = None) -> str:
    """The field, body, scanlines and vignette; with t, a CRT powering on for the first 1.4 s.

    Power-on: black, a bright line drawn out across the middle, the picture
    opening from it washed in phosphor, then settling. The scanlines and
    vignette belong to the glass and stay put.
    """
    picture = [f'<rect width="{W}" height="{H}" fill="url(#bg)"/>', *body]
    if t is not None and t < 1.4:
        if t < 0.15:
            picture = []
        else:
            sx = max(smooth(span(t, 0.15, 0.45)), 0.001)
            sy = 0.006 + 0.994 * (1 - (1 - span(t, 0.45, 0.85)) ** 3)
            flash = 0.6 * (1 - span(t, 0.45, 1.2)) ** 2
            picture = [
                f'<g transform="translate({W / 2} {H / 2}) scale({sx:.4f} {sy:.4f}) translate({-W / 2} {-H / 2})">',
                *picture,
                f'<rect width="{W}" height="{H}" fill="{BRIGHT}" opacity="{flash:.3f}"/>',
                "</g>",
            ]
        picture.insert(0, f'<rect width="{W}" height="{H}" fill="#000"/>')
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
        "<!-- Made with omarchy-deus-vult-theme tools/make-backgrounds.py -->",
        *defs(center_y),
        *picture,
        f'<rect width="{W}" height="{H}" fill="url(#scan)"/>',
        f'<rect width="{W}" height="{H}" fill="url(#vignette)"/>',
        "</svg>",
    ]
    return "\n".join(out) + "\n"


CROSS_PIXELS = sum(row.count("#") for row in CROSS)


def cross(x: float, y: float, px: float, fill: str, attrs: str = "", lit=None) -> list[str]:
    """The 13x13 cross with its top-left corner at x,y, px a pixel.

    lit(i) gives the extra attributes of pixel i in raster order, the way a
    CRT beam draws them, or None to leave it dark.
    """
    out = [f'<g fill="{fill}" {attrs}>']
    i = 0
    for r, cells in enumerate(CROSS):
        for c, cell in enumerate(cells):
            if cell == "#":
                extra = lit(i) if lit else ""
                i += 1
                if extra is not None:
                    out.append(f'<rect x="{f(x + c * px)}" y="{f(y + r * px)}" width="{f(px)}" height="{f(px)}"{extra}/>')
    out.append("</g>")
    return out


def figlet_block(rows: list[str], cx: float, top: float, size: float, attrs: str,
                 shown=lambda i: 1.0) -> tuple[list[str], float]:
    """Figlet rows centred on cx from top, monospace cells 0.6*size wide; returns the SVG and the bottom y.

    shown(i) is how much of row i is drawn yet, from the left.
    """
    cols = max(len(r) for r in rows)
    width = cols * 0.6 * size
    x = cx - width / 2
    line = 1.2 * size
    out = [f'<g font-family="{FONT}" font-size="{f(size)}" {attrs} xml:space="preserve">']
    for i, row in enumerate(rows):
        out.append(
            f'<text x="{f(x)}" y="{f(top + (i + 1) * line)}" textLength="{f(width)}" '
            f'lengthAdjust="spacingAndGlyphs">{typed(row.ljust(cols), shown(i))}</text>'
        )
    out.append("</g>")
    return out, top + len(rows) * line


def spaced(text: str, x: float, y: float, size: float, fill: str, opacity: float, anchor: str = "middle",
           spacing: float = 0.35, glow: bool = True, shown: float = 1.0) -> str:
    filt = ' filter="url(#soft)"' if glow else ""
    return (
        f'<text x="{f(x)}" y="{f(y)}" text-anchor="{anchor}" font-family="{FONT}" font-size="{f(size)}" '
        f'letter-spacing="{f(size * spacing)}" fill="{fill}" opacity="{opacity}"{filt}>{typed(text, shown)}</text>'
    )


def cross_body(t: float | None = None, breath: float = 0.0) -> list[str]:
    """The big cross and its two lines. Intro: the beam draws it pixel by pixel
    (1.2-3.6 s), then the lines type out. breath (-1..1) swells the glow."""
    px = 40
    size = 13 * px
    x, y = (W - size) / 2, (H - size) / 2 - 40
    lit = span(t, 1.2, 3.6)
    return [
        f'<circle cx="{W / 2}" cy="{f(y + size / 2)}" r="{size * 0.75}" fill="{GREEN}" '
        f'opacity="{0.10 * lit * (1 + 0.35 * breath):.3f}" filter="url(#halo)"/>',
        *cross(x, y, px, GREEN, f'filter="url(#glow)" opacity="{0.9 + 0.06 * breath:.3f}"',
               lit=lambda i: appear(t, 1.2 + 2.4 * i / CROSS_PIXELS)),
        spaced("DEUS VULT", W / 2, y + size + 150, 44, GREEN, 0.7, spacing=0.6, shown=span(t, 3.9, 4.4)),
        spaced("EVERY SQUARE PIXEL", W / 2, y + size + 220, 26, MUTED, 0.8, spacing=0.6, glow=False,
               shown=span(t, 4.5, 5.2)),
    ]


def variant_cross(_glyphs, t: float | None = None) -> str:
    """The pixel cross in the middle of a dark CRT field, glowing."""
    return frame(cross_body(t), "47%", t)


LIVE_LOOP = 8.0  # seconds; everything in the live background repeats on it


def variant_live(_glyphs, t: float | None = None) -> str:
    """The cross, alive: its glow breathes and the refresh band rolls down the
    glass, both once a loop so the video repeats without a seam."""
    phase = (t or 0.0) / LIVE_LOOP
    band_h = 520
    band_y = -band_h + (H + band_h) * phase
    band = [
        f'<linearGradient id="band" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{BRIGHT}" stop-opacity="0"/>'
        f'<stop offset="0.8" stop-color="{BRIGHT}" stop-opacity="0.045"/><stop offset="1" stop-color="{BRIGHT}" stop-opacity="0"/>'
        "</linearGradient>",
        f'<rect y="{f(band_y)}" width="{W}" height="{band_h}" fill="url(#band)"/>',
    ]
    return frame([*cross_body(breath=math.sin(2 * math.pi * phase)), *band], "47%")


def variant_motto(glyphs, t: float | None = None) -> str:
    """EVERY SQUARE / PIXEL in ANSI Shadow, as on the site's logo. Intro: the
    words type out (1.0-3.7 s), the small cross is drawn, the footer types."""
    size = 30
    rows = figlet("EVERY SQUARE", glyphs)
    pixel = figlet("PIXEL", glyphs)
    cols = max(len(r) for r in rows)
    first = len(rows)
    rows = rows + [""] + [r.center(cols).rstrip() for r in pixel]
    block_h = len(rows) * 1.2 * size
    top = (H - block_h) / 2 - 80
    # PIXEL is centred in the full width, so its typing spans the middle columns.
    word = span(t, 2.9, 3.7)
    margin = (cols - max(len(r.strip()) for r in pixel)) / 2 / cols
    art, bottom = figlet_block(
        rows, W / 2, top, size, f'fill="{GREEN}" filter="url(#glow-sm)" opacity="0.85"',
        shown=lambda i: span(t, 1.0, 2.8) if i < first else margin + (1 - 2 * margin) * word if word < 1 else 1.0,
    )
    px = 8
    body = [
        f'<ellipse cx="{W / 2}" cy="{f(top + block_h / 2)}" rx="1500" ry="520" fill="{GREEN}" '
        f'opacity="{0.07 * span(t, 1.0, 3.7):.3f}" filter="url(#halo)"/>',
        *art,
        *cross(W / 2 - 13 * px / 2, bottom + 110, px, GREEN, 'filter="url(#soft)" opacity="0.8"',
               lit=lambda i: appear(t, 3.9 + 0.7 * i / CROSS_PIXELS, settle=0.15)),
        spaced("DEUS VULT. GOD WILLS IT.", W / 2, bottom + 110 + 13 * px + 90, 26, MUTED, 0.85, spacing=0.6,
               glow=False, shown=span(t, 4.7, 5.4)),
    ]
    return frame(body, t=t)


def boot_lines() -> list[tuple[str, str, float]]:
    """(text, colour, opacity); kept impersonal: no names, places or hosts."""
    return [
        ("DEUS VULT DIGITAL BIOS v19.84  (C) EST. 1984", BRIGHT, 0.9),
        ("", GREEN, 1),
        (f"PHOSPHOR ......... {PHOSPHOR:<14} [ OK ]", BODY, 0.85),
        ("SCANLINES ........ 525            [ OK ]", BODY, 0.85),
        ("MEMORY TEST ...... 640K           [ OK ]", BODY, 0.85),
        ("ORDER ............ BEFORE EXPANSION", BODY, 0.85),
        ("STEWARDSHIP ...... BEFORE SCALE", BODY, 0.85),
        ("LOCATION ......... [CLASSIFIED]", BODY, 0.85),
        ("", GREEN, 1),
        ("BOOTING OMARCHY ...", GREEN, 0.9),
    ]


def fetch_lines() -> list[tuple[str, str]]:
    return [
        ("guest@deusvult", BRIGHT),
        ("--------------", DIM),
        ("OS       Omarchy", BODY),
        ("WM       Hyprland", BODY),
        ("THEME    Deus Vult", BODY),
        ("MOTTO    EVERY SQUARE PIXEL", BODY),
        ("EST.     1984", BODY),
    ]


def variant_boot(_glyphs, t: float | None = None) -> str:
    """A boot screen: BIOS lines, a fastfetch with the cross, the prompt.
    Intro: the BIOS lines print (1.2-3.2 s), fastfetch is typed and runs, the
    prompt comes back."""

    def by(at: float) -> bool:
        return t is None or t >= at

    size = 34
    line = 1.5 * size
    x = 300  # inside the 16:10 crop (192 px a side)
    y = 400  # below the bar, inside the 21:9 crop (257 px top and bottom)
    body = [f'<g font-family="{FONT}" font-size="{size}" filter="url(#soft)" xml:space="preserve">']
    for k, (text, fill, opacity) in enumerate(boot_lines()):
        y += line
        at = 1.2 + 0.2 * k
        if text and by(at):
            body.append(f'<text x="{x}" y="{f(y)}" fill="{fill}" opacity="{opacity}">{typed(text, span(t, at, at + 0.15))}</text>')
    y += line * 2
    if by(3.3):
        body.append(
            f'<text x="{x}" y="{f(y)}" fill="{GREEN}" opacity="0.65">guest@deusvult:~$ '
            f'<tspan opacity="1" fill="{BRIGHT}">{typed("fastfetch", span(t, 3.4, 3.8))}</tspan></text>'
        )
    body.append("</g>")
    px = 24
    top = y + line
    body += cross(x, top, px, GREEN, 'filter="url(#glow-sm)"',
                  lit=lambda i: appear(t, 4.1 + 0.4 * i / CROSS_PIXELS, settle=0.1))
    fx = x + 13 * px + 110
    body.append(f'<g font-family="{FONT}" font-size="{size}" filter="url(#soft)" xml:space="preserve">')
    fetch = fetch_lines()
    for i, (text, fill) in enumerate(fetch):
        if by(4.1 + 0.05 * i):
            body.append(f'<text x="{fx}" y="{f(top + size + i * line)}" fill="{fill}">{escape(text)}</text>')
    swatch_y = top + size + len(fetch) * line - size * 0.6
    if by(4.5):
        for i, colour in enumerate([DEEP, DIM, MUTED, BODY, GREEN, BRIGHT, LIGHT, PALE]):
            body.append(f'<rect x="{fx + i * size * 1.2}" y="{f(swatch_y)}" width="{f(size * 1.2)}" height="{size}" fill="{colour}"/>')
    body.append("</g>")
    y = max(top + 13 * px, swatch_y + size) + line * 2
    if by(4.8):
        body.append(
            f'<text x="{x}" y="{f(y)}" font-family="{FONT}" font-size="{size}" fill="{GREEN}" opacity="0.65" '
            f'filter="url(#soft)">guest@deusvult:~$ <tspan fill="{BRIGHT}" opacity="1">█</tspan></text>'
        )
    body.append(spaced("EVERY SQUARE PIXEL", W - 300, H - 330, 26, MUTED, 0.8, anchor="end", spacing=0.6, glow=False,
                       shown=span(t, 5.0, 5.6)))
    return frame(body, "40%", t)


def unlock_logo(glyphs) -> str:
    """unlock.png, the boot/login logo: the cross and DEUS VULT in ANSI Shadow on transparency."""
    w, h = 800, 188
    px = 10
    rows = figlet("DEUS VULT", glyphs)
    cols = max(len(r) for r in rows)
    gap = 44
    size = (w - 13 * px - gap - 16) / (cols * 0.6)
    text_w = cols * 0.6 * size
    x0 = (w - (13 * px + gap + text_w)) / 2
    art, _ = figlet_block(rows, x0 + 13 * px + gap + text_w / 2, (h - len(rows) * 1.2 * size) / 2 - 0.25 * size,
                          size, f'fill="{GREEN}" filter="url(#logo-glow)"')
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">',
        "<!-- Made with omarchy-deus-vult-theme tools/make-backgrounds.py -->",
        '<defs><filter id="logo-glow" x="-10%" y="-30%" width="120%" height="160%">'
        '<feGaussianBlur stdDeviation="3" result="b"/>'
        '<feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter></defs>',
        *cross(x0, (h - 13 * px) / 2, px, GREEN, 'filter="url(#logo-glow)"'),
        *art,
        "</svg>",
    ]
    return "\n".join(out) + "\n"


# name: (file under the repo root, drawing, seconds of video or None for a still).
# An intro in backgrounds/intros/ plays when its namesake still becomes the
# background (Omarchy 4.5) and ends on it; a video in backgrounds/ is itself a
# background, looped.
TARGETS = {
    "1-cross": ("backgrounds/1-cross.png", variant_cross, None),
    "2-every-square-pixel": ("backgrounds/2-every-square-pixel.png", variant_motto, None),
    "3-boot": ("backgrounds/3-boot.png", variant_boot, None),
    "4-live-cross": ("backgrounds/4-live-cross.mp4", variant_live, LIVE_LOOP),
    "intro-1-cross": ("backgrounds/intros/1-cross.mp4", variant_cross, 6.0),
    "intro-2-every-square-pixel": ("backgrounds/intros/2-every-square-pixel.mp4", variant_motto, 6.0),
    "intro-3-boot": ("backgrounds/intros/3-boot.mp4", variant_boot, 6.5),
    "unlock": ("unlock.png", unlock_logo, None),
}
FPS = 24
VIDEO_W, VIDEO_H = 2560, 1440  # what Omarchy's stock intros use, and OWE's largest decode


def render(svg: Path, png: Path) -> None:
    rendered = subprocess.run(["rsvg-convert", str(svg)], check=True, capture_output=True).stdout
    subprocess.run(
        ["magick", "-", "-strip", "-define", "png:compression-level=9", str(png)], input=rendered, check=True
    )


def raster(svg: str) -> bytes:
    return subprocess.run(
        ["rsvg-convert", "-w", str(VIDEO_W), "-h", str(VIDEO_H), "-"], input=svg.encode(), check=True, capture_output=True
    ).stdout


def render_video(draw, glyphs, seconds: float, mp4: Path) -> None:
    """Every frame drawn and rasterised in parallel, piped in order to x264."""
    count = round(seconds * FPS)
    enc = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-y", "-f", "image2pipe", "-framerate", str(FPS), "-c:v", "png", "-i", "-",
         "-c:v", "libx264", "-preset", "slow", "-crf", "18", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
         "-an", str(mp4)],
        stdin=subprocess.PIPE,
    )
    with ThreadPoolExecutor(os.cpu_count()) as pool:
        for start in range(0, count, 48):  # a chunk at a time keeps memory flat
            for png in pool.map(lambda i: raster(draw(glyphs, i / FPS)), range(start, min(start + 48, count))):
                enc.stdin.write(png)
    enc.stdin.close()
    if enc.wait():
        sys.exit(f"make-backgrounds: ffmpeg failed on {mp4}")


def make(key: str, dest: Path, only=None, svg_dir: Path | None = None, at: float | None = None) -> None:
    """Draw phosphor `key`'s targets (all, or `only`) into the theme folder dest."""
    for tool in ("rsvg-convert", "magick", "ffmpeg"):
        if not shutil.which(tool):
            sys.exit(f"make-backgrounds: needs {tool}")
    use(key)
    glyphs = load_flf(Path(__file__).with_name("ansi-shadow.flf"))
    with tempfile.TemporaryDirectory() as tmp:
        svg_dir = svg_dir or Path(tmp)
        svg_dir.mkdir(parents=True, exist_ok=True)
        for name in only or TARGETS:
            path, draw, seconds = TARGETS[name]
            if seconds is not None and at is not None:
                (svg_dir / f"{name}@{at:g}.png").write_bytes(raster(draw(glyphs, at)))
                continue
            out = dest / path
            out.parent.mkdir(parents=True, exist_ok=True)
            if seconds is None:
                svg = svg_dir / f"{name}.svg"
                svg.write_text(draw(glyphs), encoding="utf-8")
                render(svg, out)
            else:
                render_video(draw, glyphs, seconds, out)
            print(f"make-backgrounds: {out}")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("phosphor", choices=PHOSPHORS)
    p.add_argument("--out", type=Path, help="theme folder, default build/deus-vult-<phosphor>")
    p.add_argument("--only", choices=TARGETS, action="append", help="render only this one (repeatable)")
    p.add_argument("--svg", type=Path, help="also keep the SVGs (of stills) in this directory")
    p.add_argument("--at", type=float, metavar="SECONDS",
                   help="instead of the videos, write their frame at this time as PNGs into --svg's directory")
    a = p.parse_args()
    if a.at is not None and not a.svg:
        p.error("--at needs --svg DIR")
    make(a.phosphor, a.out or ROOT / "build" / f"deus-vult-{a.phosphor}", a.only, a.svg, a.at)


if __name__ == "__main__":
    main()
