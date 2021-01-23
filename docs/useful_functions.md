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
```python
from users.models import User
me = User.objects.get(username='venturafranklin@gmail.com')
me.is_superuser=True
me.is_staff=True
me.set_password('_new_password_')
me.save()
```
    
#### If delete/reload everything
Need to fix social accounts
- Go to: https://console.cloud.google.com/apis/credentials?authuser=2&folder=&organizationId=&project=chaptermanagementtool
  - Make sure to get ChapterManagementTool
- Fix the creds (id & secret) here: http://localhost:8000/admin/socialaccount/socialapp/
```
from allauth.socialaccount.models import SocialApp
from django.contrib.sites.models import Site
SocialApp.objects.filter(name="Google").first().delete()
app = SocialApp(
    provider="google",
    name="Google",
    client_id="", # Client ID called developer
    secret="",)
app.save()
app.sites.set(Site.objects.all())
app.save()
```

## Backups/Restore

### Postgres commands
#### Dump
```shell script
pg_dump --format c --no-owner --oids \
--host venturafranklin-874.postgres.pythonanywhere-services.com \
--port 10874 --username thetatau --dbname thetataucmt \
--file=database_backups/20200411.bak
```
#### Restore
__This does not work when the staging db is off from prod. ie. new table name etc.__
```shell script
dropdb thetatauCMT
createdb thetatauCMT
pg_restore --no-owner --dbname=thetatauCMT --format=c database_backups\20200411_postupdate.bak
    
pg_restore --no-owner --dbname=testcmt --port 10874 \
--host venturafranklin-874.postgres.pythonanywhere-services.com \
--username=testthetatau --format=c /home/Venturafranklin/thetatauCMT/database_backups/20200411.bak
```
__This does not work b/c the db is often in use...__
Connect to the database with at https://www.pythonanywhere.com/user/Venturafranklin/databases/
Then run the commands:
```postgresql
SELECT
   pg_terminate_backend (pg_stat_activity.pid)
FROM
   pg_stat_activity
WHERE
   pg_stat_activity.datname = 'testcmt';
   
DROP DATABASE testcmt;

CREATE DATABASE testcmt OWNER testthetatau;

-- after to verify restore worked
\c testcmt

\dt
```

### Decrypt a file

```
import os
import gnupg
filename = r""
passphrase = input("What is passphrase")
new_basename = filename.replace('.gpg', '')
g = gnupg.GPG()
with open(filename, 'rb') as inputfile:
  result = g.decrypt_file(file=inputfile, passphrase=passphrase, output=new_basename)
```
