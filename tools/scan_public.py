"""Pre-push check that nothing private reaches the public site repo. It searches every text file in the working
tree and every version of every file in git history for credentials, Azure IDs, email addresses, IP addresses,
local paths and the private words you pass in; checks that images and videos carry no metadata beyond the
encoder; and with --ocr (Windows) reads the text inside every screenshot and hero video frame and searches it too.

usage: python tools/scan_public.py [--private REGEX] [--ocr]
  --private  case-insensitive regex of private words (people, places, usernames, machine names) to flag.
             Keep that list out of this repo: the Lumi project's instructions hold it.
  --ocr      also OCR images at least 800 px wide and the 1980-wide hero videos at 6 frames per second
             (Windows OCR through powershell.exe; takes a few minutes). Run it whenever images or videos change.
Exit code 1 when something needs a look. Public by design: the GitHub handle adirh3 in links and the deploy guard,
and the footer credit. To also look for the exact Azure deployment token, put it in SWA_DEPLOYMENT_TOKEN for the
run only (see AGENTS.md); it is never printed.
"""
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "tools" / ".out" / "scan"
ARGS = sys.argv[1:]
PRIVATE = ARGS[ARGS.index("--private") + 1] if "--private" in ARGS else None
OCR = "--ocr" in ARGS

TEXT_PATTERNS = {
    "GitHub token": r"gh[pousr]_[A-Za-z0-9]{20,}|github_pat_\w{20,}",
    "API key": r"\bsk-[A-Za-z0-9_-]{16,}|AKIA[0-9A-Z]{16}",
    "JWT": r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}",
    "private key": r"-----BEGIN [A-Z ]*PRIVATE KEY",
    "Azure key or SAS": r"AccountKey=|SharedAccessSignature|[?&]sig=[A-Za-z0-9%]{20,}",
    "quoted secret": r"(?i)\b(api[_-]?key|secret|password|passwd|token)\b\s*[:=]\s*['\"][^'\"\s]{12,}['\"]",
    "long opaque string": r"(?<![A-Za-z0-9_-])(?=[A-Za-z0-9_-]*\d)(?=[A-Za-z0-9_-]*[A-Za-z])[A-Za-z0-9_-]{48,}(?![A-Za-z0-9_-])",
    "GUID (subscription, tenant...)": r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b",
    "email": r"[A-Za-z0-9._%+-]+@(?!example\.(?:com|org|net)\b)[A-Za-z0-9.-]+\.[A-Za-z]{2,}",  # example.* is reserved
    "IPv4": r"(?<![\w.])(?<![A-Za-z]/)(?!127\.)(?:\d{1,3}\.){3}\d{1,3}(?!\w)(?!\.\d)",  # not loopback, nor versions like Chrome/131.0.0.0
    "Windows path": r"\b[A-Za-z]:\\[^\s'\"<>]*",
    "home folder": r"/(?:home|Users)/[A-Za-z0-9._-]+|\\(?i:users)\\[^\\\s]+",
}
OCR_PATTERNS = {  # OCR misreads zeros as "@", so no email pattern here
    "Windows path": r"(?i)(?<![a-z])[a-z]\s?:\s?[\\/][^\s]*|[A-Za-z0-9_.-]+\\[A-Za-z0-9_.-]+\\",
    "profile folder": r"(?i)users[\\/]|appdata|roaming|\.copilot|session-?state",
    "credential words": r"(?i)gh[pousr]_|github_pat|\bsk-[a-z0-9]|bearer ",
    "IPv4": r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b",
}
if PRIVATE:
    TEXT_PATTERNS["private word"] = OCR_PATTERNS["private word"] = "(?i)" + PRIVATE
MEDIA = (".png", ".webp", ".jpg", ".jpeg", ".gif", ".ico", ".webm", ".mp4")
BENIGN_TAGS = {"major_brand", "minor_version", "compatible_brands", "encoder", "handler_name", "vendor_id", "language", "duration"}


def git(*args, inp=None):
    return subprocess.run(["git", "-C", str(ROOT), *args], input=inp, capture_output=True, check=True).stdout


