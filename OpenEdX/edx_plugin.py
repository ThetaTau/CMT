"""
nano /home/frank_ventura/.local/share/tutor-plugins/myplugin.py
tutor plugins disable myplugin
tutor plugins enable myplugin
tutor local restart
"""
from tutor import hooks

hooks.Filters.CONFIG_USER.add_items(
    [
        ("EMAIL_BACKEND", "anymail.backends.mailjet.EmailBackend"),
        ("RUN_SMTP", False),
        ("SMTP_HOST", "in-v3.mailjet.com"),
        ("SMTP_PORT", 587),
        ("SMTP_USE_SSL", False),
        ("SMTP_USE_TLS", True),
        ("SMTP_USERNAME", ""),
        ("SMTP_PASSWORD", ""),
        ("MAILJET_API_KEY", ""),
        ("MAILJET_SECRET_KEY", ""),
    ]
)

# hooks.Filters.CONFIG_USER.add_item(
#     ("OPENEDX_EXTRA_PIP_REQUIREMENTS", "'django-anymail[mailjet]==8.6'"),
# )

hooks.Filters.CONFIG_OVERRIDES.add_item(
    ("EMAIL_BACKEND", "anymail.backends.mailjet.EmailBackend"),
)

hooks.Filters.ENV_PATCHES.add_items(
    [
        ("openedx-cms-common-settings", "FEATURES['SHOW_REGISTRATION_LINKS'] = False"),
        ("openedx-lms-common-settings", "FEATURES['SHOW_REGISTRATION_LINKS'] = False"),
        ("cms-env", "EMAIL_BACKEND: anymail.backends.mailjet.EmailBackend"),
        ("lms-env", "EMAIL_BACKEND: anymail.backends.mailjet.EmailBackend"),
        ("cms-env", "MAILJET_API_KEY: "),
        ("lms-env", "MAILJET_API_KEY: "),
        ("cms-env", "MAILJET_SECRET_KEY: "),
        ("lms-env", "MAILJET_SECRET_KEY: "),
        ("common-env-features", "SHOW_REGISTRATION_LINKS: false"),
        ("openedx-auth", "SHOW_REGISTRATION_LINKS: false"),
        ("openedx-cms-common-settings", "SHOW_REGISTRATION_LINKS = False"),
        ("openedx-lms-common-settings", "SHOW_REGISTRATION_LINKS = False"),
        (
            "openedx-cms-common-settings",
            "SOCIAL_AUTH_STRATEGY = 'auth_backends.strategies.EdxDjangoStrategy'",
        ),
        (
            "openedx-lms-common-settings",
            "SOCIAL_AUTH_STRATEGY = 'auth_backends.strategies.EdxDjangoStrategy'",
        ),
        ("openedx-cms-common-settings", "ENABLE_REQUIRE_THIRD_PARTY_AUTH = False"),
        ("openedx-lms-common-settings", "ENABLE_REQUIRE_THIRD_PARTY_AUTH = False"),
        ("common-env-features", "ENABLE_REQUIRE_THIRD_PARTY_AUTH: false"),
        ("common-env", "ENABLE_REQUIRE_THIRD_PARTY_AUTH: false"),
        (
            "openedx-cms-common-settings",
            "AUTHENTICATION_BACKENDS = ['lms.envs.tutor.auth.CMTOAuth2', 'auth_backends.backends.EdXOAuth2', 'django.contrib.auth.backends.ModelBackend',]",
        ),
        (
            "openedx-lms-common-settings",
            "AUTHENTICATION_BACKENDS = ['lms.envs.tutor.auth.CMTOAuth2', 'auth_backends.backends.EdXOAuth2', 'django.contrib.auth.backends.ModelBackend',]",
        ),
        (
            "openedx-cms-common-settings",
            "SOCIAL_AUTH_OAUTH_SECRETS = {'cmt': ''}",
        ),
        (
            "openedx-lms-common-settings",
            "SOCIAL_AUTH_OAUTH_SECRETS = {'cmt': ''}",
        ),
        # (
        #     "openedx-lms-common-settings",
        #     "ALLOWED_HOSTS.append('host.docker.internal')",
        # ),
    ]
)
