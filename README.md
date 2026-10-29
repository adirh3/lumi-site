# Lumi website

The public one-page site for [Lumi](https://github.com/adirh3/Lumi): static files in [`site/`](site),
with no build step, framework, cookies, analytics or third-party requests.

- **Preview it locally:** `python -m http.server 8080 --directory site`, then open <http://localhost:8080>.
- **Deploy:** Actions → **Website** → Run workflow. It runs only when `adirh3` starts it from `main`,
  and waits for approval before deploying. [DEPLOY.md](DEPLOY.md) covers hosting, the workflow,
  the domain and launch checks.
