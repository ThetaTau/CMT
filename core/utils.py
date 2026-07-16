from django.conf import settings
from pydrive2.auth import GoogleAuth


def check_officer(request):
    user = request.user
    if getattr(user, "natoff_hidden", False):
        # National Officer previewing the site as a member: officer status now
        # comes only from an actual chapter role (including the UserAlter role),
        # never from ``natoff`` / ``officer`` group membership.
        if user.chapter_officer():
            request.is_officer = True
        return request
    if user.groups.filter(name__in=["officer", "natoff"]).exists():
        request.is_officer = True
    return request


def check_nat_officer(request):
    user = request.user
    if user.groups.filter(name="natoff").exists():
        # Raw group membership — always set so the "view as member" switch-back
        # controls stay available even while natoff functionality is hidden.
        request.in_natoff_group = True
        if not getattr(user, "natoff_hidden", False):
            request.is_nat_officer = True
    return request


def login_with_service_account():
    """
    Google Drive service with a service account.
    note: for the service account to work, you need to share the folder or
    files with the service account email.

    :return: google auth
    """
    # Define the settings dict to use a service account
    # We also can use all options available for the settings dict like
    # oauth_scope,save_credentials,etc.
    config = {
        "client_config_backend": "service",
        "service_config": {
            "client_json_file_path": str(settings.ROOT_DIR / "secrets" / "ChapterManagementTool-b239bceff1a7.json"),
        },
    }
    # Create instance of GoogleAuth
    gauth = GoogleAuth(settings=config)
    # Authenticate
    gauth.ServiceAuth()
    return gauth
