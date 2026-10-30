# Lumi website: deploying

The public one-page site for [Lumi](https://github.com/adirh3/Lumi). Static files only: no build step,
framework, cookies, analytics or third-party requests.

```text
README.md, DEPLOY.md, AGENTS.md, LICENSE
.github/workflows/website.yml   the manual deploy workflow (step 4)
tools/                          checks and capture tools (not deployed; see AGENTS.md)
site/                           everything that's deployed
  index.html                  the page (all copy and links)
  styles.css, main.js         design and the small amount of script (download button, hero loop, motion)
  staticwebapp.config.json    Azure Static Web Apps headers (CSP and security headers), caching, MIME types
  site.webmanifest, robots.txt
  assets/img/                 screenshots, WebP in dark and light at several widths
  assets/og/lumi-og.png       1280×640 social image (Open Graph, X, GitHub social preview)
  assets/icons/               favicon, touch icon, Lumi marks
  assets/video/               the hero's recorded run: dark and light, AV1 WebM and H.264 MP4, two sizes
```

Preview it locally from the repository root, then open <http://127.0.0.1:8781>:

```powershell
python -m http.server 8781 --bind 127.0.0.1 --directory site
```

## 1. Set the site URL

The site lives at `https://letlumi.com` (registered at Porkbun, which also hosts its DNS). The address
appears only in the **SITE URL** block at the top of `index.html` (canonical link, `og:url`, `og:image`,
`twitter:image`); social networks need those to be absolute. To move the site to another address,
replace it there, for example:

```powershell
$domain = 'https://new.example'   # the new address, without a trailing slash
(Get-Content site\index.html -Raw).Replace('https://letlumi.com', $domain) |
  Set-Content site\index.html -NoNewline -Encoding utf8
Select-String -Path site\index.html -Pattern 'letlumi\.com'   # should print nothing
```

## 2. The hero loop

The window at the top plays a real Lumi run on a loop: in a sample project (`checkout-api`, a small
ASP.NET Core API with synthetic request logs and git history, in an isolated Debug profile), Lumi is asked
why checkout got slower. It reads the logs and the history, finds the commit that made checkout call the
pricing service once per cart item, and answers with a daily latency chart, a diagram of the slow path
and a fix checklist, using GPT-6 Luna. The loop opens on the chart and scrolls through the answer, then
starts over the way a user does: a new chat, with the question typed on its welcome screen, and the work
behind the answer. Lumi names the chat itself after the first message. The waits are shortened and the
caption under the window says it's sped up. The dark and light versions are two separate runs of the same
question, so their answers and diagrams differ.

- The still under it (`assets/img/hero-{dark,light}-*.webp`) is the loop's first frame, so nothing jumps
  when the loop starts. Visitors who prefer reduced motion or have Save-Data on, and browsers that block
  autoplay, get the still with a Play button instead; nothing downloads until it's pressed. (Windows
  reports reduced motion when animations are off, which Remote Desktop sessions often do; a browser
  started while they were off can keep reporting it until it restarts.)
- It loads after the page, plays muted, pauses when scrolled out of view and has a Pause button. It's
  fetched once and played from a `blob:` URL, so seeking and looping never depend on the host supporting
  HTTP range requests (Safari won't play video from a host without them); that's why the CSP allows
  `blob:` media. If no format decodes, the still stays.
- To replace it, keep the file names: `assets/video/hero-{dark,light}-{1980,1320}.{webm,mp4}` at
  1980×1290 and 1320×860, plus matching stills. The current files were encoded with SVT-AV1
  (`-crf 38`) and x264 (`-crf 27`), BT.709 limited range. [`tools/capture`](tools/capture/README.md)
  records, cuts and encodes a new one.

A narrated demo can be linked from the hero later; nothing on the page waits for it.

## 3. Create the Static Web App (Free plan)

Create it in the subscription that holds Lumi's other Azure resources. The Free plan costs nothing, so
it doesn't draw on the subscription's monthly credit.

**Portal:** Create a resource → Static Web App → that subscription → plan **Free**, resource group
`rg-lumi-site`, name `swa-lumi-site`, region East US 2. For **Deployment details**, choose **Other** so
Azure doesn't add its own workflow to the repository (step 4's manual workflow replaces it).

