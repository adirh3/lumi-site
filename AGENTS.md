# Lumi website: guide for agents

The public one-page site for [Lumi](https://github.com/adirh3/Lumi), live at **https://letlumi.com**. Static
files in `site/` (no build step, framework, cookies, analytics or third-party requests), hosted on Azure Static Web
Apps and deployed by a manual GitHub workflow that only Adir can start. Adir is the only maintainer: work on `main`.

Read this first, then `DEPLOY.md` (hosting setup and history) and, to refresh screenshots or the hero loop,
`tools/capture/README.md`. Private specifics (the Azure subscription, local paths, the private-words list) are in the
Lumi project's instructions, never in this repo.

## Ground rules

- **Everything here is public**: the repo, its whole history and the Actions logs. Never commit secrets, Azure IDs,
  local paths, personal details or anything from Adir's real Lumi data. Scan before every push (below).
- **Ask before acting outside the repo**: posting or sharing the site, setting the GitHub repos' homepage, changing
  DNS, buying anything, or creating or changing Azure resources happen only when Adir asks in the current request.
- **Deploy to production only when Adir asks** for it ("deploy", "ship it"). Preview deploys when he asks to see a
  change on Azure. Approve a waiting deployment for him only when he says so (see Deploy).
- **Don't edit the Lumi app repo** from here. Read its README, docs and release notes to keep the copy accurate.

## Layout

```text
site/index.html               the whole page: hero, four features, AI accounts, downloads, FAQ, final call to action
site/robots.txt, sitemap.xml   crawl permissions and the canonical page list
site/styles.css               design tokens at the top (dark default, light via prefers-color-scheme), then sections
site/main.js                  download detection, the hero loop, the mark's motion, reveal-on-scroll, the top bar
site/staticwebapp.config.json CSP and security headers, caching, MIME types (Azure reads it; it isn't served)
site/assets/                  img/ (WebP screenshots), video/ (hero loop), og/ (social image), icons/
tools/                        checks (validate, check_deploy, scan_public), images.py, gen_mark.py, capture/
.github/workflows/website.yml the deploy workflow
```

- Homepage URL metadata and the `WebSite`/`SoftwareApplication` JSON-LD live in the **SITE URL** block at the top of
  `index.html`. Keep their address and the site's `alternateName` in sync with `robots.txt` and `sitemap.xml`.
  The sitemap lists only canonical pages, not section fragments, downloads or asset files. Only add `lastmod`
  when it reflects a real content change; structured data must match visible copy and never invent ratings.
- `main.js`: `TARGETS` (label, note and link per build) and `PLATFORM` (build → card) drive the Download button,
  the hero's platform links and the highlighted choice in each download card. The hero loop fetches its video once
  and plays it from a `blob:` URL, pauses off screen, and offers a Play button instead of autoplaying when the
  visitor prefers reduced motion, has Save-Data on or the browser blocks autoplay.
- The CSP allows only the site's own files (plus `blob:` media). Don't add fonts, scripts, embeds or analytics from
  elsewhere.

## Content rules

- Describe only what the **latest published** Lumi release ships, checked against Lumi's README, docs and release
  notes. Calm, confident and concise; no hype.
- No invented numbers, testimonials, logos, "first/only" claims or performance comparisons. No Microsoft affiliation
  or endorsement. Don't mention colleagues' use.
- Wording: the app is **Lumi** (never "LetLumi"). Define it as **"Lumi is the open-source agent for your desktop.
  It works with the AI you already have."** Use "agent", not "assistant" or "workspace", as the product category.
  The tagline is **"Let Lumi do the work."** (it matches letlumi.com).
- Cost honesty: Lumi is free and open source (MIT); the AI comes from the account the user connects (GitHub Copilot,
  a ChatGPT plan, API providers, local models), with that provider's plans, limits and charges. Never imply free AI.
- Approvals: Full access is the default, Ask first is available, and approval isn't a sandbox. The phone is a
  companion (the desktop stays on); Android app plus the mobile web app, no native iOS. macOS packages are unsigned
  and not notarized, with first-launch steps in Lumi's README (check before changing).
- Keep `alt` texts true to the images; the hero's describes both themes' answers.

## Downloads

Links follow the latest release: `https://github.com/adirh3/Lumi/releases/latest/download/<asset>` for
`Lumi-win-Setup.exe`, `Lumi-win-Portable.zip`, `Lumi-win-arm64-Setup.exe`, `Lumi-win-arm64-Portable.zip`,
`Lumi-osx-arm64-Setup.pkg`, `Lumi-osx-x64-Setup.pkg`, `Lumi.AppImage` and `Lumi-linux-arm64.AppImage`. Files with a
version in their name (the Android APK, the Linux portable archives) link to the latest release page. The names come
from Velopack's channels in Lumi's `.github/workflows/release.yml`. When Lumi's packages change, update the cards in
`index.html` and `TARGETS`/`PLATFORM` (and the detection, if needed) in `main.js` together, then check every link
returns 200 (`curl -sLr 0-0 -o NUL -w '%{http_code}' <url>`).

## Images and the hero

Every screenshot and the hero loop come from a Debug Lumi in an **isolated, seeded profile** (sample user "Alex",
sample projects), never Adir's real data; `tools/capture/README.md` has the whole procedure. `tools/images.py` turns
captures into the page's WebP sizes (its `SHOTS` table has each image's crop and widths, which the `srcset` in
`index.html` lists) and regenerates the icons; `tools/capture/build_stills.py` makes the hero stills and the social
image (`assets/og/lumi-og.png`). The animated mark at the top of the page is an inline SVG drawn by `tools/gen_mark.py`
from Lumi's icon geometry: if Lumi's icon changes, regenerate the mark, the icons and the social image. Run the scan
with `--ocr` after any media change.

