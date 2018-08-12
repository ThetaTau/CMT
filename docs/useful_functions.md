## Useful functions/notes
To prepopulate data:
python manage.py makemigrations --empty yourappname --name migrationname

django-admin migrate yourappname

to go back in time: 
   django-admin migrate yourappname %name of migration%

### To add a new app
python manage.py startapp yourappname

#### Then you need:
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
    me.save()
