import json

from braces.views import LoginRequiredMixin
from django.http import Http404, JsonResponse
from django.shortcuts import redirect
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.generic import TemplateView, View
from django_tables2 import RequestConfig

from thetatauCMT.tasks.tables import TaskTable

from . import services
from .models import RoleGuide


class CatalogView(TemplateView):
    """ "What can the CMT do?" -- the durable artifact behind every help link (TWI-9).

    Deliberately **not** ``LoginRequiredMixin``. The help icon is visible signed
    out, so an anonymous hit renders the one ``public`` area plus a sign-in
    prompt; bouncing to the login page would lose the four things a locked-out
    member actually came for.
    """

    template_name = "guides/catalog.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["catalog"] = services.get_catalog(self.request.user)
        context["duty_roles"] = sorted(services.get_duty_roles(self.request.user))
        context["role_guides"] = services.get_role_guides(self.request.user)
        return context


class RoleGuideIndexView(LoginRequiredMixin, TemplateView):
    """``/features/role/`` -- straight to your own guide when there is exactly one.

    Someone who holds one office wants their page, not a menu; someone who holds
    two (or none) needs the list. Redirecting only in the unambiguous case keeps
    the account-menu link useful for everybody.
    """

    template_name = "guides/role_guide_index.html"

    def get(self, request, *args, **kwargs):
        mine = services.get_role_guides(request.user)
        if len(mine) == 1:
            return redirect(mine[0].get_absolute_url())
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["mine"] = services.get_role_guides(self.request.user)
        context["guides"] = list(RoleGuide.objects.active())
        return context


class RoleGuideDetailView(LoginRequiredMixin, TemplateView):
    """ "I'm the new Treasurer -- what am I responsible for?" (TWI-12).

    Readable by any signed-in member, not just the officer holding the role: a
    Regent needs to know what the Scribe owes, and an adviser needs all of them.
    What is *personalised* is the open-items table, which is scoped to the
    viewer's own chapter.
    """

    template_name = "guides/role_guide.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        guide = RoleGuide.objects.active().filter(slug=self.kwargs["slug"]).first()
        if guide is None:
            raise Http404("No such role guide.")
        context.update(services.get_role_guide_detail(guide, self.request.user))
        context["is_mine"] = guide.role in services.get_duty_roles(self.request.user)
        table = TaskTable(data=context.pop("open_items"), complete=False)
        RequestConfig(self.request, paginate=False).configure(table)
        context["table"] = table
        return context


class HelpHubView(TemplateView):
    """The ``?`` icon's destination (TWI-10).

    Replaces a page that was nothing but an iframe onto a published Google Doc
    that had drifted years out of date. Four questions, four answers, all backed
    by the registry so they cannot drift again.

    Renders for anonymous visitors -- the ``?`` is in the signed-out navbar --
    but for them ``get_catalog`` returns only the ``getting-in`` area, so the
    public hub is the login-help block and nothing else.
    """

    template_name = "pages/help.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["catalog"] = services.get_catalog(self.request.user)
        context["role_guides"] = services.get_role_guides(self.request.user)
        return context


class AcknowledgeView(LoginRequiredMixin, View):
    """The single "Got it" endpoint behind every What's New surface (TWI-6).

    Accepts either a JSON body -- ``{"items": [{"kind", "id"}, ...], "source"}``
    for the modal's batch dismiss -- or a plain form post of one ``kind``/``id``
    pair, so the home page buttons keep working with JavaScript off. Ids the
    user cannot see are skipped rather than rejected: a tab left open across a
    deploy must not start throwing errors at people.
    """

    def post(self, request, *args, **kwargs):
        items, source, wants_json = self._parse(request)
        if items is None:
            return JsonResponse({"ok": False, "error": "Malformed payload."}, status=400)
        acknowledged = services.acknowledge(request.user, items, source)
        if wants_json:
            return JsonResponse({"ok": True, "acknowledged": acknowledged})
        return redirect(self._next(request))

    @staticmethod
    def _parse(request):
        """``(items, source, wants_json)``; ``items`` is ``None`` if unparseable."""
        if request.content_type == "application/json":
            try:
                payload = json.loads(request.body or b"{}")
            except (ValueError, UnicodeDecodeError):
                return None, "", True
            if not isinstance(payload, dict):
                return None, "", True
            items = payload.get("items")
            if not isinstance(items, list):
                return None, "", True
            return items, str(payload.get("source") or ""), True
        item = {"kind": request.POST.get("kind"), "id": request.POST.get("id")}
        wants_json = request.headers.get("x-requested-with") == "XMLHttpRequest"
        return [item], request.POST.get("source") or "", wants_json

    @staticmethod
    def _next(request):
        target = request.POST.get("next") or ""
        if target and url_has_allowed_host_and_scheme(
            target, allowed_hosts={request.get_host()}, require_https=request.is_secure()
        ):
            return target
        return "home"


class WhatsNewSeenView(LoginRequiredMixin, View):
    """Marks the unprompted modal as shown for this session.

    Fired by the browser at the moment the modal is actually displayed, not when
    the page is rendered. ``RMPSignMiddleware`` runs *after* the view, so a page
    can render fully and then be replaced by a redirect -- marking it seen
    server-side would burn the one showing on a page nobody saw.
    """

    def post(self, request, *args, **kwargs):
        request.session[services.WHATS_NEW_SESSION_KEY] = True
        return JsonResponse({"ok": True})


class WhatsNewArchiveView(LoginRequiredMixin, TemplateView):
    """Everything the viewer may see, acknowledged or not, newest first.

    The safety net behind every dismiss: nothing this feature hides is ever
    unrecoverable.
    """

    template_name = "guides/whats_new.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["items"] = services.get_whats_new(self.request.user, include_acknowledged=True)
        return context
