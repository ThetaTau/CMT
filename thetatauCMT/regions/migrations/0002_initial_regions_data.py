# Generated by Django 2.0.3 on 2018-06-14 20:52

from django.db import migrations


def load_regions(apps, schema_editor):
    region = apps.get_model("regions", "Region")
    region_test = region(id=1, name='Test', email='test@thetatau.org',
                         website='www.thetatau.org',
                         facebook="https://www.facebook.com/thetatau/")
    region_test.save()
    region_west = region(id=2, name='Western', email='werd@thetatau.org',
                         website='http://thetatauwestregion.org',
                         facebook="https://www.facebook.com/groups/ThetaTauWestRegion/")
    region_west.save()
    region_atlantic = region(id=3, name='Atlantic', email='ard@thetatau.org',
                             website="http://thetatau.org/atlantic-region",
                             facebook="https://www.facebook.com/groups/OTAtlantic")
    region_atlantic.save()
    region_central = region(id=4, name='Central', email='crd@thetatau.org',
                            website="http://thetatau.org/central-region",
                            facebook="https://www.facebook.com/groups/ThetaTauCentralRegion")
    region_central.save()
    region_great_lakes = region(id=5, name='Great Lakes', email='glrd@thetatau.org',
                                website="http://thetatau.org/great-lakes-region",
                                facebook="https://www.facebook.com/groups/854659084574228")
    region_great_lakes.save()
    region_gulf = region(id=6, name='Gulf', email='gulfrd@thetatau.org',
                         website="http://thetatau.org/gulf-region",
                         facebook="https://www.facebook.com/groups/TTgulfregion")
    region_gulf.save()
    region_midwest = region(id=7, name='Midwest', email='mwrd@thetatau.org',
                            website="http://thetatau.org/midwest-region",
                            facebook="https://www.facebook.com/groups/ThetaTauMidwest/")
    region_midwest.save()
    region_northeast = region(id=8, name='Northeast',
                              email='northeastRD@thetatau.org',
                              website="http://thetatau.org/northeast-region",
                              facebook="https://www.facebook.com/groups/thetataunortheast")
    region_northeast.save()
    region_southeast = region(id=9, name='Southeast',
                              email='southeastrd@thetatau.org',
                              website="http://thetatau.org/southeast-region",
                              facebook="www.facebook.com/groups/ThetaTau.Southeast")
    region_southeast.save()


class Migration(migrations.Migration):

    dependencies = [
        ('regions', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(load_regions),
    ]
