# from thetatauCMT.users.models import User
from csv import DictReader

from thetatauCMT.chapters.models import Chapter

file_path = "secrets/20180725_all_all.CSV"
missing_chapters = set()
with open(file_path, "r") as csv_file:
    reader = DictReader(csv_file)
    for row in reader:
        try:
            chapter_obj = Chapter.objects.get(name=row["chapter"])
        except Chapter.DoesNotExist:
            missing_chapters.add(row["chapter"])

print("MISSING CHAPTERS", missing_chapters)
