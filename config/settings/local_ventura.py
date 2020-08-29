from .local import *

DEFAULT_FILE_STORAGE = "django.core.files.storage.FileSystemStorage"
# GOOGLE_DRIVE_STORAGE_JSON_KEY_FILE = r"E:\workspace\CMT\thetatauCMT\secrets\ChapterManagementTool-b239bceff1a7.json"

if False:
    EMAIL_BACKEND = "anymail.backends.mailjet.EmailBackend"
    ANYMAIL = {
        "MAILJET_API_KEY": env("MAILJET_API_KEY"),
        "MAILJET_SECRET_KEY": env("MAILJET_SECRET_KEY"),
    }
    INSTALLED_APPS += ["anymail"]
