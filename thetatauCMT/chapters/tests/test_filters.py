import pytest
from pytest_django.asserts import assertQuerysetEqual
from chapters.models import Chapter
from regions.models import Region


@pytest.mark.django_db
def test_chapter_list_filter(chapter_factory):
    chapters = chapter_factory.create_batch(10)
    colonies = chapter_factory.create_batch(10, colony=True)
    from chapters.filters import ChapterListFilter

    all_chapters = chapters + colonies
    chapter_pks = {chapter.pk for chapter in all_chapters}
    qs = Chapter.objects.all()
    filter_default = ChapterListFilter(queryset=qs)
    assertQuerysetEqual(filter_default.qs, chapter_pks, lambda o: o.pk, ordered=False)
    filter_national = ChapterListFilter({"region": "national"}, queryset=qs)
    assertQuerysetEqual(filter_national.qs, chapter_pks, lambda o: o.pk, ordered=False)
    filter_colony = ChapterListFilter({"region": "colony"}, queryset=qs)
    colony_pks = {chapter.pk for chapter in colonies if chapter.colony}
    assertQuerysetEqual(filter_colony.qs, colony_pks, lambda o: o.pk, ordered=False)
    regions = Region.objects.all()
    for region in regions:
        filter_region = ChapterListFilter({"region": region.slug}, queryset=qs)
        region_pks = {
            chapter.pk for chapter in all_chapters if chapter.region.slug == region.slug
        }
        assertQuerysetEqual(filter_region.qs, region_pks, lambda o: o.pk, ordered=False)
