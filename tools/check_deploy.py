"""Checks a deployed copy of the site against the local site/ folder: every file is served and identical,
security headers, content types, caching, compression and range requests, that nothing outside site/ is
served, and (for letlumi.com) that www and http redirect to https://letlumi.com.

usage: python tools/check_deploy.py [base_url]     (default https://letlumi.com; or the preview address)
Exit code 1 when anything is wrong.
"""
import hashlib, json, pathlib, sys, urllib.error, urllib.request

base = (sys.argv[1] if len(sys.argv) > 1 else "https://letlumi.com").rstrip("/")
site = pathlib.Path(__file__).resolve().parents[1] / "site"
config = json.loads((site / "staticwebapp.config.json").read_text(encoding="utf-8"))
expected_global = config["globalHeaders"]
mime = {".html": "text/html", ".css": "text/css", ".js": "javascript", ".svg": "image/svg+xml",
        ".png": "image/png", ".ico": "image/", ".txt": "text/plain", **config["mimeTypes"]}


def fetch(path, headers=None, method="GET"):
    req = urllib.request.Request(base + path, headers=headers or {}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, {k.lower(): v for k, v in r.headers.items()}, r.read()
    except urllib.error.HTTPError as e:
        return e.code, {k.lower(): v for k, v in e.headers.items()}, e.read()


problems, served = [], 0
for f in sorted(p for p in site.rglob("*") if p.is_file()):
    rel = "/" + f.relative_to(site).as_posix()
    if f.name == "staticwebapp.config.json":
        continue
    status, h, body = fetch(rel)
    served += 1
    if status != 200:
        problems.append(f"{rel}: HTTP {status}")
        continue
    local = f.read_bytes()
    if f.suffix in (".txt", ".webmanifest", ".html", ".css", ".js", ".svg", ".json"):
        body, local = body.replace(b"\r\n", b"\n"), local.replace(b"\r\n", b"\n")
    if hashlib.sha256(body).digest() != hashlib.sha256(local).digest():
        problems.append(f"{rel}: content differs from local file ({len(body)} vs {len(local)} bytes)")
    want = mime.get(f.suffix.lower())
    if want and want not in h.get("content-type", ""):
        problems.append(f"{rel}: content-type {h.get('content-type')!r}, expected {want!r}")
    for k, v in expected_global.items():
        if h.get(k.lower()) != v:
            problems.append(f"{rel}: header {k} = {h.get(k.lower())!r}")
    cc = h.get("cache-control", "")
    if rel.startswith("/assets/") and "max-age=86400" not in cc:
        problems.append(f"{rel}: cache-control {cc!r}, expected max-age=86400")
    elif f.suffix in (".css", ".js") and not rel.startswith("/assets/") and "max-age=3600" not in cc:
        problems.append(f"{rel}: cache-control {cc!r}, expected max-age=3600")

status, h, body = fetch("/")
print(f"/ -> {status} {h.get('content-type')} | {len(body)} bytes | cache-control: {h.get('cache-control')!r}")
for k in expected_global:
    print(f"  {k}: {'OK' if h.get(k.lower()) == expected_global[k] else 'MISSING/DIFFERENT -> ' + repr(h.get(k.lower()))}")
for k in ("strict-transport-security", "x-frame-options", "server", "x-powered-by"):
    if k in h:
        print(f"  (also) {k}: {h[k]}")

for path, enc in (("/", "br"), ("/styles.css", "br"), ("/main.js", "gzip")):
    _, h, _ = fetch(path, {"Accept-Encoding": enc})
    print(f"compression {path} ({enc} requested): {h.get('content-encoding', 'none')}")

video = "/assets/video/hero-dark-1980.webm"
status, h, body = fetch(video, {"Range": "bytes=0-1023"})
print(f"range {video}: HTTP {status} | {h.get('content-range')} | {len(body)} bytes | accept-ranges: {h.get('accept-ranges')}")

for path, want in (("/staticwebapp.config.json", 404), ("/DEPLOY.md", 404), ("/README.md", 404), ("/AGENTS.md", 404),
                   ("/.github/workflows/website.yml", 404), ("/tools/check_deploy.py", 404)):
    status, _, _ = fetch(path)
    if status != want:
        problems.append(f"{path}: HTTP {status}, expected {want}")
    print(f"not deployed {path}: HTTP {status}")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


if base == "https://letlumi.com":
    opener = urllib.request.build_opener(NoRedirect)
    for source in ("https://www.letlumi.com/", "http://letlumi.com/", "http://www.letlumi.com/"):
        try:
            r = opener.open(source, timeout=30)
            code, location = r.status, r.headers.get("Location")
        except urllib.error.HTTPError as e:
            code, location = e.code, e.headers.get("Location")
        print(f"redirect {source} -> {code} {location}")
        if code not in (301, 302, 307, 308) or not (location or "").startswith(("https://letlumi.com/", "https://www.letlumi.com/")):
            problems.append(f"{source}: expected a redirect to https://letlumi.com, got {code} {location}")

print(f"files checked: {served} | problems: {len(problems)}")
for p in problems:
    print("  PROBLEM", p)
sys.exit(1 if problems else 0)
