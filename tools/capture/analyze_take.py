"""Maps chat timestamps onto a recording's clock and finds when the answer stopped changing.
usage: python tools/capture/analyze_take.py <frames_dir> <send_epoch_ms> <answer_epoch_ms>"""
import os, sys
from pathlib import Path
import numpy as np
from PIL import Image
d = Path(sys.argv[1]); send_epoch, answer_epoch = int(sys.argv[2]), int(sys.argv[3])
frames = sorted(((int(p.stem), p) for p in d.glob("*.jpg")), key=lambda x: x[0])
start = min(os.path.getmtime(p) * 1000 - t for t, p in frames[:80])
send_ms, answer_ms = round(send_epoch - start), round(answer_epoch - start)
print(f"{len(frames)} frames, last {frames[-1][0]} ms | send_ms {send_ms} | answer_ms {answer_ms}")
def gray(p, box):
    im = Image.open(p); im.draft("L", (990, 645))
    return np.asarray(im.convert("L").resize((990, 645)).crop(box), dtype=np.int16)
# transcript area and chip row, in half-size coordinates
TRANSCRIPT, CHIPS = (260, 50, 930, 465), (270, 475, 930, 500)
prev = None; act = []
for t, p in frames:
    if t < answer_ms - 2000:
        continue
    g = gray(p, TRANSCRIPT); c = gray(p, CHIPS)
    if prev is not None:
        act.append((t, float(np.abs(g - prev[0]).mean()), float(np.abs(c - prev[1]).mean())))
    prev = (g, c)
# last transcript activity before a 3 s quiet stretch
done_ms = None
for i, (t, a, _) in enumerate(act):
    if a > 0.4:
        later = [x for x in act[i + 1:] if x[0] <= t + 3000]
        if later and all(x[1] <= 0.4 for x in later) and later[-1][0] >= t + 2500:
            done_ms = t; break
print("done_ms (transcript quiet for 3 s after):", done_ms)
chips = next((t for t, _, c in act if done_ms and t > done_ms - 500 and c > 3.0), None)
print("first chip-row change after done:", chips)
# activity summary per second around the end
buckets = {}
for t, a, c in act:
    k = t // 1000
    buckets.setdefault(k, [0, 0])
    buckets[k][0] = max(buckets[k][0], a); buckets[k][1] = max(buckets[k][1], c)
print("per-second max diff (transcript/chips):", " ".join(f"{k}s:{v[0]:.1f}/{v[1]:.1f}" for k, v in sorted(buckets.items())))