**Or Azure CLI:**

```powershell
$sub = '<your subscription name or id>'
az group create --subscription $sub --name rg-lumi-site --location eastus2
az staticwebapp create --subscription $sub --name swa-lumi-site --resource-group rg-lumi-site --location eastus2 --sku Free
az staticwebapp show --subscription $sub --name swa-lumi-site --resource-group rg-lumi-site --query defaultHostname -o tsv
```

The last command prints the generated address (`<something>.azurestaticapps.net`); the site works
there before any custom domain.

The Free plan ("for personal projects") includes 100 GB of bandwidth a month, 250 MB per environment,
2 custom domains and automatically renewed HTTPS certificates, with no SLA; the Standard plan adds one
([plans](https://learn.microsoft.com/azure/static-web-apps/plans), [quotas](https://learn.microsoft.com/azure/static-web-apps/quotas)).
The site is about 13.3 MB, mostly the eight loop files, of which a visit downloads one. A visit loads
about 0.15 MB before the page shows, then the loop (0.9 MB, or 1.5 MB on high-density screens; 1–2.3 MB
in browsers without AV1), and about 1.8–3 MB in all after scrolling the whole page.

## 4. Deploy with the manual workflow

The site deploys only when you run the **Website** workflow by hand. Three guards keep it yours:

- It has no automatic triggers (no push, pull request or schedule), and only people with write access
  to the repository can run a workflow by hand; today that's only you.
- The job runs only in `adirh3/lumi-site`, only when started (or re-run) by `adirh3`, and only from `main`.
- It deploys through a GitHub **environment**, `website`, that accepts only `main` and waits for your
  approval before the deployment token is released to the job.

Deployment tokens are secrets: never commit one.

### 4.1 Create the `website` environment and its secret (once)

Settings → Environments → **New environment** `website`:

- **Required reviewers:** yourself.
- **Deployment branches and tags:** Selected branches and tags → add `main`.
- **Environment secrets:** `AZURE_STATIC_WEB_APPS_API_TOKEN`, the app's deployment token (Static Web
  App → Overview → Manage deployment token).

Or from a terminal, after step 3:

```powershell
$repo = 'adirh3/lumi-site'
$me = gh api user --jq .id
@{ reviewers = @(@{ type = 'User'; id = [int]$me })
   deployment_branch_policy = @{ protected_branches = $false; custom_branch_policies = $true } } |
  ConvertTo-Json -Depth 4 | gh api -X PUT "repos/$repo/environments/website" --input -
gh api -X POST "repos/$repo/environments/website/deployment-branch-policies" -f name=main -f type=branch
az staticwebapp secrets list --subscription $sub --name swa-lumi-site --resource-group rg-lumi-site --query properties.apiKey -o tsv |
  gh secret set AZURE_STATIC_WEB_APPS_API_TOKEN --env website --repo $repo
```

If the token ever leaks, reset it (Manage deployment token → Reset token) and run the last command again.

### 4.2 The workflow

[`.github/workflows/website.yml`](.github/workflows/website.yml) uploads `site/` as it is (there's no
build step). Its one input, `target`, chooses the live site (`production`) or a separate preview address
(`preview`). Production refuses to deploy while the placeholder site URL from step 1 is still in
`index.html`; a preview doesn't, so you can check the site on Azure before the domain is set.

### 4.3 Deploy

Actions → **Website** → Run workflow → branch `main`, target `production`. The run then waits:
**Review deployments** → `website` → **Approve and deploy**. From a terminal:
`gh workflow run website.yml --repo adirh3/lumi-site --ref main -f target=production`, then approve in the
browser. `preview` publishes to a separate preview address and leaves the live site alone.

Without GitHub, the same files can go up from your computer with the SWA CLI:

```powershell
$env:SWA_CLI_DEPLOYMENT_TOKEN = az staticwebapp secrets list --subscription $sub --name swa-lumi-site --resource-group rg-lumi-site --query "properties.apiKey" -o tsv
npx @azure/static-web-apps-cli@latest deploy ./site --env production
Remove-Item Env:SWA_CLI_DEPLOYMENT_TOKEN
```

## 5. Add the custom domain

Use the apex (`example.dev`) as the address and `www` as a redirect to it; the Free plan allows exactly
these two. For Lumi that's `letlumi.com`, with `www.letlumi.com` redirecting to it. The registrar must
support **ALIAS** (or ANAME/CNAME flattening) at the apex so visitors reach the global edge: Porkbun
does, and Azure DNS does with an alias record. An A record would serve from a single region instead.

1. In the static web app → **Custom domains** → Add → Custom domain on other DNS:
   - `www.example.dev`, hostname record type **CNAME**;
   - `example.dev`, hostname record type **TXT** → Generate code.

   Or: `az staticwebapp hostname set --subscription $sub --name swa-lumi-site --resource-group rg-lumi-site --hostname example.dev --validation-method dns-txt-token --no-wait`,
   then read the code with
   `az staticwebapp hostname show --subscription $sub --name swa-lumi-site --resource-group rg-lumi-site --hostname example.dev --query validationToken -o tsv`.
2. At the DNS provider, add:

   | Type | Host | Value |
   |---|---|---|
   | CNAME | `www` | `<something>.azurestaticapps.net` |
   | TXT | `@` | the code from step 1 |
   | ALIAS | `@` | `<something>.azurestaticapps.net` |

3. When both domains show **Ready** (Azure validates them and issues the certificates), select the apex
   → **Set default**. `www` and the `azurestaticapps.net` address then redirect to it
   ([default domain](https://learn.microsoft.com/azure/static-web-apps/custom-domain-default)).

DNS changes can take minutes to hours; apex changes up to 72 hours
([apex domain guide](https://learn.microsoft.com/azure/static-web-apps/apex-domain-external)).

**Buying the domain in Azure instead:** an App Service domain registers through GoDaddy and hosts its
DNS in Azure DNS (about $0.50 a month per zone, plus queries), so the apex can use an Azure DNS alias
record pointing at the static web app. It offers only .com, .net, .org, .biz, .co.uk, .org.uk, .nl,
.in and .co.in, and can't be bought in credit-based subscriptions
([App Service domains](https://learn.microsoft.com/azure/app-service/manage-custom-dns-buy-domain)).

## 6. After it's live

1. Make sure step 1 used the final domain; if you changed it, merge that to `main` and run the
   **Website** workflow again.
2. Check the link preview: paste the URL into [LinkedIn Post Inspector](https://www.linkedin.com/post-inspector/)
   and into a draft post on X (don't publish it). Both cache previews; Post Inspector refreshes
   LinkedIn's copy after any change to the image or text.
3. Point both repositories at the site:
   `gh repo edit adirh3/Lumi --homepage https://<your-domain>` and
   `gh repo edit adirh3/lumi-site --homepage https://<your-domain>`
4. Optional: use `site/assets/og/lumi-og.png` (1280×640) as Lumi's social preview on GitHub
   (Lumi repository → Settings → General → Social preview → Edit → Upload an image).

## Notes

- **Headers:** `staticwebapp.config.json` sets a strict Content Security Policy (only the site's own
  files). Adding analytics, embedded media or fonts from elsewhere needs a matching CSP change.
- **Caching:** files under `assets/` are cached for a day, CSS and JS for an hour. When replacing an
  image after launch, a new file name shows it to everyone at once.
- **Download links** use GitHub's `releases/latest/download/<file>` URLs, so they follow each new
  release as long as the asset names stay the same. The Android APK and the Linux portable archives have
  versions in their names, so those link to the latest release page. The Windows and Linux ARM64 links
  (`Lumi-win-arm64-Setup.exe`, `Lumi-win-arm64-Portable.zip`, `Lumi-linux-arm64.AppImage`) work only once
  a release with ARM64 builds is out: check them before deploying to production.
- **Screenshots and the hero loop** were captured from a Debug build of Lumi at commit `22c2feec`, in an
  isolated profile ("Alex" is a placeholder user). The runs are real, with GPT-6 Luna: the hero loop
  investigates a slowdown in a small sample API (`checkout-api`), and the steps shown under "Hand it a task"
  come from fixing a bug in another sample repository (`weather-cli`); the other chats are seeded
  examples. They contain no real chats, accounts or paths. [`tools/capture`](tools/capture/README.md) has
  the sample projects, the profile and the steps to capture them again.
