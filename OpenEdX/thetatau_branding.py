"""
Theta Tau branding for the Open edX (Tutor) deployment.

This is a Tutor *plugin*. It rebrands the LMS, Studio (CMS) and every
micro-frontend (MFE) to match Theta Tau's brand:

  * Primary color  -> Theta Tau dark red (#a00e11)
  * Header logo    -> Theta Tau crest (all LMS/CMS pages **and** every MFE)
  * Favicon        -> Theta Tau favicon
  * Platform name  -> "Theta Tau"
  * Footer links   -> Theta Tau links
  * Welcome banner -> Theta Tau message

It layers on top of ``tutor-indigo``: indigo provides the theme machinery and
this plugin overrides indigo's colors, config values and logo image files.

------------------------------------------------------------------------------
Install (local venv or production host)
------------------------------------------------------------------------------
1. Copy BOTH this file *and* the sibling ``thetatau_branding_theme`` folder into
   the Tutor plugins directory (keep them next to each other):

       cp -r thetatau_branding.py thetatau_branding_theme "$(tutor plugins printroot)"/

   Tutor only auto-discovers the ``*.py`` file; the theme folder is located by
   this plugin relative to its own path, so the two must sit side by side.
   (For this reason, do NOT use ``tutor plugins install`` -- it copies only the
   .py file and the logo override would be skipped.)

2. Enable indigo (if not already) and this plugin, then rebuild and restart:

       tutor plugins enable indigo thetatau_branding
       tutor config save
       tutor images build openedx mfe     # bake theme colors + logos into images
       tutor local restart                # or: tutor k8s start

See BRANDING.md for full details, customization and production notes.
"""

from __future__ import annotations

import os

from tutor import fmt, hooks

# --------------------------------------------------------------------------- #
# Brand constants.
# Keep these in sync with thetatauCMT/static/css/project.css (--tt-* variables).
# --------------------------------------------------------------------------- #
TT_PRIMARY_COLOR = "#a00e11"  # Theta Tau dark red (--tt-dark-red)
PLATFORM_NAME = "Theta Tau"
WELCOME_MESSAGE = "Theta Tau — Professional Engineering Fraternity Learning"

# Footer links shown by the indigo theme (LMS + MFEs).
FOOTER_NAV_LINKS = [
    {"title": "Theta Tau", "url": "https://thetatau.org"},
    {"title": "Chapter Management Tool", "url": "https://cmt.thetatau.org"},
    {"title": "Contact", "url": "https://thetatau.org/contact"},
    {"title": "Privacy Policy", "url": "https://thetatau.org/privacy-policy"},
]

HERE = os.path.dirname(os.path.abspath(__file__))
THEME_ROOT = os.path.join(HERE, "thetatau_branding_theme")


# --------------------------------------------------------------------------- #
# 1. Force branding config values.
#    CONFIG_OVERRIDES takes precedence over whatever is stored in config.yml, so
#    branding stays identical across every environment that enables this plugin.
# --------------------------------------------------------------------------- #
hooks.Filters.CONFIG_OVERRIDES.add_items(
    [
        ("INDIGO_PRIMARY_COLOR", TT_PRIMARY_COLOR),
        ("INDIGO_WELCOME_MESSAGE", WELCOME_MESSAGE),
        ("INDIGO_FOOTER_NAV_LINKS", FOOTER_NAV_LINKS),
        # Platform name is a *core* Tutor setting used by the LMS, Studio, MFEs
        # and outgoing emails. Remove this line if you would rather manage the
        # platform name per-environment in config.yml.
        ("PLATFORM_NAME", PLATFORM_NAME),
    ]
)


# --------------------------------------------------------------------------- #
# 2. Override indigo's logo / favicon image files.
#
#    indigo's ThemedLogo component (injected into every MFE) and the legacy
#    LMS/CMS themes all load the logo from
#        {LMS_BASE_URL}/static/indigo/images/logo.png
#    so replacing these theme files rebrands the logo *everywhere* at once.
#
#    We register our template root at HIGH priority. Tutor builds the Jinja
#    FileSystemLoader from ENV_TEMPLATE_ROOTS in priority order and returns the
#    first match, so our images take precedence over the ones shipped by
#    tutor-indigo. PNG/ICO files are copied verbatim (never Jinja-rendered), so
#    binary assets are safe here.
#
#    Note: we do NOT need to register an ENV_TEMPLATE_TARGET -- indigo already
#    renders the whole "indigo/" tree (from every template root) into
#    build/openedx/themes, which picks up our overriding files automatically.
# --------------------------------------------------------------------------- #
if not os.path.isdir(THEME_ROOT):
    fmt.echo_alert(
        f"thetatau_branding: theme assets not found at {THEME_ROOT}. "
        "Copy the 'thetatau_branding_theme' folder next to thetatau_branding.py "
        "inside `tutor plugins printroot`."
    )

hooks.Filters.ENV_TEMPLATE_ROOTS.add_item(THEME_ROOT, priority=hooks.priorities.HIGH)


# --------------------------------------------------------------------------- #
# 3. Point the MFE browser-tab favicon at the Theta Tau favicon served by the
#    LMS theme. The visible in-page logo is already handled by indigo's
#    ThemedLogo (section 2); this only covers the browser tab icon.
# --------------------------------------------------------------------------- #
hooks.Filters.ENV_PATCHES.add_item(
    (
        "mfe-lms-common-settings",
        'MFE_CONFIG["FAVICON_URL"] = '
        f"\"{{ 'https' if ENABLE_HTTPS else 'http' }}://{{ LMS_HOST }}"
        '/static/indigo/images/favicon.ico"',
    )
)
