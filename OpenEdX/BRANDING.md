# Theta Tau — Open edX branding

This folder rebrands the Tutor-managed Open edX site (LMS, Studio/CMS and every
micro-frontend) to match Theta Tau's brand. It is the first step in tightening
the Open edX ↔ CMT integration.

> For the **connection** itself — single sign-on and the REST API CMT uses to
> enroll members and sync training progress — see [CONNECTION.md](CONNECTION.md).

> **Stack:** Tutor **v21** (Open edX *Ulmo*) with `tutor-indigo` and `tutor-mfe`
> already installed in the `tutor/` venv. Everything Open edX runs in Docker
> containers managed by Tutor; the CMT Django app runs in its own containers and
> is unaffected by these changes.

---

## What changes

| Brand element        | Where it shows                                   | Mechanism |
|----------------------|--------------------------------------------------|-----------|
| Primary color `#a00e11` | LMS + Studio legacy pages (buttons, links, nav) | `INDIGO_PRIMARY_COLOR` |
| Header logo (crest)  | **All** LMS/CMS pages **and every MFE**          | indigo theme image override |
| Favicon              | LMS, Studio, and MFE browser tabs                | theme image + `MFE_CONFIG.FAVICON_URL` |
| Platform name "Theta Tau" | LMS, Studio, MFEs, outgoing email           | `PLATFORM_NAME` |
| Footer links         | LMS + MFE footer                                 | `INDIGO_FOOTER_NAV_LINKS` |
| Welcome banner       | LMS home hero                                    | `INDIGO_WELCOME_MESSAGE` |

Brand values come from the CMT palette in
[../thetatauCMT/static/css/project.css](../thetatauCMT/static/css/project.css)
(`--tt-dark-red: #a00e11`, gold `--tt-gold: #f4c046`).

### Files in this folder

| File | Purpose |
|------|---------|
| [thetatau_branding.py](thetatau_branding.py) | The Tutor plugin (colors, name, footer, welcome, favicon, logo wiring) |
| `thetatau_branding_theme/indigo/lms/static/images/logo.png` | LMS + MFE header logo (light mode) |
| `thetatau_branding_theme/indigo/lms/static/images/logo-white.png` | Header logo (dark mode) |
| `thetatau_branding_theme/indigo/lms/static/images/favicon.ico` | LMS favicon |
| `thetatau_branding_theme/indigo/cms/static/images/studio-logo.png` | Studio logo |
| `thetatau_branding_theme/indigo/cms/static/images/favicon.ico` | Studio favicon |

> The logo files are copies of `ThetaTauLogoLargeTransparent512.png`. Drop in a
> different image at the same path/filename to change any logo — a wide
> "wordmark" lockup reads better in the header, and a light/white version of the
> crest improves dark mode. Keep the **filenames** unchanged.

---

## Why a plugin (and how the logo override works)

`tutor-indigo` is the official Open edX theming plugin. Rather than fork it, this
plugin *layers on top* of it:

- **Colors / name / footer / welcome** are set via `CONFIG_OVERRIDES`, so they
  win over anything in `config.yml` and stay identical in every environment.
- **Logos** are overridden by registering an extra Tutor *template root* at
  `HIGH` priority. Tutor builds its Jinja `FileSystemLoader` from the template
  roots in priority order and returns the **first** match, so our images take
  precedence over indigo's. Both the legacy themes and indigo's `ThemedLogo`
  component (injected into every MFE) load the logo from
  `…/static/indigo/images/logo.png`, so overriding that one file rebrands the
  logo everywhere at once. `.png`/`.ico` files are copied verbatim, never
  templated.

---

## 1. Test locally

