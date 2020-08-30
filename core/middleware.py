from django.shortcuts import redirect
from django.contrib import messages
from django.conf import settings

from forms.models import RiskManagement, PledgeProgram


class RMPSignMiddleware:
    """Django Middleware (add to MIDDLEWARE) to enforce members to sign rmp"""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        # only relevant for logged in users
        if not request.user.is_authenticated:
            return response
        path = request.path
        # pages to not redirect on (no recursion please!)
        path = path.strip("/")
        if (
            path
            in "logout forms/rmp rmp electronic_terms forms/pledge_program forms/report".split()
        ) or settings.DEBUG:
            return response
        if request.user.is_officer:
            if not RiskManagement.user_signed_this_year(request.user):
                messages.add_message(
                    request,
                    messages.ERROR,
                    f"You must sign the Risk Management Policies and Agreements "
                    f"of Theta Tau this year.",
                )
                return redirect("rmp")
        if request.user.is_council_officer():
            if not PledgeProgram.signed_this_semester(request.user.current_chapter):
                messages.add_message(
                    request,
                    messages.ERROR,
                    f"Your chapter must submit the New Member Education Program this semester.",
                )
                return redirect("forms:pledge_program")
        return response
