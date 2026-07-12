import datetime
from collections import defaultdict
from enum import Enum

from django.db import models
from django.db.models import Sum
from django.db.models.functions import Round

from core.models import BIENNIUM_YEARS, YearTermModel
from thetatauCMT.chapters.models import Chapter


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
    points = models.PositiveIntegerField(default=0, help_text="Total number of points possible in year")
    term_points = models.PositiveIntegerField(default=0, help_text="Total number of points possible in term")
    formula = models.CharField(max_length=200, help_text="Formula for calculating score")
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
            # Half-open [start, end) so an event on the exact semester boundary
            # (Jul 1 / Jan 1) is counted in exactly one semester, never dropped.
            qs = self.events.filter(chapter=chapter, date__gte=date_start, date__lt=date_end).all()
        return qs

    def chapter_submissions(self, chapter, date=None):
        if date is None:
            qs = self.submissions.filter(chapter=chapter).all()
        else:
            date_start, date_end = YearTermModel.date_range(date)
            # Half-open [start, end) so a submission on the exact semester
            # boundary is counted in exactly one semester, never dropped.
            qs = self.submissions.filter(chapter=chapter, date__gte=date_start, date__lt=date_end).all()
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
        # A biennium has four scored terms; map each (year, term) to a column.
        # Spring of the start year and Fall of the final year belong to the
        # neighboring biennia and are intentionally left out.
        biennium_slots = {
            (start_year, "fa"): "score1",
            (start_year + 1, "sp"): "score2",
            (start_year + 1, "fa"): "score3",
            (start_year + 2, "sp"): "score4",
        }
        # Pull every chapter score for this chapter in one query and bucket it
        # by score type id and biennium column.
        scores_by_type = defaultdict(dict)
        chapter_scores = qs.filter(
            chapters__chapter=chapter,
            chapters__year__gte=start_year,
            chapters__year__lte=start_year + 2,
        ).values("id", "chapters__year", "chapters__term", "chapters__score")
        for row in chapter_scores:
            slot = biennium_slots.get((row["chapters__year"], row["chapters__term"]))
            if slot is not None:
                scores_by_type[row["id"]][slot] = row["chapters__score"]
        score_types_out = []
        for score_info in qs.values("type", "points", "section", "description", "name", "slug", "id"):
            slot_scores = scores_by_type.get(score_info["id"], {})
            total = 0.0
            for slot in ("score1", "score2", "score3", "score4"):
                value = slot_scores.get(slot, 0.0)
                score_info[slot] = value
                total += value
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
        # Each term is already capped at self.term_points by chapter_score.
        # An academic year is a Fall term plus the following Spring term, and the
        # two together may not exceed self.points. Fall keeps its full value and
        # Spring is trimmed to whatever room is left (never below zero). This is
        # symmetric, so the stored values are stable no matter which term is saved.
        if term == "fa":
            fall_score, spring_score = score, score_opp
        else:
            fall_score, spring_score = score_opp, score
        if fall_score + spring_score > self.points:
            spring_score = max(self.points - fall_score, 0)
        if term == "fa":
            score, score_opp = fall_score, spring_score
        else:
            score, score_opp = spring_score, fall_score
        try:
            score_chapter = self.chapters.get(chapter=chapter, year=year, term=term)
        except ScoreChapter.DoesNotExist:
            score_chapter = ScoreChapter(chapter=chapter, type=self, year=year, term=term)
        score_chapter.score = score
        score_chapter.save()
        try:
            score_chapter_opp = self.chapters.get(chapter=chapter, year=year_opp, term=term_opp)
        except ScoreChapter.DoesNotExist:
            score_chapter_opp = ScoreChapter(chapter=chapter, type=self, year=year_opp, term=term_opp)
        score_chapter_opp.score = score_opp
        score_chapter_opp.save()


class ScoreChapter(YearTermModel):
    class Meta:
        unique_together = ("term", "year", "type", "chapter")

    chapter = models.ForeignKey(Chapter, related_name="scores", on_delete=models.CASCADE)
    type = models.ForeignKey(ScoreType, on_delete=models.PROTECT, related_name="chapters")
    score = models.FloatField(default=0)

    @classmethod
    def type_score_biennium(cls, date=None, chapters=None):
        if date is None:
            query = cls.objects.filter(year__gte=BIENNIUM_YEARS[0]).exclude(year=BIENNIUM_YEARS[0], term="sp")
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
            chapter_dict = grouped_scores.get(chapter, {"Bro": 0, "Ops": 0, "Ser": 0, "Pro": 0})
            chapter_dict.update(score)
            grouped_scores[chapter] = chapter_dict
        for chapter, score in grouped_scores.items():
            grouped_scores[chapter]["total"] = round(score["Bro"] + score["Ops"] + score["Ser"] + score["Pro"], 2)
        return grouped_scores.values()

    def update_score(self):
        # Delegate to the single source of truth so the same term + year caps
        # are applied everywhere a chapter score is (re)computed.
        self.type.update_chapter_score(self.chapter, self.get_date())
        self.refresh_from_db()
