# Generated by Django 2.0.3 on 2018-07-28 05:24

import os
import datetime
from urllib.request import urlopen
from time import sleep
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify
from django.db import migrations
from django.conf import settings
from django.core.files import File
from django.core.files.temp import NamedTemporaryFile
import googleapiclient

import gspread
from oauth2client.service_account import ServiceAccountCredentials
# from oauth2client import file, client, tools

TODAY = timezone.now()
LAST_SEMESTER = TODAY - timezone.timedelta(days=90)
LAST_YEAR = TODAY - timezone.timedelta(days=365)

# scopes = 'https://www.googleapis.com/auth/spreadsheets.readonly'
# id_file = os.path.join(settings.ROOT_DIR.root, r'secrets/GoogleSheetsClient_id.json')
# id_file_out = os.path.join(settings.ROOT_DIR.root, r'secrets/GoogleSheetsClient_id_out.json')
# store = file.Storage(id_file_out)
# creds = store.get()
# if not creds or creds.invalid:
#     flow = client.flow_from_clientsecrets(id_file, scopes)
#     creds = tools.run_flow(flow, store)
scope = ['https://spreadsheets.google.com/feeds',
         'https://www.googleapis.com/auth/drive']

id_file = os.path.join(settings.ROOT_DIR.root,
                       r'secrets/ChapterManagementTool-b239bceff1a7.json')
creds = ServiceAccountCredentials.from_json_keyfile_name(id_file, scope)

gspread_client = gspread.authorize(creds)

