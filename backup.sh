#!/bin/bash
# chmod +x backup.sh
# from django.core.management import call_command
# call_command('dbbackup', '--encrypt', '--noinput')
# call_command('dbrestore', '--decrypt', '--noinput',
#              '--passphrase=%passphrase%', database='default')

if [[ $1 == "" ]]; then
  echo 'You must provide database encryption passphrase'
  exit 1
fi

PASSPHRASE=$1

RESTORE_TEST=${2:-true}

source virtualenvwrapper.sh

echo "Backup production to local drive"
if ! workon thetatauCMT-313; then
  echo "An error occurred setting thetatauCMT-313"
  exit
fi
export GNUPGHOME="/home/Venturafranklin/thetatauCMT/secrets"
export DBBACKUP_STORAGE_LOCATION="/home/Venturafranklin/thetatauCMT/database_backups"
if ! python manage.py dbbackup --encrypt --noinput --clean; then
  echo "An error occurred backing up database"
  exit
fi

if [ "$RESTORE_TEST" = true ]; then
  deactivate

  echo "Restore test restore to staging"
  if ! workon testCMT-313; then
    echo "An error occurred setting testCMT-313"
    exit
  fi
  export GNUPGHOME="/home/Venturafranklin/thetatauCMT/secrets"
  export DBBACKUP_STORAGE_LOCATION="/home/Venturafranklin/thetatauCMT/database_backups"
  # Wipe the staging schema first: restoring on top of a schema that has
  # drifted from production (e.g. a column later altered to an identity
  # column) makes pg_restore's --clean ALTER/DROP statements fail because
  # they assume the target already matches the dump's shape.
  if ! echo "DROP SCHEMA public CASCADE; CREATE SCHEMA public;" | python manage.py dbshell -- -v ON_ERROR_STOP=1; then
    echo "An error occurred resetting the staging schema"
    exit
  fi
  if ! python manage.py dbrestore --database default --decrypt --noinput --passphrase=$PASSPHRASE; then
    echo "An error occurred restoring database"
    exit
  fi

  echo "De-identify staging database"
  export DBBACKUP_STORAGE_LOCATION="/home/Venturafranklin/testCMT/database_backups"
  python manage.py anonymize_db
  python manage.py dbbackup --noinput --clean --servername DEIDENTIFED

  deactivate
else
  echo "Skipping restore test"
fi

echo "Backup production to Google Cloud"
if ! workon thetatauCMT-313; then
  echo "An error occurred setting thetatauCMT-313"
  exit
fi
export GNUPGHOME="/home/Venturafranklin/thetatauCMT/secrets"
export DBBACKUP_LOCAL="False"
if ! python manage.py dbbackup --encrypt --noinput; then
  echo "An error occurred backing up database to remote"
  exit
fi
