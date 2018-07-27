Install
=========

Install python 3.6
Install PostgreSQL 10.3
Install Node 9.9.0 (https://nodejs.org/en/)
pip install virtualenv
pip install virtualenvwrapper (Windows: pip install virtualenvwrapper-win)
    export WORKON_HOME=~/Envs

mkvirtualenv cmt
cd to location to clone (cd E:\workspace\CMT)
git clone https://github.com/VenturaFranklin/thetatauCMT.git
setprojectdir E:\workspace\CMT\thetatauCMT
add2virtualenv E:\workspace\CMT\thetatauCMT\thetatauCMT

Download MailHog to thetatauCMT folder

workon cmt
pip install Django
pip install -r requirements/local.txt

"pg_env.bat"
"C:\Program Files\PostgreSQL\10\bin\createdb" thetatauCMT

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
