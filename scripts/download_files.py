import os
import csv
from django.conf import settings
from submissions.models import Submission


def run():
    if not os.path.exists('submissions'):
        os.makedirs('submissions')
    file_name = os.path.join('submissions', "submissions_download.csv")
    fields = ['id', 'name', 'url', 'drive_id']
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
    drive = GoogleDrive(gauth)

    with open(file_name, 'w', newline='') as export_file:
        writer = csv.DictWriter(export_file, fieldnames=fields)
        writer.writeheader()
        for submission in Submission.objects.all():
            file_name = submission.file.name
            print(file_name)
            save = input(f"Save file: {file_name}? y/n")
            if save == 'y':
                url = submission.file.url
                print(f"   Saving {file_name} from {url}")
                base_name = f"{submission.chapter.slug}_{os.path.basename(file_name)}"
                new_path = os.path.join('submissions', base_name)
                drive_id = url.split(r"/d/")[1].split(r"/view?")[0]
                file_obj = drive.CreateFile({'id': drive_id})
                file_obj.GetContentFile(new_path)
                row = {
                    'id': submission.id,
                    'name': file_name,
                    'url': url,
                    'drive_id': drive_id,
                }
                writer.writerow(row)
            elif save == 'x':
                break
