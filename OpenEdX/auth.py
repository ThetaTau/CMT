from social_core.backends.oauth import BaseOAuth2PKCE

BASE_API = "https://cmt.thetatau.org"


class CMTOAuth2(BaseOAuth2PKCE):
    """CMT OAuth authentication backend"""

    name = "cmt"
    AUTHORIZATION_URL = f"{BASE_API}/o/authorize/"
    ACCESS_TOKEN_URL = f"{BASE_API}/o/token/"
    ACCESS_TOKEN_METHOD = "POST"
    DEFAULT_SCOPE = ["openid"]
    SCOPE_SEPARATOR = ","
    EXTRA_DATA = [
        ("email", "email"),
        ("username", "username"),
        ("name", "name"),
        ("first_name", "first_name"),
        ("last_name", "last_name"),
    ]
    PKCE_DEFAULT_CODE_CHALLENGE_METHOD = "plain"
    PKCE_DEFAULT_CODE_VERIFIER_LENGTH = 48  # must be b/w 43-127 chars
    DEFAULT_USE_PKCE = True

    def get_user_details(self, response):
        """Return user details from CMT account"""
        return {
            "id": response.get("sub"),
            "uid": response.get("sub"),
            "username": response.get("username"),
            "email": response.get("email"),
            "first_name": response.get("first_name"),
            "last_name": response.get("last_name"),
            "fullname": response.get("name"),
            "terms_of_service": "true",
            "honor_code": "true",
            "country": "US",
        }

    def user_data(self, access_token, *args, **kwargs) -> dict:
        """Fetch user data from Bitbucket Data Center REST API"""
        # At this point, we don't know the current user's username
        headers = {"Authorization": f"Bearer {access_token}"}
        response = self.get_json(
            url=f"{BASE_API}/o/userinfo",
            method="GET",
            headers=headers,
        )
        return response
