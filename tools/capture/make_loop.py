"""Builds the hero loop's frames from a recorded Lumi run plus a separate clip of three wheel gestures over
the finished answer: A (bottom -> chart), B1 (chart -> diagram), B2 (diagram -> bottom).

The loop opens on the chart (the still image is that frame), scrolls to the diagram and the checklist,
dissolves to the empty chat, replays the typing at ~1.9x, the work with idle waits squeezed, the answer
streaming in, then scrolls back up to the chart. The Debug window title is painted over.

usage: python tools/capture/make_loop.py <frames_dir> <out_dir> <send_ms> <answer_ms> <done_ms>
                                 --gestures=<dir> [--gesture-speed=1.6] [--preview]
  send_ms   the moment the prompt was sent (main take)
  answer_ms the final answer starts streaming
  done_ms   the answer has finished
  The gestures clip starts on the same idle, finished answer.
"""
import shutil
import sys
from pathlib import Path

import numpy as np
from PIL import Image

FPS = 30
TITLE_BOX = (0, 0, 430, 56)


def option(name, default=None):
    return next((a.split("=", 1)[1] for a in sys.argv if a.startswith(f"--{name}=")), default)


src_dir = Path(sys.argv[1])
out_dir = Path(sys.argv[2])
send_ms, answer_ms, done_ms = (int(v) for v in sys.argv[3:6])
gesture_dir = Path(option("gestures"))
GESTURE_SPEED = float(option("gesture-speed", "1.0"))
preview = "--preview" in sys.argv


def read_frames(directory):
    out, small_map = [], {}
    for p in sorted(directory.glob("*.jpg"), key=lambda p: int(p.stem)):
        im = Image.open(p)
        im.draft("L", (495, 323))  # decode at a quarter of the size; only motion is measured here
        small = np.asarray(im.convert("L").resize((330, 215)), dtype=np.int16)
        if small.mean() >= 2:
            out.append((int(p.stem), p))
            small_map[int(p.stem)] = small
    return out, small_map, np.array([t for t, _ in out])


SOURCES = {"m": read_frames(src_dir), "g": read_frames(gesture_dir)}
frames = SOURCES["m"][0]


def nearest(ms, src="m"):
    fr, _, st = SOURCES[src]
    return fr[int(np.abs(st - ms).argmin())][1]


def load(path):
    im = Image.open(path).convert("RGB")
    if im.size != (1980, 1290):
        # A take whose window was briefly a pixel wider keeps a sliver of frame at the right edge.
        im = im.crop((0, 0, 1980, 1290))
    strip = im.getpixel((700, 8))
    im.paste(strip, TITLE_BOX)
    return im


def bursts(t0, t1, threshold=0.35, gap=600, pad=(150, 250), src="m"):
    fr, sm, _ = SOURCES[src]
    active, prev = [], None
    for t, _ in fr:
        if t0 <= t <= t1:
            g = sm[t]
            if prev is not None and np.abs(g - prev).mean() > threshold:
                active.append(t)
            prev = g
    spans = []
    for t in active:
        a, b = t - pad[0], t + pad[1]
        if spans and a <= spans[-1][1] + gap:
            spans[-1][1] = max(spans[-1][1], b)
        else:
            spans.append([a, b])
    return spans


# Typing: composer changes before the send.
composer, prev = [], None
for t, p in frames:
    if t >= send_ms - 300:
        break
    c = np.asarray(Image.open(p).convert("L").crop((560, 1090, 1860, 1150)), dtype=np.int16)
    if prev is not None and np.abs(c - prev).mean() > 0.25:
        composer.append(t)
    prev = c
type_start, type_end = composer[0], composer[-1]


# Follow-up chips: first change in the chip row after the answer is done, then the moment the chips'
# text has arrived (the row matches the gestures clip, which starts on the same idle answer).
def row(t, src="m"):
    return np.asarray(Image.open(nearest(t, src)).convert("L").crop((540, 950, 1860, 1000)), dtype=np.int16)


base = row(done_ms - 300)
chips_ms = None
for t, _ in frames:
    if done_ms - 200 < t < done_ms + 8000 and np.abs(row(t) - base).mean() > 3.0:
        chips_ms = t
        break

# The three gestures in the gestures clip.
g_last = int(SOURCES["g"][2][-1])
gestures = [g for g in bursts(0, g_last, threshold=0.6, gap=500, pad=(60, 120), src="g") if g[1] - g[0] > 500]
if len(gestures) < 3:
    sys.exit(f"expected 3 gestures in {gesture_dir}, found {gestures}")
(a0, a1), (b10, b11), (b20, b21) = gestures[:3]
rest_ms = a1 + 900

ref_row = row(a0 - 300, "g")
ready_ms = None
for t, _ in frames:
    if t > (chips_ms or done_ms) and np.abs(row(t) - ref_row).mean() < 1.0:
        ready_ms = t
        break
