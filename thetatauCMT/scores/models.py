from enum import Enum
from django.db import models
from django.db.models import Sum
from core.models import YearTermModel
from chapters.models import Chapter


class ScoreType(models.Model):
    class Meta:
        ordering = ['name', ]

    class SECTION(Enum):
        brotherhood = ('Bro', 'Brotherhood')
        operate = ('Ops', 'Operate')
        professional = ('Pro', 'Professional')
        service = ('Ser', 'Service')

        @classmethod
        def get_value(cls, member):
            return cls[member].value[0]

    class TYPES(Enum):
        event = ('Evt', 'Event')
        submit = ('Sub', 'Submit')
        special = ('Spe', 'Special')

        @classmethod
        def get_value(cls, member):
            return cls[member].value[0]

    name = models.CharField(max_length=50)
    description = models.CharField(max_length=200)
    section = models.CharField(
        max_length=3,
        choices=[x.value for x in SECTION]
    )
    points = models.PositiveIntegerField(
        default=0,
        help_text="Total number of points possible in year")
    term_points = models.PositiveIntegerField(
        default=0,
        help_text="Total number of points possible in term")
    formula = models.CharField(max_length=200,
                               help_text="Formula for calculating score")
    slug = models.SlugField(unique=True)  # name_short
    type = models.CharField(
        max_length=3,
        choices=[x.value for x in TYPES]
    )
    base_points = models.FloatField(default=0)
    attendance_multiplier = models.FloatField(default=0)
    member_add = models.FloatField(default=0)
    stem_add = models.FloatField(default=0)
    alumni_add = models.FloatField(default=0)
    guest_add = models.FloatField(default=0)
    special = models.CharField(max_length=200)

    def __str__(self):
        return f"{self.name}"  # : {self.description}"

    def chapter_events(self, chapter):
        return self.events.filter(chapter=chapter).all()

    def chapter_score(self, chapter):
        """
        :param chapter:
        :return: total (float)
        """
        total = 0
        if self.type == "Evt":
            # Filter events for chapter
            events = self.chapter_events(chapter)
            total = events.aggregate(Sum('score'))['score__sum']
        elif self.type == "Sub":
            # Filter submissions for chapter
            submissions = self.submissions.filter(chapter=chapter).all()
            total = submissions.aggregate(Sum('score'))['score__sum']
        elif self.type == "Spe":
            pass
        if total is None:
            total = 0
        return total

    def calculate_special(self, obj):
        formula_out = self.special
        calcualted_elsewhere = [
            'HOURS', 'GPA', 'MEMBERS',
            'PLEDGE', 'OFFICER', 'MODIFIED',
        ]
        if any(x in formula_out for x in calcualted_elsewhere):
            # All these should be calculated somewhere else
            formula_out = 0
        # We do not create dict/list to loop and do this
        # b/c obj may not contain info
        if 'GUESTS' in formula_out:
            formula_out.replace('GUESTS', obj.guests)
        if 'HOST' in formula_out:
            formula_out.replace('HOST', obj.host)
        if 'MILES' in formula_out:
            formula_out.replace('MILES', obj.miles)
        if 'memberATT' in formula_out:
            formula_out.replace('memberATT', 0)
        if 'MEETINGS' in formula_out:
            meeting_attend = obj.calculate_meeting_attendance()
            formula_out.replace('MEETINGS', meeting_attend)
        return eval(formula_out)

    def calculate_score(self, obj):
        total_score = 0
        if self.special:
            return self.calculate_special(obj)
        # Some events have base points just for having event
        total_score += self.base_points
        if self.type == 'Evt':
            # filter users for active/pnm
            total_score += len(obj.users) * self.member_add
            # obj.date  # get_semester
            percent_attendance = 0  # needs to be calculated
            attendance_points = percent_attendance * self.attendance_multiplier
            total_score += attendance_points
            # filter users for alumni
            total_score += len(obj.users) * self.alumni_add
            total_score += obj.guests * self.guest_add
            total_score += obj.stem * self.stem_add
        return total_score


class ScoreChapter(YearTermModel):
    chapter = models.ForeignKey(Chapter, related_name="scores",
                                on_delete=models.CASCADE)
    type = models.ForeignKey(ScoreType,
                             on_delete=models.PROTECT,
                             related_name="chapters")
    score = models.FloatField(default=0)