## Work locally

```powershell
pip install -r tools/requirements.txt          # once; the browser checks use the installed Microsoft Edge
python -m http.server 8781 --bind 127.0.0.1 --directory site   # in the background; stop it by its PID when done
python tools/validate.py                        # or a URL; --shots saves screenshots to tools/.out/shots/
```

`validate.py` must pass: no console errors, failed requests, sideways scrolling or missing `alt`; the Download
button detects the platform; the hero loop plays in dark and light on desktop and phone; and axe finds no
accessibility violations. Also look at the change yourself (dark and light, 1440 px and 390 px wide; the download
grid at 1100 px too) and show Adir screenshots of visible changes. He can also look on his phone if you serve
`site/` on the Tailscale address in the project instructions.

## Before every push

```powershell
python tools/scan_public.py --private "<regex from the project instructions>"           # add --ocr when media changed
```

It searches the working tree and the whole history (and with `--ocr`, the text inside screenshots and video frames)
for credentials, Azure IDs, emails, IPs, local paths and the private words. To also look for the exact deployment
token, set `SWA_DEPLOYMENT_TOKEN` for that run only (piped from `az staticwebapp secrets list ... --query
properties.apiKey -o tsv`) and remove it afterwards. Fix anything it finds before pushing; once pushed, it's public.
Commits go straight to `main`; pushing doesn't deploy.

## Deploy

The **Website** workflow (`.github/workflows/website.yml`) runs only by hand, only in `adirh3/lumi-site`, only from
`main` and only when started by `adirh3`, and waits in the `website` environment for approval (required reviewer:
adirh3; the deployment token is that environment's secret). Runs queue one at a time.

```powershell
gh workflow run website.yml --repo adirh3/lumi-site --ref main -f target=preview      # or target=production
```

- **preview** goes to a separate address (unlisted, but public: it's in the run's log). **production** is
  https://letlumi.com; it refuses to run while `index.html` still has the placeholder site URL.
- **Approval**: Adir approves under the run's **Review deployments** (or in the GitHub app). If he asked you to
  approve, find the run's id and approve the waiting environment:
  ```powershell
  $envId = gh api repos/adirh3/lumi-site/environments/website --jq .id
  "{`"environment_ids`":[$envId],`"state`":`"approved`",`"comment`":`"Approved at Adir's request`"}" |
    gh api -X POST repos/adirh3/lumi-site/actions/runs/<run id>/pending_deployments --input -
  ```
- **Verify**: `python tools/check_deploy.py` (letlumi.com: files identical, headers, caching, nothing outside
  `site/` served, www/http redirects) or with the preview address, then `python tools/validate.py https://letlumi.com/`.

## Hosting

- Azure Static Web Apps, **Free** plan: app `swa-lumi-site`, resource group `rg-lumi-site`, East US 2. Free allows two
  custom domains (both used) and includes 100 GB of traffic a month per subscription, with no paid overage; the
  Standard plan (a monthly fee per app) adds overage. A visit's first load is about 1–2 MB.
- **letlumi.com** is registered at Porkbun, which also hosts its DNS: `ALIAS @` and `CNAME www` point at the app's
  `azurestaticapps.net` address, a `TXT @` holds Azure's validation code, and MX/SPF records belong to Porkbun's email
  forwarding. letlumi.com is the app's default domain, so www, http and the Azure address redirect to it ("Set
  default" exists only in the Azure portal).
- If the deployment token leaks: reset it (portal → the app → Manage deployment token), then set the `website`
  environment's secret again (`DEPLOY.md`, step 4.1).
