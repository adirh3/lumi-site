# Lumi website

The public one-page site for [Lumi](https://github.com/adirh3/Lumi), live at <https://letlumi.com>: static files in
[`site/`](site), with no build step, framework, cookies, analytics or third-party requests.

- **Preview it locally:** `python -m http.server 8781 --bind 127.0.0.1 --directory site`, then open
  <http://127.0.0.1:8781>. `python tools/validate.py` checks it in Edge, with axe for accessibility
  (`pip install -r tools/requirements.txt` first).
- **Deploy:** Actions → **Website** → Run workflow. It runs only when `adirh3` starts it from `main`,
  and waits for approval before deploying. [DEPLOY.md](DEPLOY.md) covers hosting, the workflow,
  the domain and launch checks.
- **Working on it:** [AGENTS.md](AGENTS.md) has the content rules, the checks to run before pushing and
  deploying, and how screenshots and the hero loop are captured ([tools/capture](tools/capture/README.md)).