Run every command **from the repo root** so the `.\OpenEdX\...` paths resolve
(if the shell is in another directory you'll get `Copy-Item ... does not exist`).

```powershell
# Windows / PowerShell — run from the repo root:
Set-Location C:\workspace\CMT
.\tutor\Scripts\Activate.ps1

# Copy the plugin AND its theme assets into the Tutor plugins directory.
# They must sit next to each other. Absolute source paths so cwd doesn't matter.
$pluginRoot = tutor plugins printroot
Copy-Item .\OpenEdX\thetatau_branding.py    $pluginRoot -Force
Copy-Item .\OpenEdX\thetatau_branding_theme $pluginRoot -Recurse -Force

tutor plugins enable indigo thetatau_branding
tutor config save

# Rebuild the images so the new colors + logos are baked in, then (re)start.
tutor images build openedx mfe
tutor local start -d
```

> Building the `mfe` image runs `npm install` for the indigo brand package and
> needs internet access. The first `openedx`/`mfe` build takes a while.

Open the site (`tutor local status` shows the URL, e.g. `http://local.openedx.io`)
and confirm: red primary color, Theta Tau crest in the header of the LMS **and**
of the login / dashboard / account MFEs, Theta Tau favicon, and the footer links.

### Quick verification

```powershell
tutor config printvalue INDIGO_PRIMARY_COLOR      # -> #a00e11
tutor config printvalue PLATFORM_NAME             # -> Theta Tau

# Confirm our logo won the override in the rendered environment:
$root = tutor config printroot
Get-Item "$root\env\build\openedx\themes\indigo\lms\static\images\logo.png"
```

---

## 2. Deploy to production

The production host runs the same Tutor stack. The steps mirror local; only the
shell differs (Linux) and image distribution may go through a registry.

```bash
# On the production host, in the Tutor virtualenv:
source /path/to/tutor-venv/bin/activate            # wherever tutor lives
cd /path/to/CMT                                     # repo checkout, so the paths below resolve

# Copy the plugin + theme assets from the repo checkout into the plugins dir.
PLUGIN_ROOT="$(tutor plugins printroot)"
cp     OpenEdX/thetatau_branding.py         "$PLUGIN_ROOT"/
cp -r  OpenEdX/thetatau_branding_theme      "$PLUGIN_ROOT"/

tutor plugins enable indigo thetatau_branding
tutor config save
```

Then rebuild + roll out. **Pick the row that matches how production runs:**

**a) Build on the production host (single Docker host — matches this setup):**

```bash
tutor images build openedx mfe
tutor local start -d          # recreates only the changed containers
```

**b) Build once, ship via a registry (multi-host / CI):**

```bash
tutor images build openedx mfe
tutor images push  openedx mfe
# on each host that pulls:
tutor config save
tutor local dc pull
tutor local start -d
```

> `tutor local start -d` recreates containers whose image changed and leaves the
> rest running. No database migration or downtime is involved — this is a
> static-asset/theme change only.

### Moving the config, not just the plugin

Everything brand-related lives **in the plugin** (`CONFIG_OVERRIDES` +
`ENV_PATCHES`), so production needs no manual `tutor config save --set …`
commands — copying the two artifacts and enabling the plugin is the whole config
change. Keep both files in version control (this folder) so local and production
never drift.

If you prefer the platform name to differ per environment, delete the
`("PLATFORM_NAME", …)` line from `thetatau_branding.py` and instead run, per host:

```bash
tutor config save --set PLATFORM_NAME="Theta Tau"
```

---

## 3. Customizing later

Edit [thetatau_branding.py](thetatau_branding.py) and re-run steps 1/2:

- **Color** — change `TT_PRIMARY_COLOR`.
- **Footer** — edit `FOOTER_NAV_LINKS` (list of `{"title", "url"}`; set to `[]`
  to remove all links).
- **Welcome banner** — change `WELCOME_MESSAGE`.
- **Logos / favicon** — replace the files under `thetatau_branding_theme/…`
  (same filenames).

After any change: `tutor config save && tutor images build openedx mfe &&
tutor local start -d`. (Color/logo changes require rebuilding `openedx`; MFE-only
changes require rebuilding `mfe`.)

To roll the branding back:

```bash
tutor plugins disable thetatau_branding
tutor config save && tutor images build openedx mfe && tutor local start -d
```

---

## 4. Known limitation — MFE Paragon color palette (phase 2)

The steps above recolor the **legacy** LMS/CMS theme, and set the logo, favicon,
name, footer and welcome message on **everything** (including MFEs). However, the
*component* palette inside the MFEs (Paragon buttons, form controls, etc.) is
still driven by indigo's pre-built Paragon theme CSS (`PARAGON_THEME_URLS`,
indigo blue), which `INDIGO_PRIMARY_COLOR` does **not** affect.

To fully recolor MFE components to Theta Tau red you build a small Paragon
"design tokens" brand package and point `MFE_CONFIG["PARAGON_THEME_URLS"]` at its
compiled `light.css` / `dark.css`. That is a self-contained follow-up: it adds a
`CONFIG_OVERRIDES`/`ENV_PATCHES` entry to this same plugin and a hosted CSS file —
no change to the workflow above. Track it as the next branding task.