CHAPTER_IDS = {
    "Alpha": ("0B96Hi_WlZHjiVUZtRHhJczQ0TmM", "1oNzRdTXUaN_LviYhfCgsFUgikUl3UQ1RgV9-m1VuORU"),
    "Beta": ("0BzIlA76qsUR1TWpQZk1JeUJuWHc", "1eVavxOIsWrbhyJqg0LgQTjRLaFpW4c3A5kq2MYhWy7Q"),
    "Chi": ("0B_eUBbkPZ9Qzd2NmZHJELU1fNEE", "1zPanW9NKvswsvOvj95zM5kKU3h56z-ah_5JgIEG4TKw"),
    "Chi Beta": ("0B_cLLHe_gZvjRUViRW5ydlpRMGc", "1zIBEXGaXcBv6snGHalkv6GlzMT1L5j6Zk-zw0S6mWEQ"),
    "Chi Delta": ("0B_p653vEwSAPSFZFT2hRY1Y2N1U", "1-yXNs3tAAkf-TZ4p8yvSZbKVm4nPpYkOYn630fLY6Ug"),
    "Chi Gamma": ("0BwNO6p4U9sxJUGFOQTdSbmZDUEU", "1NniDu8_oPpTQyiK1Uj1JkGnM0VFMhZDL4NC5Tt3FyuI"),
    "CSLB Colony": ("1NpW6KGpcpSPBnYDwFO0FHRZ2dDQiZds3", "177qSeQzLuvkSmi2kDatzezhcqRdDihsDGBFj5TXkr_s"),
    "Delta": ("1GChDUGPdvLY_yRgjKna-rkGpXuBvmrSg", "1sdH37J1paTHWYumbfDU-kvY92XosxN1Qcxc_dFlx05c"),
    "Delta Gamma": ("0B81EvQnrid4zQkg0VEViNnZ3d28", "1ymh-1WSvj9y2NSZEvgRrT4f-UQN8VhIQELlJ7Ve1RFw"),
    "Drexel Colony": ("", ""),
    "Epsilon": ("0B6bzpkjAJ36vZkU4NHg3b0hVcXM", "1QNXVdG8M-xAGy_4D0TvxIuNkOJyxddstkdDc8f35fCA"),
    "Epsilon Beta": ("0B_AKLJwJjL1tbGt5Q1lMOWtnOVU", "1diYxOoBkJislYZUb76B0Gh15iTtXGzMieLdwtGTFjT4"),
    "Epsilon Delta": ("0B8bo9I4vIpliV2xrY0RORnB1UkU", "1UTPaZlSJiuChRsjaU6E61lzqMxwwSDqtOpR7ubsUUoM"),
    "Eta": ("1p68UWiYF6GqJoUtXIqJF9qiaxr6dyifA", "1hoP0uVcp_g9b7iSwou0zF-c4BAHoqyRU-o1pjunHrZ4"),
    "Eta Delta": ("0B02twq9wT4BjeTJSNGV5M1RaamM", "1MquhW7kMPeLE_IcPJ9sHNZlYzDhXT2DR1pi8-e7N8Uc"),
    "Eta Epsilon": ("", ""),
    "Eta Gamma": ("10W580h2YuUe2jdPvGxP5RlUCFvEGfUx0", "1rhErsBps5M6Ch42glPgel-VHL6fXVdVYl9_yt3Kp7IQ"),
    "Gamma Beta": ("0B3HIB7Xyc8RFYUstVmgtU2E0eFU", "1efI03Iug-sAnVDnzTC_CiednOlAP-rFer7W-atKY-AE"),
    "Iota Delta": ("0B-G6PAD3IjoLUG9sendBUlJrVms", "12UqwbltCdILJFPVHQeOyy09LISvdUnupQF3mKL1Z79A"),
    "Iota Epsilon": ("1rMXD1z9NmMSagAJV0tVit7jQ67cW8cga", "1K8bHhyklQ1hV-QC4FD8AVZO-QEqJCUeZw_Zset9fPLQ"),
    "Iota Gamma": ("0B_NQLjA1MB4TV0ZXM1plaWszNFk", "1NOaehGmDysFCi4Q2yXasIsIDQjzhc-Ob8Z5As3TWbPA"),
    "Kappa": ("0B7O0i30Wb90VV0pJYm9KSEVJdDQ", "1yLR57R5iVVRWx8mS58agHyvs27XtZJwX4QyXBQYW6H4"),
    "Kappa Beta": ("0BxIGKYA_bdU1SHVETFlyT3N5ajA", "1WzFNh7yELNiH0Atre0fZEfLEkRoZ9XTX17_d6uiAWxs"),
    "Kappa Delta": ("0B5DKELLAEdpkSXpHZVhTOHVCZFE", "118ZzWaZt-6zrBPfYBAxSonMkoDGAIcGe6YRjlx-71_g"),
    "Kappa Epsilon": ("0B47cipovKIL_NnczVXpJQm0xZUk", "1qEWo0lq59imBmjGQhvOuluiLBNSiy3Sbs8dVRidkCpQ"),
    "Kappa Gamma": ("0B1qCv_xPtMV6ejdYRzY4VHBMOEk", "1uGbM0M3j5_WOKtK_U1EZlFSVzcWG9wAwiwt8Qqv8bOc"),
    "Lambda Beta": ("0B7mX4kQV3Z7dc1JZUEI2MFZQbnM", "11KSOAzifLurLUV8aqd7aasXRMgRJSw3uTKOJUiVb0e8"),
    "Lambda Delta": ("0B7fqHPfdQO2fM3N4b084SzFQLTQ", "1IbIIBkp5SGRyriYZzxJdHbDPs9qQTw1eINh7xLjfZDE"),
    "Lambda Epsilon": ("0B-uuEbUjpCglWUZTNk5rNDlWQm8", "1lLwBeZOWMjK-w2hnEsFsrKglLvYvphMuOH3z6I-ln1s"),
    "Lambda Gamma": ("0B1kla2_OPGoqWDRLb0JYV1NsQnM", "1KZsmfkgFX1w55wu1PaesofBaCDun4CIVOwupdAGFXF4"),
    "Mu": ("0By_rxEMR2BGmRWZEMUJleHE0Tmc", "15biUCYABVZMlRuZaqIoCobM4S_EYQqB-DX69f6znDlk"),
    "Mu Delta": ("0B6MHf3CbvkeSbkJ2UENxOEZRRFk", "1O1k2-gbrVJfh6lpy1VEequ7cc4LjvzKTpgfujOtiNnI"),
    "Mu Epsilon": ("1Dfo6H9GBJ5auC2euzG0uiakBByNJt5Jp", "1LS7MLYgaDLGVAERiOAtQHwBpUA5lwyQdD2_ey_0wcKY"),
    "Mu Gamma": ("1nCPJm8sRH9K0RfAttvhwC-yRPlWu4NWo", "1h_yYWCRLS-f1hR0m2Lb2-FubMGMx2pI-TYUZmzRaI2s"),
    "NAU Colony": ("1ohYPPHx4dpFlz0HDn2cUwcffnJsdTHDS", "1uKWsQnvf-zP9PW79uZmhzOKP9e6a0TLTDaEwFh2tQFc"),
    "Nu Delta": ("0B5rWUOlHAaolX0tLQUdMZ1lCdVk", "1H3aejxM2xhfJ7J4zAAZS8cYdQNvbizX1T-OV6ZK5LyU"),
    "Nu Gamma": ("0B28uGJWS2M11SURoRWcwZWlJVU0", "1Zd6tlhJOwI8DROnQznPl7biwb9qoACfYc65FsTFQWlI"),
    "Omega": ("0Bxml_t_faJ4sWElPN2hDZHAtcGc", "1zvdKT3XHyl6HSFy7Dr7PVtCbGQLNiCZ3nRq9WoaImb0"),
    "Omega Beta": ("0B9NIfN3Otsz4N1VRUTdSZWg3ejQ", "1Llz2ff21RNw-8_encUnHBL_wv6OMxiALNjd8wALUgtM"),
    "Omega Delta": ("0B-0rrU3uv1YzVVd5QUNWT2xOa1k", "1Tyu286vI2YRBXS4gGmWuJxhXjc3T2VKGKcdkLq7rrm4"),
    "Omega Gamma": ("0B5tAs996WJoqOHFLVUNUdkhuTlE", "1stNmqu9PZPU3KcgOJ2R3I5dQIXn5HmgNurr_Ovh6AAk"),
    "Omicron": ("0BwuO_OiSMRHGUV9hRWtVOEloMWs", "11Xno05rD534fC-4qjKi3HLHuPh7LsD0PmXNHW_iBcNE"),
    "Omicron Beta": ("0B0bbraFmfwdcYjU3SWFrUjQ5WVk", "1BSj4rq3FX6fwvAT69R0O6xY8GVsZhLPnH71yhvozdzc"),
    "Omicron Delta": ("0Bzvrj7fbH5hGeS1PZWdUUVA3cWc", "1HhkztyWN3eIgEnC_Ol6V9K4U2BAxXWd-Q6dCPj6z0to"),
    "Omicron Gamma": ("0B0a8aDcg6IYLUzdlZ1NtalRjb0E", "1YYola3Q5193UwT_KYPsaQ8__qSljtHRHQ9tEqyhgm50"),
    "Phi": ("0B14qs8w_TmJBNXowaS1UTjY0M1U", "1mnzBZESaPund9vYDw7NiIhmlkCW97B4AOiLhEO9HQ6Q"),
    "Phi Delta": ("0B9auaviEAXZcMXdQcEdKT1ZoNm8", "1IGtQsz9x1edVgx-esCIatW9t0aXpzRNNv3CcPDYORgs"),
    "Phi Gamma": ("0B5VCRkharVgvX014YklnaXgxSjQ", "1nt9_f032iw0R8x8WBvXv1hOr6x-GSnsJnJP6vPGHYYg"),
    "Pi": ("0ByQH0Vf6d9RRM0lTYW9XMmg0Y2s", "1q0qUKoEAz7DQegBx8T1Bh3vbXt95mODm7jPS9Qf0_A8"),
    "Pi Delta": ("0B5D-1QIq4DQXRDJhTnZjcGNDVDA", "1kWMYeDXYLSHolFNRrXwLPOM8I7Muwgt5BZPQwAQkBrI"),
    "Pi Gamma": ("0BwHQdC-QUBuoc3RYRGR3djMxSW8", "1nuZh4djL9x9YhcBM1Wv0YMoEMehQRV-n_9jIKwBbtGE"),
    "Psi Beta": ("0B91FobKEoghFclluclZ2em5tVTg", "1sM5yvrXYcafML9CEQy6vRK7UggO59ZJUwY4VmGO_CVI"),
    "Psi Delta": ("0BwvK5gYQ6D4nbE1ldF9zdUJyTEU", "1eYhwwWa_Ag28hrZiv5zweuG93gELRpabSEr5TVeIm6Q"),
    "Psi Gamma": ("0B6s5EQ8fQvBhWkdvSnZSRm9NYjQ", "1GG3_GjSl-qwbBrQrAD_KbTbD8wyjduxTS8rhS0-TUrM"),
    "Rho": ("0B6rzasbQK3-WMy03TTh6TGpESEU", "1-Yd6_iAU00ZLyHNBEyadPhwnOAhPEuresAfktwhXb_c"),
    "Rho Beta": ("0B39F0HluPw_1Sm54WWJUUzdGSmM", "1eHlqlam-2ozpV3vFT2CPTDOsu6K5CnWuits2xs5R5JA"),
    "Rho Delta": ("0BwvK5gYQ6D4nbjRXZmNEbnhING8", "1HnV99hcyYgWkAkn6hqLTGuARK5Ty7q0-wbw-x016EBI"),
    "Rho Gamma": ("0B1JHO0ZmAXfhYUYza01mRXN3VFk", "1gibtp2f8qfOHeKalXKVE02VYFW2zOs-w-yf_lRrmiPg"),
    "ROW Colony": ("", ""),
    "SCU Colony": ("1oWOawXLoOdexI5CeBh_7Jhh75wQ3dLpV", "1cX7WVsCRYC5iIygEc0ggMXGiONXkaRJs5up3Mbo1W94"),
    "Sigma": ("0BxmiHqtEaU3aNFdTSDUzUWx0OHM", "1_9cWjBW_D40P_sqjNqT649R4dhy8ztAgX55cD739MYw"),
    "Sigma Delta": ("0BxkaPpKFoEx2TDNMRjcxQVJEYzA", "1TwEnMTskrKq8L5ygpAO7s741ThZVyUtAzi733ZtsXyc"),
    "Sigma Gamma": ("0B3arKXLRh6znT1NPR3Z1blZJTE0", "15fqpNw8AXHZm4lbUdGKbZcJ4rMOiZ6PloeejwclYrOc"),
    "Tau": ("1hASDa1s-i3mKXRtApaVK-ZGpfr4vU2dR", "1kHSVtkIBXRmsUHOpF79feB9pReYDCYf4kcU5WS8VEso"),
    "Tau Beta": ("0B31srXTOG1qyTUhFNnFLLUxaRG8", "1xKJKDNnKyQb6JhMtMpCK9Cv9NCg_DVD6BR2kiPSGCW4"),
    "Tau Delta": ("0B8ncLqGYCpE4X0xyRjBWbjNQZjA", "1fe8qQoQL3uEaFUjoh8-3D7pTTX1bOEGXNyigc_5sdyY"),
    "Tau Gamma": ("17yhBr5jeCWQ6YzevOamICfjZd9pGnzD9", "1ebbO02pRaZJaJ-BpOoaHYfR6zXshCn4VDgihi5BbqXw"),
    "TEST": ("", ""),
    "Theta Delta": ("0B6nDNzHse8KwcDQta1pEdVVWQjQ", "1mHWJtlaOWhB5cXc3nRDUTKui2fDSWxl-3n3-PFEZAL4"),
    "Theta Epsilon": ("1UQnKkW3thxuLFxlPaOC-bL39EK7iUA87", "17lX0UuMMR2oKnbeGpF1hKx24QvYiX-NrDFtL4wGlVjM"),
    "Theta Gamma": ("0B3l4dXZqGwMHVG5Bcl9zZDBBY28", "1My_D9KKgHVUf49BzPv9Mh6pmqls1C8toXt0JDtowDTc"),
    "TU Colony": ("", ""),
    "Nu Epsilon": ("1juUjrZ3KQ0LAWjxVdofGs2ZLPaP-d-kx", "1AO5yMjC_2cfm6hKnR-NkrbffhP5ooKjx5typ6RSowpk"),
    "UA Colony": ("", ""),
    "UCSB Colony": ("1y7q7wVYy7G5BKuC9DmZRSJb6JqPDeUiL", "1D7ubVHyIu3_t0iOJgFvWVeey6swNsBgTwNGgJ7oWCUU"),
    "UNH Colony": ("1nWNQbqAZgaT1FbJUbK3gWce7XIR3JdY-", "1piDtdvAb5HAkSt7HGBCw7fxg-Z_x1Sp7lNOsJVsutbM"),
    "Upsilon": ("0B1lDFFBG6pEyVWdvYzJHUDV2cW8", "1gn2eG2jOA-N97gQ0OcqfcXHkx8f_iMGkwaEFxWBtNQY"),
    "Upsilon Beta": ("0B_J5sIGV00LUcTMzZWFhclV3eTg", "10azJTSKADtcyr-D2ORbywNGbvJIT9BjkwRZbjm1ohyM"),
    "Upsilon Delta": ("0Bxj7_GkM3_lcdzlpa29iVjk2T28", "1QZlgfLd0eOACImLNQzcK9kv9ZQ-6dr1CLyQfWMcP6Ss"),
    "Upsilon Gamma": ("0B2f3yzXus05xcDZWVjZoMEsxWFE", "1_dsR_-EuZF97fAbFZyPpCeKQK4e2z59fSKODMDojP-A"),
    "Victoria Colony": ("", ""),
    "Xi": ("0B-yv8aNy0r62amZ3SVRGU056WTA", "1e4T_hIO1GBxo55YP_ULN5Uk22Il002A9wnDEhAWABTc"),
    "Xi Beta": ("0B1yK_JpzZJoSZ24ySXRKc3dlVmc", "1sBObnh4pghb0Gtcefxs4wqRR9X1MGdk5srvXq7Ll_q4"),
    "Xi Delta": ("1NcF0qYg2uPfNYc3SM-MricnWjTuPhYBh", "1zNK0F8wfokdXC6-RMi6NiZ9__Gj63_noNJgDuhJ_EKw"),
    "Xi Gamma": ("1Vkju01Jx9LRiig9Bz806_jQCGEcE2cuL", "1eYgZXOkIrew4hHf2kp-HpQPTnc0Hddc4wkDV0TEns1o"),
    "Zeta": ("0BzcB3rqceD0UQndFX1dTYlZ6eVE", "1jVABxz0IeKK5hb1PxtotPVmxTISN3em9no2Ewa_vCYI"),
    "Zeta Delta": ("0B5qN94xhCJzfbkRCWHBYaHc5LWs", "1Gesqs0kNEmDWCXZtX_V1iktr1TxjXH2Adb9W0Wua0n0"),
    "Zeta Epsilon": ("0B5qOLmcOGqC5NWtjQVpTN1NFdGM", "1PtQ2Axe4iXmbP03zGDa_IYB6Pqe1sgWJIxkYCtE1y0E"),
    "Zeta Gamma": ("0B_dT5SyJC5sMbUs1NzRCX1FsWEk", "1QmeKV0E68sRg9IA-3G-F_N4PCk5ou6IgZI4IykGAxqw"),
}


