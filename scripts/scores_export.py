import csv
import datetime
from scores.models import ScoreChapter
from chapters.models import Chapter
from events.models import Event
from submissions.models import Submission

fields = [
    "Chapter name",
    "Region",
    "Brotherhood",
    "Operate",
    "Professional",
    "Service",
    "Term",
    "Year",
    "Total",
    "Brotherhood #",
    "Operate #",
    "Professional #",
    "Service #",
    "Total #",
]


def run(*args):
    """
    Not inclusive of year_end
    python manage.py runscript scores_export --script-args year_start year_end
    python manage.py runscript scores_export --script-args 2018 2022
    """
    year_start, year_end = args[0], args[1]
    with open(
        f"exports/scores_export_{year_start}_{year_end}.csv", "w", newline=""
    ) as export_file:
        writer = csv.DictWriter(export_file, fieldnames=fields)
        writer.writeheader()
        chapters = Chapter.objects.exclude(active=False)
        for year in range(int(year_start), int(year_end)):
            for term in ["sp", "fa"]:
                print("Processing:", year, term)
                month = {"sp": 3, "fa": 10}[term]
                date = datetime.date(year, month, 1)
                scores_terms = ScoreChapter.type_score_biennium(date, chapters)
                for scores_term in scores_terms:
                    writer.writerow(
                        {
                            "Chapter name": scores_term["chapter_name"],
                            "Region": scores_term["region"],
                            "Brotherhood": scores_term["Bro"],
                            "Operate": scores_term["Ops"],
                            "Professional": scores_term["Pro"],
                            "Service": scores_term["Ser"],
                            "Term": {"sp": "Spring", "fa": "Fall"}[term],
                            "Year": year,
                            "Total": scores_term["total"],
                        }
                    )
