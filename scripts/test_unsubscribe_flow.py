"""Verify the UnsubscribeConfirmView flow end-to-end.

Run inside the app container:
    python manage.py runscript test_unsubscribe_flow
"""

from django.test import Client
from django.urls import reverse

from thetatauCMT.users.models import User
from thetatauCMT.users.views import make_unsubscribe_token


def run():
    user = User.objects.filter(email="venturafranklin@gmail.com").first()
    if user is None:
        print("No test user available; aborting.")
        return

    # Reset baseline
    user.unsubscribe_email = False
    user.save(update_fields=["unsubscribe_email"])
    print(f"Before: unsubscribe_email={user.unsubscribe_email}")

    token = make_unsubscribe_token(user)
    url = reverse("users:unsubscribe", kwargs={"token": token})

    client = Client()
    get = client.get(url, HTTP_HOST="localhost")
    print(
        f"GET  {url} -> {get.status_code}; body has 'Confirm unsubscribe': " f"{b'Confirm unsubscribe' in get.content}"
    )

    post = client.post(url, HTTP_HOST="localhost")
    print(
        f"POST {url} -> {post.status_code}; body has 'You'; unsubscribed: "
        f"{b'You&rsquo;re unsubscribed' in post.content}"
    )

    user.refresh_from_db()
    print(f"After:  unsubscribe_email={user.unsubscribe_email}")

    # Test bad token
    bad = client.get(reverse("users:unsubscribe", kwargs={"token": "garbage"}), HTTP_HOST="localhost")
    print(f"GET bad -> {bad.status_code}; shows invalid: " f"{b'Invalid or expired link' in bad.content}")

    # Restore
    user.unsubscribe_email = False
    user.save(update_fields=["unsubscribe_email"])
    print("Restored unsubscribe_email=False")
