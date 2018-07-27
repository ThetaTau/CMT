'''
Created on Jun 22, 2018

@author: venturf2
IMPORTANT: pydrive uses v2 of Google Drive API
'''
import os
from django.conf import settings
import gspread
from oauth2client import file, client, tools
from events.models import Event
from chapters.models import Chapter
from scores.models import ScoreType



def get_all_ids():
    from pydrive.auth import GoogleAuth
    from pydrive.drive import GoogleDrive
    GoogleAuth.DEFAULT_SETTINGS['client_config_file'] = \
        os.path.join(settings.ROOT_DIR.root, r'secrets/GoogleSheetsClient_id.json')
    GoogleAuth.DEFAULT_SETTINGS['save_credentials_backend'] = 'file'
    GoogleAuth.DEFAULT_SETTINGS['save_credentials'] = True
    GoogleAuth.DEFAULT_SETTINGS['save_credentials_file'] = \
        os.path.join(settings.ROOT_DIR.root, r'secrets/GoogleSheetsClient_id_out.json')
    print(GoogleAuth.DEFAULT_SETTINGS)
    gauth = GoogleAuth()
    gauth.LocalWebserverAuth()
    NATIONALS_FOLDER = '0BwvK5gYQ6D4nTDRtY1prZG12UU0'
    # Create GoogleDrive instance with authenticated GoogleAuth instance
    drive = GoogleDrive(gauth)
    # Search parameters:
    #     https://developers.google.com/drive/api/v3/search-parameters
    national_folders = drive.ListFile({
        'q': f"'{NATIONALS_FOLDER}' in parents"}).GetList()
    for region_folder in national_folders:
        print(f"title: {region_folder['title']}, id: {region_folder['id']}")
        print(region_folder)
        REGION_ID = region_folder['id']
        regional_folders = drive.ListFile({
            'q': f"'{REGION_ID}' in parents"}).GetList()
        if not regional_folders:
            continue
        for chapter_folder in regional_folders:
            print(f"    title: {chapter_folder['title']}, id: {chapter_folder['id']}")
            CHAPTER_ID = chapter_folder['id']
            chapter_items = drive.ListFile({
                'q': f"'{CHAPTER_ID}' in parents"}).GetList()
            if not chapter_items:
                continue
            for item in chapter_items:
                print(f"        title: {item['title']}, id: {item['id']}")




