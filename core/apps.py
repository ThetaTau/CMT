from viewflow.frontend.apps import ViewflowFrontendConfig


class GuardedViewflowFrontendConfig(ViewflowFrontendConfig):
    """Override the viewflow frontend site so its queue/inbox/archive listings use
    the ``core.flows`` list views that tolerate stale task rows (#952).

    Referenced from ``INSTALLED_APPS`` in place of ``"viewflow.frontend"``; it
    keeps the same app ``name``/``label`` (so flow registration and templates are
    unchanged) and only swaps the ``viewset`` that builds the site URLs.
    """

    viewset = "core.flows.GuardedFrontendViewSet"
