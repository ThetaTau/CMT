from social_core.backends.oauth import BaseOAuth2PKCE


class CMTOAuth2(BaseOAuth2PKCE):
    """CMT OAuth authentication backend"""

    name = "cmt"
    AUTHORIZATION_URL = "https://cmt.thetatau.org/o/authorize/"
    ACCESS_TOKEN_URL = "https://cmt.thetatau.org/o/token/"
    ACCESS_TOKEN_METHOD = "POST"
    SCOPE_SEPARATOR = ","
    EXTRA_DATA = [("id", "id"), ("expires", "expires")]
    PKCE_DEFAULT_CODE_CHALLENGE_METHOD = "s256"  # can be "plain" or "s256"
    PKCE_DEFAULT_CODE_VERIFIER_LENGTH = 48  # must be b/w 43-127 chars
    DEFAULT_USE_PKCE = True

    def get_user_details(self, response):
        """Return user details from CMT account"""
        return {
            "username": response.get("login"),
            "email": response.get("email") or "",
            "first_name": response.get("name"),
        }