def blobs():
    """(name, bytes) for the working tree and every blob in history, each content once."""
    seen = set()
    for rel in git("ls-files", "-co", "--exclude-standard").decode().splitlines():
        path = ROOT / rel
        if path.is_file():
            data = path.read_bytes()
            seen.add(git("hash-object", "--stdin", inp=data).strip().decode())
            yield rel + " (working tree)", data
    names = {}
    for line in git("rev-list", "--all", "--objects").decode().splitlines():
        sha, _, path = line.partition(" ")
        if path:
            names.setdefault(sha, path)
    kinds = git("cat-file", "--batch-check", inp="\n".join(names).encode()).decode().splitlines()
    for line in kinds:
        sha, kind, _ = line.split()
        if kind == "blob" and sha not in seen:
            seen.add(sha)
            yield f"{names[sha]} (history {sha[:8]})", git("cat-file", "-p", sha)


def scan_text(label, text, patterns, hits):
    for name, pattern in patterns.items():
        for m in re.finditer(pattern, text):
            hits.append(f"[{name}] {label}: {m.group(0)[:100]}")


hits, media = [], []
token = os.environ.get("SWA_DEPLOYMENT_TOKEN", "").strip().encode()
for label, data in blobs():
    name = label.split(" (")[0].lower()
    if token and token in data:
        hits.append(f"[DEPLOYMENT TOKEN] {label}")
    if name.endswith(MEDIA):
        media.append((label, data))
        continue
    if name == "tools/scan_public.py":  # its own patterns would match themselves
        continue
    scan_text(label, data.decode("utf-8", "replace"), TEXT_PATTERNS, hits)

shutil.rmtree(OUT, ignore_errors=True)
(OUT / "media").mkdir(parents=True)
from PIL import Image  # noqa: E402

for i, (label, data) in enumerate(media):
    name = label.split(" (")[0]
    path = OUT / "media" / f"{i:03d}-{Path(name).name}"
    path.write_bytes(data)
    if path.suffix.lower() in (".webm", ".mp4"):
        probe = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format_tags:stream_tags", "-of", "json", str(path)],
                                          capture_output=True, text=True).stdout or "{}")
        tags = {k: v for t in [probe.get("format", {}).get("tags", {})] + [s.get("tags", {}) for s in probe.get("streams", [])] for k, v in t.items()}
        extra = {k: v for k, v in tags.items() if k.lower() not in BENIGN_TAGS}
    else:
        im = Image.open(path)
        extra = {k: str(v)[:60] for k, v in im.info.items() if k not in ("loop", "background", "duration", "timestamp", "transparency", "gamma", "dpi", "sizes")}
        if len(im.getexif()):
            extra["exif"] = f"{len(im.getexif())} tags"
    if extra:
        hits.append(f"[metadata] {label}: {extra}")

if OCR:
    ocr_in, ocr_out = OUT / "ocr-in", OUT / "ocr-out"
    ocr_in.mkdir()
    for path in sorted((OUT / "media").iterdir()):
        if path.suffix.lower() in (".webm", ".mp4"):
            if "-1980." in path.name and path.suffix.lower() == ".mp4":
                # The transcript area, enlarged, so the small step and command text reads well.
                subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-vf", "fps=6,crop=1600:1290:380:0,scale=2400:-1:flags=lanczos",
                                str(ocr_in / f"{path.stem}-%03d.png")], check=True)
        elif path.suffix.lower() != ".ico":
            im = Image.open(path)
            if im.width >= 800:
                im.convert("RGB").save(ocr_in / f"{path.stem}.png")
    shell = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
    print(subprocess.run([str(shell), "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ROOT / "tools" / "ocr.ps1"),
                          "-In", str(ocr_in), "-Out", str(ocr_out)], capture_output=True, text=True).stdout.strip())
    for txt in sorted(ocr_out.glob("*.txt")):
        scan_text(f"OCR {txt.stem}", txt.read_text(encoding="utf-8-sig"), OCR_PATTERNS, hits)

print(f"scanned text and {len(media)} media file version(s){' with OCR' if OCR else ''}; private words: {'yes' if PRIVATE else 'not given'}")
for line in sorted(set(hits)):
    print("  " + line)
print("nothing found" if not hits else f"{len(set(hits))} item(s) to look at")
sys.exit(1 if hits else 0)