def get_all_chapter_submissions(apps, schema_editor):
    chapter_names = list(sorted(CHAPTER_IDS.keys()))
    for chapter_name in chapter_names:
        chapter_info = CHAPTER_IDS[chapter_name]
        print(chapter_name)
        if not chapter_info[1]:
            continue
        get_chapter_data(chapter_name,
                         chapter_info[1],
                         apps)


def get_chapter_data(chapter_name, chapter_key, apps):
    chapter = apps.get_model("chapters", "Chapter")
    spreadsheet = gspread_client.open_by_key(chapter_key)
    sleep(1)
    sheets = spreadsheet.worksheets()
    chapter_obj = chapter.objects.get(name=chapter_name)
    for sheet in sheets:
        # print(sheet.title)
        if "Submissions" in sheet.title:
            sleep(1)
            submissions = sheet.get_all_records()
            for submission in submissions:
                add_user_submission(chapter_obj, submission, apps)


submit_types = [
    "Pledge Program",
    "Hall of Fame",
    "Newsletter",
    "Report",
    "Awards",
    "Project",
    "Audit",
    "Article",
    "Lockin Goals",
    "OSM",
    "RMP",
    "Scholarship App",
]


def add_user_submission(chapter_obj, submit_row, apps):
    print(submit_row)
    submission = apps.get_model("submissions", "Submission")
    score_type = apps.get_model("scores", "ScoreType")
    if submit_row['Date']:
        date_obj = datetime.datetime.strptime(submit_row['Date'],
                                              '%m/%d/%Y')
    submit_type = submit_row['Type']
    if submit_type == "Lock-In Goals":
        submit_type = "Lockin Goals"
    if submit_type not in submit_types:
        return
    submit_type = slugify(submit_type)
    score_type_obj = score_type.objects.get(slug=submit_type)
    url = submit_row['Location of Upload']
    if "http" not in url:
        return
    file_temp = NamedTemporaryFile()
    file_temp.write(urlopen(url).read())
    file_temp.flush()
    new_submission = submission(
        date=date_obj,
        created=date_obj,
        modified=date_obj,
        file=File(file_temp),
        name=submit_row['File Name'][:49],
        type=score_type_obj,
        score=submit_row['Score'],
        chapter=chapter_obj
    )
    try:
        with transaction.atomic():
            new_submission.save()
    except googleapiclient.errors.HttpError:
        print(f"Error uploading file: {submit_row['File Name'][:49]}")


def migrate_data_backward(apps, schema_editor):
    submission = apps.get_model("submissions", "Submission")
    submission.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('submissions', '0002_auto_20180706_1204'),
        ('chapters', '0005_chapter_slug'),
        ('scores', '0003_initial_scores_data'),
    ]

    operations = [
        migrations.RunPython(get_all_chapter_submissions,
                             migrate_data_backward),
    ]
