import datetime
from enum import Enum
from django.db import models
from django.db.models import Sum
from django.db.models.functions import Round
from core.models import YearTermModel, BIENNIUM_YEARS
from chapters.models import Chapter


class ScoreType(models.Model):
    class Meta:
        ordering = [
            "name",
        ]

    class SECTION(Enum):
        bro = ("Bro", "Brotherhood")
        ops = ("Ops", "Operate")
        pro = ("Pro", "Professional")
        ser = ("Ser", "Service")

        @classmethod
        def get_value(cls, member):
            return cls[member.lower()].value[1]

    class TYPES(Enum):
        evt = ("Evt", "Event")
        sub = ("Sub", "Submit")
        spe = ("Spe", "Special")

        @classmethod
        def get_value(cls, member):
            return cls[member.lower()].value[1]

    name = models.CharField(max_length=50)
    description = models.CharField(max_length=200)
    section = models.CharField(max_length=3, choices=[x.value for x in SECTION])
    points = models.PositiveIntegerField(
        default=0, help_text="Total number of points possible in year"
    )
    term_points = models.PositiveIntegerField(
        default=0, help_text="Total number of points possible in term"
    )
    formula = models.CharField(
        max_length=200, help_text="Formula for calculating score"
    )
    slug = models.SlugField(unique=True)  # name_short
    type = models.CharField(max_length=3, choices=[x.value for x in TYPES])
    base_points = models.FloatField(default=0)
    attendance_multiplier = models.FloatField(default=0)
    member_add = models.FloatField(default=0)
    stem_add = models.FloatField(default=0)
    alumni_add = models.FloatField(default=0)
    guest_add = models.FloatField(default=0)
    special = models.CharField(max_length=200)

    def __str__(self):
        return f"{self.name}"  # : {self.description}"

    def chapter_events(self, chapter, date=None):
        if date is None:
            qs = self.events.filter(chapter=chapter).all()
        else:
            date_start, date_end = YearTermModel.date_range(date)
            qs = self.events.filter(
                chapter=chapter, date__gt=date_start, date__lt=date_end
            ).all()
        return qs

    def chapter_submissions(self, chapter, date=None):
        if date is None:
            qs = self.submissions.filter(chapter=chapter).all()
        else:
            date_start, date_end = YearTermModel.date_range(date)
            qs = self.submissions.filter(
                chapter=chapter, date__gt=date_start, date__lt=date_end
            ).all()
        return qs

    def chapter_score(self, chapter, date=None):
        """
        :param chapter:
        :return: total (float)
        """
        total = 0
        if self.type == "Evt":
            # Filter events for chapter
            events = self.chapter_events(chapter, date=date)
            total = events.aggregate(Sum("score"))["score__sum"]
        elif self.type == "Sub":
            # Filter submissions for chapter
            submissions = self.chapter_submissions(chapter, date=date)
            total = submissions.aggregate(Sum("score"))["score__sum"]
        elif self.type == "Spe":
            pass
        if total is None:
            total = 0
        return round(min(total, self.term_points), 2)

    @classmethod
    def annotate_chapter_score(cls, chapter, start_year=None, qs=None):
        if qs is None:
            qs = cls.objects.all()
        if start_year is None:
            start_year = BIENNIUM_YEARS[0]
        start_year = int(start_year)
        scores_values = qs.filter(
            chapters__chapter=chapter,
            chapters__year__gte=start_year,
            chapters__year__lte=start_year + 2,
        ).values("chapters__year", "chapters__score", "chapters__term", "id")
        score_values_ids = set(scores_values.values_list("id", flat=True))
        score_types = qs.all().values(
            "type", "points", "section", "description", "name", "slug", "id"
        )
        score_types_out = []
        for score_info in score_types:
            if score_info["id"] in score_values_ids:
                for score_value in scores_values.filter(id=score_info["id"]):
                    year = score_value["chapters__year"] - start_year
                    term = score_value["chapters__term"]
                    # if year = 0 or 2 continue
                    offset = {0: 1, 2: 4}
                    if year in offset:
                        if year == 0 and term == "sp":
                            continue
                        offset = offset[year]
                    else:
                        offset = {"fa": 3, "sp": 2}[term]
                    score_info[f"score{offset}"] = score_value["chapters__score"]
            total = 0.0
            for key in ["score1", "score2", "score3", "score4"]:
                if key not in score_info:
                    score_info[key] = 0.0
                else:
                    total += score_info[key]
            score_info["total"] = total
            score_types_out.append(score_info)
        return score_types_out

    def calculate_special(self, obj, extra_info=None):
        formula_out = self.special
        calcualted_elsewhere = [
            "HOURS",
            "GPA",
            "MEMBERS",
            "PLEDGE",
            "OFFICER",
        ]
        if any(x in formula_out for x in calcualted_elsewhere):
            # All these should be calculated somewhere else
            formula_out = 0
            return formula_out
        # We do not create dict/list to loop and do this
        # b/c obj may not contain info
        if "GUESTS" in formula_out:
            formula_out = formula_out.replace("GUESTS", str(obj.guests))
        if "HOST" in formula_out:
            formula_out = formula_out.replace("HOST", str(obj.host))
        if "MILES" in formula_out:
            formula_out = formula_out.replace("MILES", str(obj.miles))
        if "memberATT" in formula_out:
            actives = obj.chapter.get_actives_for_date(obj.date).count()
            # obj.date  # get_semester
            percent_attendance = 0
            if actives:
                percent_attendance = min(obj.members / actives, 1)
            formula_out = formula_out.replace("memberATT", str(percent_attendance))
        if "MEETINGS" in formula_out:
            return obj.calculate_meeting_attendance(obj.chapter, obj.date)
        if "MODIFIED" in formula_out:
            # 20*UNMODIFIED+10*MODIFIED
            if extra_info is not None:
                unmodified = extra_info.get("unmodified", False)
            else:
                unmodified = True
            if unmodified:
                unmod = 1
                mod = 0
            else:
                unmod = 0
                mod = 1
            formula_out = formula_out.replace("UNMODIFIED", str(unmod))
            formula_out = formula_out.replace("MODIFIED", str(mod))
        return round(eval(formula_out), 2)

    def calculate_score(self, obj, extra_info=None):
        total_score = 0
        if self.special and self.special != "0":
            return self.calculate_special(obj, extra_info=extra_info)
        # Some events have base points just for having event
        total_score += self.base_points
        if self.type == "Evt":
            total_score += obj.members * self.member_add
            actives = obj.chapter.get_actives_for_date(obj.date).count()
            # obj.date  # get_semester
            percent_attendance = 0
            if actives:
                percent_attendance = min(obj.members / actives, 1)
            attendance_points = percent_attendance * self.attendance_multiplier
            total_score += attendance_points
            # filter users for alumni
            total_score += obj.alumni * self.alumni_add
            total_score += obj.guests * self.guest_add
            total_score += obj.stem * self.stem_add
        return round(total_score, 2)

    def update_chapter_score(self, chapter, date):
        """
        This should be separate from calculate_score b/c it needs to include
        the score that is being calculated after the save of that obj
        :param chapter:
        :param date:
        :return:
        """
        term = ScoreChapter.get_term(date)
        year = date.year
        term_opp_options = {"sp": "fa", "fa": "sp"}
        # if current fall, next spring
        year_opp = year + 1
        term_opp = term_opp_options[term]
        month = 3
        if term == "sp":
            # if current spring term, last fall
            year_opp = year - 1
            month = 10
        score = self.chapter_score(chapter, date)
        date_opp = datetime.date(year_opp, month, 1)
        score_opp = self.chapter_score(chapter, date_opp)
        # the score is the term score
        #   max for year is the self.points
        #   max for semester is self.term_points
        total_points_year = score + score_opp
        if total_points_year > self.points:
            # Some scores allow all points to be earned in one semester
            # should not go over max for year
            # eg. if max is 100, 60 in fall and 80 in spring
            #       will allow 60 in fall and sum-max
            #           spring = max - fall
            #           spring = 100 - 60 = 40
            if term == "sp":
                # the current spring semester will be limited
                limited_points = self.points - score_opp
                score = limited_points
            else:
                limited_points = self.points - score
                score_opp = limited_points
        try:
            score_chapter = self.chapters.get(chapter=chapter, year=year, term=term)
        except ScoreChapter.DoesNotExist:
            score_chapter = ScoreChapter(
                chapter=chapter, type=self, year=year, term=term
            )
        score_chapter.score = score
        score_chapter.save()
        try:
            score_chapter_opp = self.chapters.get(
                chapter=chapter, year=year_opp, term=term_opp
            )
        except ScoreChapter.DoesNotExist:
            score_chapter_opp = ScoreChapter(
                chapter=chapter, type=self, year=year_opp, term=term_opp
            )
        score_chapter_opp.score = score_opp
        score_chapter_opp.save()


