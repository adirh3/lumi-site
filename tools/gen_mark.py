"""Draws Lumi's icon as the hero's inline, animatable SVG (the <svg class="hero-mark lumi-mark"> in index.html) and
writes it into site/index.html. It copies the geometry and colours of Lumi's src/Lumi/Services/AppIconArt.cs: the
squircle tile, Lumi's sparkle, your sparkle and the model dot, with their gradients and shadows. The groups are
nested so styles.css can move each part the way Lumi's loading window does.

usage: python tools/gen_mark.py
If Lumi's icon changes, update the constants below from AppIconArt.cs, run this, then regenerate the PNG icons
(python tools/images.py icons <lumi_repo>) and the social image (tools/capture/build_stills.py).
"""
import math
import re
import sys
from pathlib import Path

U = 1024.0
HARMONICS = [0.9076039046, 0.0961679041, -0.0040758391, 0.0003167373, -0.0000127069]
LUMI, LUMI_TIP = (503.81, 520.19), 350.0
YOU, YOU_TIP = (709.09, 314.91), 132.0
MODEL, MODEL_R = (259.15, 764.85), 26.0


def signed_power(v, p):
    return math.copysign(abs(v) ** p, v)


def smooth(points):
    """A closed Catmull-Rom spline through the points, as SVG path data (same as AppIconArt.Smooth)."""
    n = len(points)
    f = lambda v: f"{v:.1f}".rstrip("0").rstrip(".")
    d = [f"M{f(points[0][0])} {f(points[0][1])}"]
    for i in range(n):
        p0, p1, p2, p3 = points[(i - 1) % n], points[i], points[(i + 1) % n], points[(i + 2) % n]
        c1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
        d.append(f"C{f(c1[0])} {f(c1[1])} {f(c2[0])} {f(c2[1])} {f(p2[0])} {f(p2[1])}")
    return "".join(d) + "Z"


def squircle():
    pts = []
    for i in range(64):
        a = 2 * math.pi * i / 64
        pts.append((U / 2 + U / 2 * signed_power(math.cos(a), 0.4), U / 2 + U / 2 * signed_power(math.sin(a), 0.4)))
    return smooth(pts)


def sparkle(centre, tip, count=96):
    pts = []
    for i in range(count):
        a = 2 * math.pi * i / count
        r = sum(h * math.cos(4 * k * a) for k, h in enumerate(HARMONICS)) * tip
        pts.append((centre[0] + r * math.cos(a), centre[1] + r * math.sin(a)))
    return smooth(pts)


SHADOW = "#2B1484"
TINT = "#EEE6FF"
YOU_FILL = "#E4CFFF"

lumi_d = sparkle(LUMI, LUMI_TIP)
you_d = sparkle(YOU, YOU_TIP)
mx, my = MODEL


def blur(fid, sd):
    return (f'<filter id="{fid}" filterUnits="userSpaceOnUse" x="-200" y="-200" width="1424" height="1424">'
            f'<feGaussianBlur stdDeviation="{sd}"/></filter>')


