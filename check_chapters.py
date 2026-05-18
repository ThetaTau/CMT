import os
os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings.test"
import django
django.setup()
from thetatauCMT.chapters.models import Chapter
count = Chapter.objects.count()
print("Count:", count)
if count > 0:
    ch = Chapter.objects.first()
    print("First:", ch.slug, ch.name)
from thetatauCMT.users.forms import UserAlterForm
print("AlterForm choices count:", len(UserAlterForm.base_fields["chapter"].choices))
if UserAlterForm.base_fields["chapter"].choices:
    print("First choice:", UserAlterForm.base_fields["chapter"].choices[0])
