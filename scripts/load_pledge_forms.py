import csv
import warnings
from datetime import datetime
from django.db import transaction
from django.db.utils import IntegrityError
from forms.models import Pledge
from chapters.models import Chapter


def run(*args):
    """
    Space seperated list with --script-args "path_to_file" "path2_to_file"
    :param args: List of files to read pledge forms
    :return: None
    python manage.py runscript load_pledge_forms --script-args secrets/20200205_pledgeforms.csv
    """
    for path in args:
        with open(path) as f:
            reader = csv.DictReader(f)
            for pledge_form in reader:
                chapter_obj = Chapter.get_school_chapter(pledge_form["School Name"])
                name = f'{pledge_form["Legal First Name"]} {pledge_form["Full Middle Name"]} {pledge_form["Last Name"]}'
                form_obj = Pledge(
                    name=name,
                    chapter=chapter_obj,
                    email=pledge_form["School E-mail"],
                    created=datetime.strptime(
                        pledge_form["Submission Date"], "%Y-%m-%d %H:%M:%S"
                    ),
                )
                try:
                    with transaction.atomic():
                        form_obj.save()
                except IntegrityError:
                    warnings.warn(f"{name} already existed for {chapter_obj}")
                    continue
