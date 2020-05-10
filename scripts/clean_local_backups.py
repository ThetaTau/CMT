import datetime
from pathlib import Path


def run(*args):
    """
    This will find all backups from dbbackup that have been compressed
    :param args: None
    :return: None
    python manage.py runscript clean_local_backups
    """
    database_backups_path = Path(r'database_backups')
    database_backups = []
    for path in database_backups_path.iterdir():
        if not path.is_file():
            continue
        if '.gz' not in path.suffixes and '.gpg' not in path.suffixes:
            continue
        file_name = path.stem
        # 'default-blue-liveconsole7-2020-05-10-143843.psql.gz'
        file_name_parts = file_name.split('.')[0].split('-')
        date = file_name_parts[-4:]
        date = '-'.join(date)
        date = datetime.datetime.strptime(date, '%Y-%m-%d-%H%M%S')
        database_backups.append((path, date))
    if len(database_backups) > 2:
        database_backups.sort(key=lambda x: x[1], reverse=True)
        to_delete = database_backups[2:]
        for path_info in to_delete:
            path, date = path_info
            path.unlink()
