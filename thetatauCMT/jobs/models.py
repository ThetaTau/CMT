import os
from django.db import models
from django.template.defaultfilters import slugify
from django.utils import timezone
from django_userforeignkey.models.fields import UserForeignKey
from django.db.models.manager import BaseManager
from django.utils.translation import gettext_lazy as _
from multiselectfield import MultiSelectField
from ckeditor_uploader.fields import RichTextUploadingField
from core.models import TimeStampedModel, EnumClass
from address.models import (
    Locality,
    Country,
)


class Keyword(models.Model):
    name = models.CharField(max_length=1000)

    def __str__(self):
        return self.name


class Major(models.Model):
    name = models.CharField(max_length=1000)

    def __str__(self):
        return self.name


def get_job_attachment_upload_path(instance, filename):  # instance refers to object
    return os.path.join(
        "jobs-attachments",
        f"{instance.created_by.chapter.slug}",  # name of chapter
        f"{instance.slug}-{filename}",  # name of file submitted
    )


class Job(TimeStampedModel):
    class JOB_TYPE(EnumClass):
        intern = ("intern", "Internship")
        coop = ("coop", "Co-op")
        full_time = ("full_time", "Full Time")
        part_time = ("part_time", "Part Time")
        contractor = ("contractor", "Contractor")

    class JOB_EXPERIENCE(EnumClass):
        in_school = ("in_school", "In School")
        new_grad = ("new_grad", "New Grad")
        less_than_one = ("less_than_one", "1 < years")
        less_than_five = ("less_than_five", "1 < years < 5")
        less_than_ten = ("less_than_ten", "5 < years < 10")
        less_than_fifteen = ("less_than_fifteen", "10 < years < 15")
        less_than_twenty = ("less_than_twenty", "15 < years < 20")
        twenty_plus = ("twenty_plus", "20 < years")

    class EDUCATION_QUALIFICATION(EnumClass):
        highschool = ("highschool", "High School")
        bachelors = ("bachelors", "Bachelors")
        masters = ("masters", "Masters")
        phd = ("phd", "PhD")

    class LOCATION(EnumClass):
        on_site = ("on_site", "On Site")
        hybrid = ("hybrid", "Hybrid")
        flexible = ("flexible", "Flexible")
        dedicated_office = ("dedicated_office", "Dedicated Office")
        remote = ("remote", "Remote")

    CONTACT_CHOICES = (
        (
            True,
            "Yes, please reach out. Your name and email will show on the job listing.",
        ),
        (
            False,
            "No, contact the job posting only. Your name and email will NOT show on the job listing",
        ),
    )
    contact = models.BooleanField(
        verbose_name="Contact",
        default=True,
        choices=CONTACT_CHOICES,
        help_text="Are you available to answer questions about the job?",
    )
    other_contact = models.CharField(
        _("Other Contact"),
        max_length=1000,
        blank=True,
        null=True,
        help_text="Is there another contact email or phone number for this job listing?",
    )
    company = models.CharField(_("Company Name"), max_length=255)
    description = RichTextUploadingField(
        help_text="No need to copy the entire job post, please share most relevant details "
        "or anything else to help job searchers"
    )
    education_qualification = MultiSelectField(
        max_length=255,
        choices=[x.value for x in EDUCATION_QUALIFICATION],
        help_text="What education is needed for this job?",
    )
    experience = MultiSelectField(
        max_length=255,
        choices=[x.value for x in JOB_EXPERIENCE],
        help_text="What experience is needed for this job?",
    )
    job_type = MultiSelectField(
        max_length=255,
        choices=[x.value for x in JOB_TYPE],
    )
    location_type = MultiSelectField(
        max_length=255, choices=[x.value for x in LOCATION]
    )
    publish_end = models.DateField(
        default=timezone.now,
        help_text="When the job post should NO LONGER be available for job searchers.",
    )
    publish_start = models.DateField(
        default=timezone.now,
        help_text="When the job post should be available for job searchers.",
    )
    slug = models.SlugField(_("Slug"), max_length=255, unique=True, blank=True)
    SPONSORED_CHOICES = (
        (True, "This job posting was sponsored by a company"),
        (False, "This job posting was created/shared by a member"),
    )
    sponsored = models.BooleanField(
        _("Sponsored"),
        choices=SPONSORED_CHOICES,
        default=False,
        help_text="Is the job posting sponsored by a company?",
    )
    title = models.CharField(_("Title"), max_length=255)
    url = models.URLField(
        help_text="What is the link for more information about the job?"
    )
    priority = models.IntegerField(
        verbose_name="Priority order, 1 highest",
        help_text="The order you want Jobs to appear in, "
        "1 will be on top. Sorted by priority and then reverse published start date",
        default=10,
        choices=list(zip(range(1, 11), range(1, 11))),
        unique=False,
    )
    created_by = UserForeignKey(
        auto_user_add=True,
        verbose_name="The user that created this object",
        related_name="jobs_created",
    )
    keywords = models.ManyToManyField(
        Keyword,
        related_name="jobs",
        default=None,
        blank=True,
        help_text="Keywords to help job searchers find this job",
    )
    MAJOR_CHOICES = (
        (True, "Yes, listed below"),
        (False, "No, job posting is open to any and all majors"),
    )
    majors_specific = models.BooleanField(
        _("Specific Majors"),
        choices=MAJOR_CHOICES,
        default=False,
        help_text="Are there specific majors this job listing is targeted for?",
    )
    majors = models.ManyToManyField(
        Major,
        related_name="jobs",
        default=None,
        blank=True,
        help_text="If the job posting is for specific majors only, what are those majors?",
    )
    location = models.ManyToManyField(
        Locality,
        related_name="jobs",
        help_text="What is the location of the main office even if the job is remote.",
    )
    country = models.ForeignKey(
        Country, null=True, related_name="jobs", on_delete=models.CASCADE
    )
    attachment = models.FileField(
        upload_to=get_job_attachment_upload_path, null=True, blank=True
    )

    class Meta:
        ordering = ["priority", "-publish_start"]
        verbose_name = "Job"

    def __unicode__(self):
        return "Job: %s" % self.title

    def save(self, *args, **kwargs):
        if not self.id:
            self.slug = slug = slugify(self.title)
            counter = 1
            while self.__class__.objects.filter(slug=self.slug).exists():
                self.slug = "{0}-{1}".format(slug, counter)
            counter += 1
        return super().save(*args, **kwargs)


