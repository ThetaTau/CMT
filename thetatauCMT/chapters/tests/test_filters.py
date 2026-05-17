import pytest
from pytest_django.asserts import assertQuerySetEqual
from thetatauCMT.chapters.models import Chapter
from thetatauCMT.regions.models import Region


@pytest.mark.django_db
def test_chapter_list_filter(chapter_factory):
    chapters = chapter_factory.create_batch(10)
    candidate_chapters = chapter_factory.create_batch(10, candidate_chapter=True)
    from thetatauCMT.chapters.filters import ChapterListFilter

    all_chapters = chapters + candidate_chapters
    chapter_pks = {chapter.pk for chapter in all_chapters}
    qs = Chapter.objects.all()
    filter_default = ChapterListFilter(queryset=qs)
    assertQuerySetEqual(filter_default.qs, chapter_pks, lambda o: o.pk, ordered=False)
    filter_national = ChapterListFilter({"region": "national"}, queryset=qs)
    assertQuerySetEqual(filter_national.qs, chapter_pks, lambda o: o.pk, ordered=False)
    filter_candidate_chapter = ChapterListFilter(
        {"region": "candidate_chapter"}, queryset=qs
    )
    candidate_chapter_pks = {
        chapter.pk for chapter in candidate_chapters if chapter.candidate_chapter
    }
    assertQuerySetEqual(
        filter_candidate_chapter.qs,
        candidate_chapter_pks,
        lambda o: o.pk,
        ordered=False,
    )
    # Per-region filtering depends on Region.region_choices being evaluated dynamically
    # which requires the filter choices to be refreshed per FilterSet instantiation.
