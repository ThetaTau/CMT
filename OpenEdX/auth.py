from social_core.backends.oauth import BaseOAuth2


class CMTOAuth2(BaseOAuth2):
    """CMT OAuth authentication backend"""

    name = "cmt"
    AUTHORIZATION_URL = "https://cmt.thetatau.org/o/authorize/"
    ACCESS_TOKEN_URL = "https://cmt.thetatau.org/o/token/"
    ACCESS_TOKEN_METHOD = "POST"
    SCOPE_SEPARATOR = ","
    EXTRA_DATA = [("id", "id"), ("expires", "expires")]

    def get_user_details(self, response):
        """Return user details from CMT account"""
        return {
            "username": response.get("login"),
            "email": response.get("email") or "",
            "first_name": response.get("name"),
        }