if ready_ms is None:
    sys.exit("the main take never reaches the gestures clip's starting state")

WORK_SPEED, IDLE_CAP, TYPE_SPEED = 2.4, 0.2, 2.1

# Work bursts between the send and the answer.
work = bursts(send_ms - 100, answer_ms + 200)

timeline = [
    ("hold", rest_ms, 2.4, "g"),
    ("play", b10, b11, GESTURE_SPEED, "g"),
    ("hold", b11 + 700, 1.7, "g"),
    ("play", b20, b21, GESTURE_SPEED, "g"),
    ("hold", b21 + 700, 1.3, "g"),
    ("fade", b21 + 700, type_start - 700, 0.6, "g", "m"),
    ("hold", type_start - 700, 0.35, "m"),
    ("play", type_start - 40, type_end + 120, TYPE_SPEED, "m"),
    ("hold", type_end + 300, 0.4, "m"),
]
cursor = send_ms - 60
for a, b in work:
    if b <= cursor:
        continue
    if a > cursor:
        timeline.append(("play", cursor, a, max(1.0, (a - cursor) / 1000 / IDLE_CAP), "m"))
    timeline.append(("play", max(a, cursor), b, WORK_SPEED, "m"))
    cursor = b
if answer_ms > cursor:
    timeline.append(("play", cursor, answer_ms, max(1.0, (answer_ms - cursor) / 1000 / IDLE_CAP), "m"))
    cursor = answer_ms
stream_seconds = (done_ms - cursor) / 1000
stream_speed = max(1.6, stream_seconds / 6.0)
timeline.append(("play", cursor, done_ms, stream_speed, "m"))
timeline.append(("hold", done_ms + 300, 0.5, "m"))
# The chips load (placeholders), squeezed, then their text arrives at real speed.
settle_from = ready_ms - 900
if settle_from > done_ms + 300:
    timeline.append(("play", done_ms + 300, settle_from, max(1.0, (settle_from - done_ms - 300) / 1000 / 0.5), "m"))
timeline.append(("play", max(settle_from, done_ms + 300), ready_ms + 200, 1.0, "m"))
timeline.append(("hold", a0 - 300, 0.4, "g"))
timeline.append(("play", a0 - 60, a1 + 120, GESTURE_SPEED, "g"))
timeline.append(("hold", rest_ms, 0.4, "g"))

if out_dir.exists():
    shutil.rmtree(out_dir)
out_dir.mkdir(parents=True)

count = 0
cache = {}


def frame_at(ms, src="m"):
    path = nearest(ms, src)
    if path not in cache:
        if len(cache) > 6:
            cache.clear()
        cache[path] = load(path)
    return cache[path]


def emit(im):
    global count
    count += 1
    if not preview:
        im.save(out_dir / f"{count:05d}.jpg", quality=95, subsampling=0)


for seg in timeline:
    kind = seg[0]
    if kind == "hold":
        _, ms, seconds, src = seg
        for _ in range(round(seconds * FPS)):
            emit(frame_at(ms, src))
    elif kind == "play":
        _, a, b, speed, src = seg
        n = max(1, round((b - a) / 1000 / speed * FPS))
        for i in range(n):
            emit(frame_at(a + (b - a) * i / n, src))
    elif kind == "fade":
        _, a, b, seconds, src_a, src_b = seg
        n = round(seconds * FPS)
        ia, ib = frame_at(a, src_a).copy(), frame_at(b, src_b).copy()
        for i in range(n):
            x = (i + 1) / (n + 1)
            x = x * x * (3 - 2 * x)
            emit(Image.blend(ia, ib, x))

print(f"typing {type_start}-{type_end} ms, chips at {chips_ms} ms, ready at {ready_ms} ms, {len(work)} work bursts")
print(f"gestures A {a0}-{a1}, B1 {b10}-{b11}, B2 {b20}-{b21}; rest frame {rest_ms} ms (gestures clip)")
print(f"stream {stream_seconds:.1f} s at {stream_speed:.2f}x")
print(f"{count} frames = {count / FPS:.1f} s at {FPS} fps -> {out_dir}")
if preview:
    marks = {"rest": (rest_ms, "g"), "diagram": (b11 + 700, "g"), "bottom": (b21 + 700, "g"),
             "g-start": (a0 - 300, "g"), "empty": (type_start - 700, "m"), "typed": (type_end + 300, "m"),
             "streaming": ((answer_ms + done_ms) // 2, "m"), "done": (done_ms + 300, "m"),
             "m-after-chips": ((chips_ms or done_ms) + 2500, "m")}
    for name, (ms, src) in marks.items():
        load(nearest(ms, src)).resize((990, 645)).save(out_dir / f"preview-{name}.png")
