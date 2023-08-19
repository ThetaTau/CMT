from django.conf import settings
from pydrive2.auth import GoogleAuth


def check_officer(request):
    if request.user.groups.filter(name__in=["officer", "natoff"]).exists():
        request.is_officer = True
    return request


def check_nat_officer(request):
    if request.user.groups.filter(name="natoff").exists():
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
            "client_json_file_path": str(
                settings.ROOT_DIR
                / "secrets"
                / "ChapterManagementTool-b239bceff1a7.json"
            ),
        },
    }
    # Create instance of GoogleAuth
    gauth = GoogleAuth(settings=config)
    # Authenticate
    gauth.ServiceAuth()
    return gauth
