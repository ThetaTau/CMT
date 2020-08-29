from django.shortcuts import redirect
from django.contrib import messages

from forms.models import RiskManagement


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
        if path in "logout forms/rmp rmp electronic_terms".split():
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

        return response
