"""Turns captured screenshots into the page's WebP images, and regenerates the icons from Lumi's app icon.
The hero stills and the Open Graph image come from tools/capture/build_stills.py instead.

usage:
  python tools/images.py shot <name> <dark.png> <light.png> [--crop=x0,y0,x1,y1]
                                          writes site/assets/img/<name>-<theme>-<width>.webp for each width
  python tools/images.py icons <lumi_repo>
                                          writes site/assets/icons/* from Lumi's src/Lumi/Assets/lumi-icon.png

Captures come from a Debug Lumi in an isolated profile, as tools/capture/README.md describes: the desktop window's
client area at 1980x1290 (Lumi's UI scale 150% on a 100% monitor), captured with tools/capture/snap_window.py.
SHOTS holds each image's crop in such a capture and its widths. Keep the widths: index.html's srcset lists them.
Pass --crop when the part to keep sits elsewhere in a new capture (always for the phone: its crop depends on the
design preview's window size).
"""
import sys
from pathlib import Path

from PIL import Image

SITE = Path(__file__).resolve().parents[1] / "site"
SHOTS = {
    # name: (crop box in the capture, output widths)
    "work": ((432, 66, 1950, 950), (1518, 1012, 760)),          # chat area of a run with its steps open
    "files": ((432, 66, 1950, 944), (1518, 1012, 760)),         # chat area of the expenses chat
    "customize": ((0, 40, 1980, 1290), (1980, 1320, 880)),      # Customize > Skills, without the title bar
    "accounts": ((487, 165, 1494, 1125), (1007, 672)),          # the Add an AI account dialog
    "phone": ((164, 288, 656, 1353), (492, 328)),               # the phone screen in the 820x1479 design preview window
}


def shot(name, dark, light, crop=None):
    crop, widths = crop or SHOTS[name][0], SHOTS[name][1]
    for theme, source in (("dark", dark), ("light", light)):
        im = Image.open(source).convert("RGB").crop(crop)
        if im.width < max(widths):
            # The page's srcset names these widths, so a smaller capture is scaled up (a capture at a higher
            # display scaling is sharper).
            print(f"note: the {theme} crop is {im.width} px wide; scaled up to {max(widths)}")
        for w in widths:
            out = im if w == im.width else im.resize((w, round(im.height * w / im.width)), Image.LANCZOS)
            path = SITE / "assets" / "img" / f"{name}-{theme}-{out.width}.webp"
            out.save(path, "WEBP", quality=88, method=6)
            print(f"{path.name} {out.width}x{out.height} {path.stat().st_size // 1024} KB")


def icons(lumi_repo):
    target = SITE / "assets" / "icons"
    src = Image.open(Path(lumi_repo) / "src" / "Lumi" / "Assets" / "lumi-icon.png").convert("RGBA")
    src.save(target / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)])
    for size, name in ((192, "icon-192.png"), (512, "icon-512.png"), (32, "favicon-32.png")):
        src.resize((size, size), Image.LANCZOS).save(target / name, optimize=True)
    # iOS fills transparency with black and applies its own mask, so the touch icon gets an opaque backdrop.
    touch = Image.new("RGBA", (180, 180), (14, 14, 18, 255))
    touch.alpha_composite(src.resize((180, 180), Image.LANCZOS))
    touch.convert("RGB").save(target / "apple-touch-icon.png", optimize=True)
    for size in (64, 128, 256):
        src.resize((size, size), Image.LANCZOS).save(target / f"lumi-mark-{size}.webp", "WEBP", quality=92, method=6)
    print(", ".join(sorted(p.name for p in target.iterdir())))


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--crop=")]
    crop = next((tuple(int(v) for v in a[7:].split(",")) for a in sys.argv[1:] if a.startswith("--crop=")), None)
    if len(args) >= 4 and args[0] == "shot" and args[1] in SHOTS:
        shot(args[1], args[2], args[3], crop)
    elif len(args) >= 2 and args[0] == "icons":
        icons(args[1])
    else:
        sys.exit(__doc__)
