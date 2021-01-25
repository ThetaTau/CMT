import os
import sys

path = ""
if path not in sys.path:
    sys.path.append(path)


os.environ["DJANGO_SETTINGS_MODULE"] = ""
os.environ["DJANGO_SECRET_KEY"] = ""
os.environ["DJANGO_ALLOWED_HOSTS"] = ""
os.environ["DJANGO_ADMIN_URL"] = ""
os.environ["MAILJET_API_KEY"] = ""
os.environ["MAILJET_SECRET_KEY"] = ""
os.environ["DJANGO_AWS_ACCESS_KEY_ID"] = ""
os.environ["DJANGO_AWS_SECRET_ACCESS_KEY"] = ""
os.environ["DJANGO_AWS_STORAGE_BUCKET_NAME"] = ""
os.environ["ROLLBAR_ACCESS"] = ""
os.environ["DATABASE_URL"] = ""
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = ""
os.environ["DJANGO_GCP_STORAGE_BUCKET_NAME"] = "theta-tau"
os.environ["RECAPTCHA_PUBLIC_KEY"] = ""
os.environ["RECAPTCHA_PRIVATE_KEY"] = ""
os.environ["MOOSEND_API_KEY"] = ""


from django.core.wsgi import get_wsgi_application  # noqa: E402

MAINTENANCE_FILE = rf"{path}/maintenance_active"

if not os.path.exists(MAINTENANCE_FILE):
    application = get_wsgi_application()
else:

    def application(environ, start_response):
        status = "503 Service Unavailable"
        maintenance_file_path = rf"{path}/thetatauCMT/templates/503.html"
        content = open(maintenance_file_path, "r").read()
        response_headers = [
            ("Content-Type", "text/html"),
            ("Content-Length", str(len(content))),
        ]
        start_response(status, response_headers)
        yield content.encode("utf8")