class ScoreChapter(YearTermModel):
    class Meta:
        unique_together = ("term", "year", "type", "chapter")

    chapter = models.ForeignKey(
        Chapter, related_name="scores", on_delete=models.CASCADE
    )
    type = models.ForeignKey(
        ScoreType, on_delete=models.PROTECT, related_name="chapters"
    )
    score = models.FloatField(default=0)

    @classmethod
    def type_score_biennium(cls, date=None, chapters=None):
        if date is None:
            query = cls.objects.filter(year__gte=BIENNIUM_YEARS[0]).exclude(
                year=BIENNIUM_YEARS[0], term="sp"
            )
        else:
            term = ScoreChapter.get_term(date)
            query = cls.objects.filter(year=date.year, term=term)
        if chapters is None:
            chapters = Chapter.objects.exclude(active=False)
        scores = (
            query.filter(chapter__in=chapters)
            .values("chapter", "type__section")
            .annotate(
                section_score=Round(models.Sum("score")),
                region=models.F("chapter__region__name"),
                chapter_name=models.F("chapter__name"),
            )
            .order_by("chapter_name")
        )
        grouped_scores = {}
        for score in scores:
            chapter = score["chapter"]
            score[f"{score.pop('type__section')}"] = score.pop("section_score")
            chapter_dict = grouped_scores.get(
                chapter, {"Bro": 0, "Ops": 0, "Ser": 0, "Pro": 0}
            )
            chapter_dict.update(score)
            grouped_scores[chapter] = chapter_dict
        for chapter, score in grouped_scores.items():
            grouped_scores[chapter]["total"] = round(
                score["Bro"] + score["Ops"] + score["Ser"] + score["Pro"], 2
            )
        return grouped_scores.values()

    def update_score(self):
        date = self.get_date()
        score_val = self.type.chapter_score(self.chapter, date)
        self.score = score_val
        self.save()
