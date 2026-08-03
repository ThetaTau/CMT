"""Mount the Django admin at ``settings.ADMIN_URL`` instead of ``/admin/``.

``material.admin.apps.MaterialAdminConfig`` registers a django-material frontend
module whose resolver is hard-coded to ``^admin/``. That module is pulled into the
root URLconf by ``include(modules.urls)``, so the admin stayed reachable at the
well-known ``/admin/`` path even when ``DJANGO_ADMIN_URL`` set a secret prefix.
This subclass is referenced from ``INSTALLED_APPS`` in place of ``"material.admin"``
so the module mounts at the configured prefix only.
"""

from django.conf import settings
from django.contrib import admin
from material.admin.apps import MaterialAdminConfig
from material.frontend.urlconf import ModuleURLResolver


def admin_url_regex():
    """``settings.ADMIN_URL`` as a regex anchored to the start of the path.

    Django resolves ``re_path`` patterns with ``re.search``, so an unanchored
    value would also match the admin under any prefix (``/foo/<admin-url>/``).
    """
    return r"^{}".format(settings.ADMIN_URL.lstrip("^"))


class SecureMaterialAdminConfig(MaterialAdminConfig):
    """``MaterialAdminConfig`` with the ``^admin/`` mount point made configurable."""

    @property
    def urls(self):
        return ModuleURLResolver(
            admin_url_regex(),
            admin.site.urls[0],
            namespace="admin",
            module=self,
        )
