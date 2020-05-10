#!/bin/bash
# chmod +x backup.sh

source virtualenvwrapper.sh

# Backup production to local drive
workon thetatauCMT
export GNUPGHOME="/home/Venturafranklin/thetatauCMT/secrets"
export DBBACKUP_STORAGE_LOCATION="/home/Venturafranklin/thetatauCMT/database_backups"
python manage.py dbbackup --compress --encrypt --noinput

deactivate

# Restore test to staging
workon testCMT
export GNUPGHOME="/home/Venturafranklin/thetatauCMT/secrets"
export DBBACKUP_STORAGE_LOCATION="/home/Venturafranklin/thetatauCMT/database_backups"
python manage.py dbrestore --uncompress --decrypt --noinput

deactivate

# Backup production to Google Cloud
workon thettauCMT
export GNUPGHOME="/home/Venturafranklin/thetatauCMT/secrets"
export DBBACKUP_LOCAL="False"
python manage.py dbbackup --compress --encrypt --noinput

# Cleanup old local backups; Only keep 2 local
python manage.py runscript clean_local_backups
