import os
import environ
from django.conf import settings
from quickbooks import QuickBooks
from intuitlib.client import AuthClient


def get_quickbooks_client():
    env = environ.Env()
    auth_client = AuthClient(
        client_id=env("QUICKBOOKS_CLIENT"),
        client_secret=env("QUICKBOOKS_SECRET"),
        environment="production",
        redirect_uri="http://localhost:8000/callback",
    )
    token_path = str(settings.ROOT_DIR / "secrets" / "QUICKBOOKS_REFRESH_TOKEN")
    if os.path.exists(token_path):
        with open(token_path, "r") as refresh_token_file:
            refresh_token = refresh_token_file.read()
    else:
        print("NEED TO GENERATE REFRESH TOKEN!")
        return
    auth_client.refresh(refresh_token=refresh_token)
    with open(token_path, "w") as refresh_token_file:
        refresh_token_file.write(auth_client.refresh_token)
    client = QuickBooks(
        auth_client=auth_client,
        refresh_token=auth_client.refresh_token,
        company_id="9130348538823906",
        minorversion=62,
    )
    return client
