"""Rebuilds the hero stills (the loops' first frames) and the Open Graph image from the hero loop frames.

usage: python tools/capture/build_stills.py <dark_loop_dir> <light_loop_dir> <lumi_repo>
  *_loop_dir  frame folders written by make_loop.py (00001.jpg is the still)
  lumi_repo   a checkout of adirh3/Lumi, for the Inter fonts and the app icon
       python tools/capture/build_stills.py --og-only <lumi_repo>
  --og-only   rebuild only the social image, using the existing 1980-wide dark hero still
"""
import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
parser.add_argument("dark_loop_dir", type=Path, nargs="?")
parser.add_argument("light_loop_dir", type=Path, nargs="?")
parser.add_argument("lumi_repo", type=Path, nargs="?")
parser.add_argument("--og-only", type=Path, metavar="lumi_repo", help="rebuild only the social image from the saved hero still")
args = parser.parse_args()
paths = (args.dark_loop_dir, args.light_loop_dir, args.lumi_repo)
if args.og_only:
    if any(paths):
        parser.error("--og-only cannot be combined with loop folders or a positional lumi_repo")
elif not all(paths):
    parser.error("provide dark_loop_dir, light_loop_dir and lumi_repo, or --og-only lumi_repo")

REPO = args.og_only or args.lumi_repo
SITE = Path(__file__).resolve().parents[2] / "site"
IMG = SITE / "assets" / "img"
LOOPS = {"dark": args.dark_loop_dir, "light": args.light_loop_dir}


def rounded(im, radius):
    mask = Image.new("L", im.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, im.width - 1, im.height - 1), radius, fill=255)
    out = im.convert("RGBA")
    out.putalpha(mask)
    return out


def glow(canvas, center, radius, color, alpha):
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    cx, cy = center
    d.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), fill=color + (alpha,))
    layer = layer.filter(ImageFilter.GaussianBlur(radius * 0.45))
    canvas.alpha_composite(layer)


def build_stills():
    report = []
    for theme, loop in LOOPS.items():
        frame = Image.open(loop / "00001.jpg").convert("RGB")
        for w in (1980, 1320, 880):
            out = frame if w >= frame.width else frame.resize((w, round(frame.height * w / frame.width)), Image.LANCZOS)
            path = IMG / f"hero-{theme}-{out.width}.webp"
            out.save(path, "WEBP", quality=88, method=6)
            report.append(f"{path.name} {out.width}x{out.height} {path.stat().st_size // 1024} KB")
    return report


def build_og():
    W, H = 1280, 640
    fonts = REPO / "src" / "Lumi.Mobile" / "Assets" / "Fonts"
    bold = ImageFont.truetype(str(fonts / "Inter-Bold.ttf"), 92)
    semi = ImageFont.truetype(str(fonts / "Inter-SemiBold.ttf"), 23)
    body = ImageFont.truetype(str(fonts / "Inter-Regular.ttf"), 31)

    canvas = Image.new("RGBA", (W, H), (14, 14, 18, 255))
    glow(canvas, (180, 120), 360, (99, 102, 241), 120)
    glow(canvas, (1040, 600), 420, (167, 139, 250), 95)
    glow(canvas, (760, 660), 300, (244, 114, 182), 60)

    # The chat area of the loop's first frame: the header, the answer and its chart.
    source = IMG / "hero-dark-1980.webp" if args.og_only else LOOPS["dark"] / "00001.jpg"
    frame = Image.open(source).convert("RGB")
    shot = frame.crop((436, 64, 1966, 872))
    shot = shot.resize((700, round(shot.height * 700 / shot.width)), Image.LANCZOS)
    shot = rounded(shot, 20)
    shadow = Image.new("RGBA", (shot.width + 120, shot.height + 120), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle((60, 70, 60 + shot.width, 70 + shot.height), 26, fill=(0, 0, 0, 170))
    shadow = shadow.filter(ImageFilter.GaussianBlur(28))
    sx, sy = 540, (H - shot.height) // 2
    canvas.alpha_composite(shadow, (sx - 60, sy - 60))
    canvas.alpha_composite(shot, (sx, sy))
    ImageDraw.Draw(canvas).rounded_rectangle((sx, sy, sx + shot.width - 1, sy + shot.height - 1), 20,
                                             outline=(255, 255, 255, 40), width=2)

    icon = Image.open(REPO / "src" / "Lumi" / "Assets" / "lumi-icon.png").convert("RGBA").resize((104, 104), Image.LANCZOS)
    canvas.alpha_composite(icon, (72, 120))
    d = ImageDraw.Draw(canvas)
    d.text((70, 236), "Lumi", font=bold, fill=(244, 244, 247, 255))
    # The tagline, as large as fits the column left of the screenshot.
    size = 38
    while ImageFont.truetype(str(fonts / "Inter-SemiBold.ttf"), size).getlength("Let Lumi do the work.") > sx - 74 - 34:
        size -= 1
    tagline = ImageFont.truetype(str(fonts / "Inter-SemiBold.ttf"), size)
    d.text((74, 356), "Let Lumi do the work.", font=tagline, fill=(244, 244, 247, 255))
    small = ImageFont.truetype(str(fonts / "Inter-Regular.ttf"), 27)
    y = 410
    for line in ("The open-source agent", "for your desktop.", "It works with the AI", "you already have."):
        d.text((74, y), line, font=small, fill=(200, 200, 214, 255))
        y += 32
    d.text((74, 548), "Windows  ·  macOS  ·  Linux", font=semi, fill=(165, 180, 252, 255))

    og = canvas.convert("RGB")
    out = SITE / "assets" / "og" / "lumi-og.png"
    og.save(out, "PNG", optimize=True)
    return f"{out.name} {og.width}x{og.height} {out.stat().st_size // 1024} KB"


if __name__ == "__main__":
    if not args.og_only:
        for line in build_stills():
            print(line)
    print(build_og())
