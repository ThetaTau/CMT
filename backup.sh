#!/bin/bash
# chmod +x backup.sh

source virtualenvwrapper.sh

echo "Backup production to local drive"
if ! workon thetatauCMT; then
  echo "An error occurred setting thetatauCMT"
  exit
fi
export GNUPGHOME="/home/Venturafranklin/thetatauCMT/secrets"
export DBBACKUP_STORAGE_LOCATION="/home/Venturafranklin/thetatauCMT/database_backups"
if ! python manage.py dbbackup --compress --encrypt --noinput; then
  echo "An error occurred backing up database"
  exit
fi

deactivate

echo "Restore test restore to staging"
if ! workon testCMT; then
  echo "An error occurred setting testCMT"
  exit
fi
export GNUPGHOME="/home/Venturafranklin/thetatauCMT/secrets"
export DBBACKUP_STORAGE_LOCATION="/home/Venturafranklin/thetatauCMT/database_backups"
if ! python manage.py dbrestore --database default --uncompress --decrypt --noinput; then
  echo "An error occurred restoring database"
  exit
fi

deactivate

echo "Backup production to Google Cloud"
if ! workon thetatauCMT; then
  echo "An error occurred setting thetatauCMT"
  exit
fi
export GNUPGHOME="/home/Venturafranklin/thetatauCMT/secrets"
export DBBACKUP_LOCAL="False"
if ! python manage.py dbbackup --compress --encrypt --noinput; then
  echo "An error occurred backing up database to remote"
  exit
fi

echo "Cleanup old local backups; Only keep 2 local"
if ! python manage.py runscript clean_local_backups; then
  echo "An error occurred cleaning up old backups"
  exit
fi