class JobSearch(TimeStampedModel):
    class NOTIFICATION(EnumClass):
        none = ("none", "Get no notification emails on matching jobs.")
        immediate = (
            "immediate",
            "Get notified immediately of a new matching job.",
        )
        daily = (
            "daily",
            "Get a daily email digests of new matching jobs.",
        )
        weekly = (
            "weekly",
            "Get a weekly email digests of new matching jobs.",
        )

    class FILTER(EnumClass):
        include = ("include", "Must match")
        optional = ("optional", "Optionally match")
        exclude = ("exclude", "Does not match")

    search_title = models.CharField(_("Search Name"), max_length=255)
    search_description = models.CharField(
        _("Search Description"),
        max_length=255,
        help_text="Provide a short description to help you remember this search",
    )
    CONTACT_CHOICES = (
        (None, "Any"),
        (True, "Yes"),
        (False, "No"),
    )
    contact = models.BooleanField(
        verbose_name="Contact",
        default=None,
        null=True,
        blank=True,
        choices=CONTACT_CHOICES,
        help_text="Is there a contact for the job?",
    )
    contact_filter = models.CharField(
        max_length=20,
        choices=[x.value for x in FILTER],
        default="include",
    )
    company = models.CharField(
        _("Company Name Contains"),
        help_text="Contains search, leave blank to not search on this field",
        max_length=255,
        null=True,
        blank=True,
    )
    company_filter = models.CharField(
        max_length=20,
        choices=[x.value for x in FILTER],
        default="include",
    )
    description = models.CharField(
        _("Description Contains"),
        help_text="Contains search, leave blank to not search on this field",
        max_length=255,
        null=True,
        blank=True,
    )
    description_filter = models.CharField(
        max_length=20,
        choices=[x.value for x in FILTER],
        default="include",
    )
    education_qualification = MultiSelectField(
        max_length=255,
        choices=[
            (None, "Any"),
        ]
        + [x.value for x in Job.EDUCATION_QUALIFICATION],
        help_text="What education is needed for this job?",
        null=True,
        blank=True,
        default=None,
    )
    education_filter = models.CharField(
        max_length=20,
        choices=[x.value for x in FILTER],
        default="include",
    )
    experience = MultiSelectField(
        max_length=255,
        choices=[
            (None, "Any"),
        ]
        + [x.value for x in Job.JOB_EXPERIENCE],
        help_text="What experience is needed for this job?",
        null=True,
        blank=True,
        default=None,
    )
    experience_filter = models.CharField(
        max_length=20,
        choices=[x.value for x in FILTER],
        default="include",
    )
    job_type = MultiSelectField(
        max_length=255,
        choices=[
            (None, "Any"),
        ]
        + [x.value for x in Job.JOB_TYPE],
        null=True,
        blank=True,
        default=None,
    )
    job_type_filter = models.CharField(
        max_length=20,
        choices=[x.value for x in FILTER],
        default="include",
    )
    location_type = MultiSelectField(
        max_length=255,
        choices=[
            (None, "Any"),
        ]
        + [x.value for x in Job.LOCATION],
        null=True,
        blank=True,
        default=None,
    )
    location_type_filter = models.CharField(
        max_length=20,
        choices=[x.value for x in FILTER],
        default="include",
    )
    SPONSORED_CHOICES = (
        (None, "Any"),
        (True, "Yes"),
        (False, "No"),
    )
    sponsored = models.BooleanField(
        _("Sponsored"),
        choices=SPONSORED_CHOICES,
        default=None,
        help_text="Is the job posting sponsored by a company?",
        null=True,
        blank=True,
    )
    sponsored_filter = models.CharField(
        max_length=20,
        choices=[x.value for x in FILTER],
        default="include",
    )
    title = models.CharField(
        _("Title Contains"),
        help_text="Contains search, leave blank to not search on this field",
        max_length=255,
        null=True,
        blank=True,
    )
    title_filter = models.CharField(
        max_length=20,
        choices=[x.value for x in FILTER],
        default="include",
    )
    created_by = UserForeignKey(
        auto_user_add=True,
        verbose_name="The user that created this object",
        related_name="job_searches_created",
    )
    keywords = models.ManyToManyField(
        Keyword,
        related_name="job_searches",
        default=None,
        blank=True,
        help_text="Keywords to help job searchers find this job",
    )
    keywords_filter = models.CharField(
        max_length=20,
        choices=[x.value for x in FILTER],
        default="include",
    )
    majors = models.ManyToManyField(
        Major,
        related_name="job_searches",
        default=None,
        blank=True,
        help_text="Majors to search for",
    )
    majors_filter = models.CharField(
        max_length=20,
        choices=[x.value for x in FILTER],
        default="include",
    )
    location = models.ManyToManyField(
        Locality,
        related_name="job_searches",
        help_text="What is the location of jobs",
        blank=True,
        default=None,
    )
    location_filter = models.CharField(
        max_length=20,
        choices=[x.value for x in FILTER],
        default="include",
    )
    country = models.ForeignKey(
        Country,
        null=True,
        related_name="job_searches",
        on_delete=models.CASCADE,
        blank=True,
        default=None,
    )
    country_filter = models.CharField(
        max_length=20,
        choices=[x.value for x in FILTER],
        default="include",
    )
    notification = models.CharField(
        verbose_name="Do you want to be notified of matching new jobs?",
        max_length=20,
        choices=[x.value for x in NOTIFICATION],
        default="none",
    )

    class Meta:
        ordering = ["-modified"]
        verbose_name = "Job Search"

    def __unicode__(self):
        return "Job Search: %s" % self.title

    def search(self, queryset):
        ands = models.Q()
        ors = models.Q()
        nots = models.Q()
        for search_obj in [
            ("title_filter", "title", "__icontains"),
            ("description_filter", "description", "__icontains"),
            ("company_filter", "company", "__icontains"),
            ("contact_filter", "contact", ""),
            ("education_filter", "education_qualification", "__contains"),
            ("experience_filter", "experience", "__contains"),
            ("job_type_filter", "job_type", "__contains"),
            ("majors_filter", "majors", "__pk__contains"),
            ("location_type_filter", "location_type", "__contains"),
            ("location_filter", "location", "__pk__contains"),
            ("country_filter", "country", ""),
            ("keywords_filter", "keywords", "__pk__contains"),
        ]:
            operator_name, filter_name, filter_type = search_obj
            filter_val = getattr(self, filter_name)
            operator_val = getattr(self, operator_name)
            if filter_val and isinstance(filter_val, BaseManager):
                filter_val = list(filter_val.values_list("pk", flat=True))
            if filter_val:
                # query_new = models.Q(**{f"{filter_name}{filter_type}": filter_val})
                if not isinstance(filter_val, list):
                    filter_val = [filter_val]
                for filter_val in filter_val:
                    if operator_val == self.FILTER.include.name:
                        ands &= models.Q(**{f"{filter_name}{filter_type}": filter_val})
                    elif operator_val == self.FILTER.optional.name:
                        ors |= models.Q(**{f"{filter_name}{filter_type}": filter_val})
                    elif operator_val == self.FILTER.exclude.name:
                        nots &= ~models.Q(**{f"{filter_name}{filter_type}": filter_val})
        query = ands & ors & nots
        return queryset.filter(query).distinct()
