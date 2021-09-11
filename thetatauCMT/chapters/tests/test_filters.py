import pytest
from pytest_django.asserts import assertQuerysetEqual
from chapters.models import Chapter
from regions.models import Region


@pytest.mark.django_db
def test_chapter_list_filter(chapter_factory):
    chapters = chapter_factory.create_batch(10)
    candidate_chapters = chapter_factory.create_batch(10, candidate_chapter=True)
    from chapters.filters import ChapterListFilter

    all_chapters = chapters + candidate_chapters
    chapter_pks = {chapter.pk for chapter in all_chapters}
    qs = Chapter.objects.all()
    filter_default = ChapterListFilter(queryset=qs)
    assertQuerysetEqual(filter_default.qs, chapter_pks, lambda o: o.pk, ordered=False)
    filter_national = ChapterListFilter({"region": "national"}, queryset=qs)
    assertQuerysetEqual(filter_national.qs, chapter_pks, lambda o: o.pk, ordered=False)
    filter_candidate_chapter = ChapterListFilter(
        {"region": "candidate_chapter"}, queryset=qs
    )
    candidate_chapter_pks = {
        chapter.pk for chapter in candidate_chapters if chapter.candidate_chapter
    }
    assertQuerysetEqual(
        filter_candidate_chapter.qs,
        candidate_chapter_pks,
        lambda o: o.pk,
        ordered=False,
    )
    regions = Region.objects.all()
    for region in regions:
        filter_region = ChapterListFilter({"region": region.slug}, queryset=qs)
        region_pks = {
            chapter.pk for chapter in all_chapters if chapter.region.slug == region.slug
        }
        assertQuerysetEqual(filter_region.qs, region_pks, lambda o: o.pk, ordered=False)
