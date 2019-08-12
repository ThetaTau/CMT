## Useful functions/notes
To prepopulate data:

    python manage.py makemigrations --empty yourappname --name migrationname
 Normal migration:

    django-admin migrate yourappname
to go back in time:

    django-admin migrate yourappname %name of migration%
### To add a new app:

    python manage.py startapp yourappname

#### Then you need to do:
- config/urls add new connect to yourappname/urls
- config/settings/base add new LOCAL_APPS
- copy over tests/folder, delete tests.py
- copy over urls.py file from another app
- create initial blank views

#### If delete users, need to add back the officers:
    python manage.py officer_groups

#### Super user from existing user
    python manage.py shell
from users.models import User
me = User.objects.get(username='venturafranklin@gmail.com')
me.is_superuser=True
me.is_staff=True
me.set_password('_new_password_')
me.save()
    
#### If delete/reload everything
Need to fix social accounts
- Go to: https://console.developers.google.com/apis/credentials/oauthclient/
  - Make sure to get ChapterManagementTool
- Fix the creds here: http://localhost:8000/admin/socialaccount/socialapp/
    
## Backups/Restore

### Django commands
#### Dump 
make sure to change date; `^ instead of \ in windows`

This currently takes 5 minutes and is 44.9 MB on 20190303

On restore: Need to fix the social accounts in development 
````
python manage.py dumpdata --natural-foreign \
--exclude auth.permission --exclude contenttypes \
--indent 4 > database_backups/20190811.json
````
#### Restore
    python manage.py flush
    python manage.py loaddata database_backups\$date$.json
### Postgres commands
#### Dump
    pg_dump --format c --no-owner --oids \
    --host venturafranklin-874.postgres.pythonanywhere-services.com \
    --port 10874 --username thetatau --dbname thetataucmt \
    --file=database_backups/20190811.bak
#### Restore
    dropdb thetatauCMT
    createdb thetatauCMT
    pg_restore --no-owner --dbname=thetatauCMT \
    --username=postgres --format=c database_backups/20190303.bak
    
    pg_restore --no-owner --dbname=testcmt --port 10874 \
    --host venturafranklin-874.postgres.pythonanywhere-services.com \
    --username=testthetatau --format=c database_backups/20190811.bak
