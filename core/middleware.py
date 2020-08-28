from django.shortcuts import redirect

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
        if path in "logout forms/rmp".split():
            return response
        if request.user.is_officer:
            if not RiskManagement.user_signed_this_year(request.user):
                return redirect("rmp")

        return response
