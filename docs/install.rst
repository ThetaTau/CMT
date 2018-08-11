Install
=========

Install python 3.6<br/>
Install PostgreSQL 10.3<br/>
Install Node 9.9.0 (https://nodejs.org/en/)<br/>
pip install virtualenv<br/>
pip install virtualenvwrapper (Windows: pip install virtualenvwrapper-win)<br/>
    export WORKON_HOME=~/Envs<br/>

mkvirtualenv cmt<br/>
cd to location to clone (For example: cd E:\workspace\CMT)<br/>
git clone https://github.com/VenturaFranklin/thetatauCMT.git<br/>
setprojectdir E:\workspace\CMT\thetatauCMT<br/>
add2virtualenv E:\workspace\CMT\thetatauCMT\thetatauCMT<br/>

Download MailHog to thetatauCMT folder

workon cmt<br/>
pip install Django<br/>
pip install -r requirements/local.<br/>

"pg_env.bat"<br/>
"C:\Program Files\PostgreSQL\10\bin\createdb" thetatauCMT<br/>

edit data\pg_hba.conf ("E:\workspace\CMT\data\pg_hba.conf")
    # IPv4 local connections:
    host    all             all             127.0.0.1/32            md5
change to:
    # IPv4 local connections:
    host    all             all             127.0.0.1/32            trust

restart the postgres service

python manage.py migrate

python manage.py createsuperuser

for dev we will use test as the superuser

npm install

npm install compass


## Now to run you need:
`"C:\Program Files\PostgreSQL\10\pg_env.bat"`
and then
`npm run dev`

or edit the activate for virtualenv
C:\Users\venturf2\Envs\cmt\Scripts\activate.bat
add the lines at the bottom:
```
:: User defined
"C:\Program Files\PostgreSQL\10\pg_env.bat"
```

Then add the
set GOOGLE_DRIVE_STORAGE_JSON_KEY_FILE=%fileinsecretsfolder%
and
set GOOGLE_API_KEY=%generatethis%


To prepopulate data:
python manage.py makemigrations --empty yourappname --name migrationname

django-admin migrate yourappname


python manage.py startapp yourappname

then:
    - config/urls add new connect to yourappname/urls
    - config/settings/base add new LOCAL_APPS
    - copy over tests/folder, delete tests.py
    - copy over urls.py file from another app
    - create initial blank views

If delete users, need to add back the officers:
    python manage.py officer_groups


To Add existing user as superuser from cmd line:
    python manage.py shell
    from users.models import User
    me = User.objects.get(username='venturafranklin@gmail.com')
    me.is_superuser=True
    me.is_staff=True
    me.save()