svg = f'''<svg class="hero-mark lumi-mark" data-lumi-mark viewBox="0 0 1024 1024" aria-hidden="true" focusable="false">
<defs>
<path id="lm-sq" d="{squircle()}"/><path id="lm-lp" d="{lumi_d}"/><path id="lm-yp" d="{you_d}"/>
<clipPath id="lm-clip"><use href="#lm-sq"/></clipPath>
<linearGradient id="lm-tile" gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="1024" y2="1024"><stop offset="0" stop-color="#5D5CF2"/><stop offset=".52" stop-color="#9C58F5"/><stop offset="1" stop-color="#D84DE8"/></linearGradient>
<radialGradient id="lm-sheen" gradientUnits="userSpaceOnUse" cx="190" cy="110" r="720"><stop offset="0" stop-color="#fff" stop-opacity=".2"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></radialGradient>
<radialGradient id="lm-depth" gradientUnits="userSpaceOnUse" cx="930" cy="1010" r="560"><stop offset="0" stop-color="#C026D3" stop-opacity=".22"/><stop offset="1" stop-color="#C026D3" stop-opacity="0"/></radialGradient>
<linearGradient id="lm-edge" gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="0" y2="1024"><stop offset="0" stop-color="#fff" stop-opacity=".32"/><stop offset=".3" stop-color="#fff" stop-opacity=".06"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>
<linearGradient id="lm-lumi" gradientUnits="userSpaceOnUse" x1="0" y1="{LUMI[1] - LUMI_TIP:.2f}" x2="0" y2="{LUMI[1] + LUMI_TIP:.2f}"><stop offset="0" stop-color="#fff"/><stop offset="1" stop-color="{TINT}"/></linearGradient>
<linearGradient id="lm-model" gradientUnits="userSpaceOnUse" x1="0" y1="{my - MODEL_R:.2f}" x2="0" y2="{my + MODEL_R:.2f}"><stop offset="0" stop-color="#fff"/><stop offset="1" stop-color="{TINT}"/></linearGradient>
{blur("lm-b26", 26)}{blur("lm-b6", 6)}{blur("lm-b8", 8)}{blur("lm-b30", 30)}
</defs>
<g class="lm-tile">
<g clip-path="url(#lm-clip)"><rect width="1024" height="1024" fill="url(#lm-tile)"/><rect width="1024" height="1024" fill="url(#lm-sheen)"/><rect width="1024" height="1024" fill="url(#lm-depth)"/></g>
<use href="#lm-sq" clip-path="url(#lm-clip)" fill="none" stroke="url(#lm-edge)" stroke-width="6"/>
</g>
<g clip-path="url(#lm-clip)">
<circle class="lm-ping" cx="{mx}" cy="{my}" r="64" fill="none" stroke="#fff" stroke-width="10" opacity="0"/>
<g class="lm-part lm-model"><g class="lm-spin"><g class="lm-loop"><g class="lm-radial">
<circle cx="{mx}" cy="{my + MODEL_R * 0.3:.2f}" r="{MODEL_R}" fill="{SHADOW}" fill-opacity=".32" filter="url(#lm-b6)"/>
<circle cx="{mx}" cy="{my}" r="{MODEL_R}" fill="url(#lm-model)"/>
</g></g></g></g>
<g class="lm-lumi"><g class="lm-swell">
<use href="#lm-lp" transform="translate(0 22)" fill="{SHADOW}" fill-opacity=".3" filter="url(#lm-b26)"/>
<use href="#lm-lp" fill="url(#lm-lumi)"/>
</g></g>
<g class="lm-part lm-you"><g class="lm-spin"><g class="lm-loop"><g class="lm-radial"><g class="lm-unspin"><g class="lm-unloop">
<use href="#lm-yp" transform="translate(0 8)" fill="{SHADOW}" fill-opacity=".12" filter="url(#lm-b8)"/>
<use href="#lm-yp" transform="translate(0 40)" fill="{SHADOW}" fill-opacity=".3" filter="url(#lm-b30)"/>
<use href="#lm-yp" fill="{YOU_FILL}"/>
</g></g></g></g></g></g>
</g>
</svg>'''

page = Path(__file__).resolve().parents[1] / "site" / "index.html"
with open(page, encoding="utf-8", newline="") as f:
    html = f.read()
pattern = re.compile(r'<svg class="hero-mark lumi-mark".*?</svg>', re.S)
if len(pattern.findall(html)) != 1:
    sys.exit(f"expected one <svg class=\"hero-mark lumi-mark\"> in {page}")
updated = pattern.sub(lambda _: svg, html)
if updated != html:
    with open(page, "w", encoding="utf-8", newline="") as f:
        f.write(updated)
print(f"{'updated' if updated != html else 'unchanged'}: {page.name}, {len(svg)} chars; "
      f"you offset from Lumi {YOU[0] - LUMI[0]:.2f},{YOU[1] - LUMI[1]:.2f}; model {MODEL[0] - LUMI[0]:.2f},{MODEL[1] - LUMI[1]:.2f}")
