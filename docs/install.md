Install
=========

Install python 3.6

Install PostgreSQL 10.X (https://www.postgresql.org/download/)
    __Remember where you set the data folder!__

Install Node 9.9.0 (or latest) (https://nodejs.org/en/)

pip install virtualenv

pip install virtualenvwrapper (Windows: pip install virtualenvwrapper-win)

mkvirtualenv cmt

workon cmt

cd to location to clone (For example: cd E:\workspace\CMT)

git clone https://github.com/VenturaFranklin/thetatauCMT.git

setprojectdir Your_project_dir (For example: setprojectdir E:\workspace\CMT\thetatauCMT)

add2virtualenv Your_project_app_dir

    (THIS IS NOT THE SAME FOLDER AS ABOVE, BUT A SUBDIRECTORY For example setprojectdir E:\workspace\CMT\thetatauCMT\thetatauCMT)

workon cmt

pip install Django

pip install -r requirements/local.txt (Postgres needs to be installed first)

run from command line the postgress bat file: "C:\Program Files\PostgreSQL\10\pg_env.bat"

run from command line the postgress create bat file: "C:\Program Files\PostgreSQL\10\bin\createdb" thetatauCMT

edit wherever you installed postgress data folder: data\pg_hba.conf (For example: ""C:\Program Files\PostgreSQL\10\data\pg_hba.conf"")
    # IPv4 local connections:
    host    all             all             127.0.0.1/32            md5
change to:
    # IPv4 local connections:
    host    all             all             127.0.0.1/32            trust

restart the postgres service

workon cmt

python manage.py migrate

python manage.py createsuperuser

for dev we will use test as the superuser

npm install

npm install compass


#### Now to run you need:
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

#### Then add the following:
    - set GOOGLE_DRIVE_STORAGE_JSON_KEY_FILE=%fileinsecretsfolder%
        - (For example: set GOOGLE_DRIVE_STORAGE_JSON_KEY_FILE="E:\workspace\CMT\thetatauCMT\secrets\ChapterManagementTool-b239bceff1a7.json")
    - set GOOGLE_API_KEY=%generatethis%
        - (Please contact franklin.ventura@thetatau.org for this)

#### To setup pycharm:
    - Add project from existing pycharm files in cloned directory
    - Ignore Django facet issue (unless you have pycharm pro)
    - File --> Settings --> Project: thetatauCMT --> Project Interpreter
        Add virtualenv configured above, set as env for project
    - Set the environment variables
        - 


## [Now see helpful functions](useful_functions.md)
