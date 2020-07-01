# Install

=========

## Instructions for MacOS

### Install Python 3.7 (or latest) with Homebrew

`brew update && brew upgrade`
`brew install python` (This will install python3 by default)

To make python3 the default python in your environment, do either one of the following:
_temporarily modify PATH_
`export PATH="/usr/local/opt/python/libexec/bin:/usr/local/sbin:$PATH"`

_permanently modify PATH_
`echo 'export PATH="/usr/local/opt/python/libexec/bin:/usr/local/sbin:$PATH"' >> ~/.bashrc`
If chose this option, be sure to do `source ~/.bashrc` before continuing or whenever restart terminal

Verify python version with `python --version` and you should get output `Python 3.7.7`

Verify pip version with `pip -V` and you should get output `pip 20.0.2 from /usr/local/lib/python3.7/site-packages/pip (python 3.7)`

### Install Node 9.9.0 (or latest)

Install Node at https://nodejs.org/en/
Verify Node version with `node -v`and you should get output `v12.16.3` (or later)

### Install and configure virtualenvwrapper

`pip install virtualenv`
`pip install virtualenvwrapper`

Add the following lines to the shell startup file (.bashrc):

```
export WORKON_HOME=~/virtualenvs
export VIRTUALENVWRAPPER_PYTHON=/usr/bin/python
source /usr/local/bin/virtualenvwrapper.sh
```

Then, either restart Terminal window or do `source ~/.bashrc` to put these changes into effect

To create virtual environment for our project:
`mkvirtualenv cmt` -> output: `created virtual environment CPython3.7.7.final.0-64 in 682ms`

`workon cmt`

cd to location to clone project repository (For example: `cd ~/Desktop/CMT`)
`git clone https://github.com/VenturaFranklin/thetatauCMT.git`

cd to the repo location (`cd ~/Desktop/CMT/thetatauCMT`), then do:
`setvirtualenvproject`in that directory

`add2virtualenv ~/Desktop/CMT/thetatauCMT/thetatauCMT`

    NOTE: THIS IS NOT THE SAME FOLDER AS ABOVE, BUT A SUBDIRECTORY

`workon cmt`

### Install PostgreSQL 10.X

Install PostgreSQL app to run the database server and follow instructions at https://postgresapp.com/
Run the Postgres server with the app and make sure that the server status is **Running**

Install PostgreSQL 10.X at https://www.postgresql.org/download/
**Remember where you set the data folder! For example: `/Library/PostgreSQL/10`**

Try to run `pg_config`, if get a _not found_ error, then you need to find the path of this command with:
`sudo find / -name pg_config` and receive an output similar to `/Library/PostgreSQL/10/bin`
Change the PATH to run Postgres command line tools:
`export PATH=/Library/PostgreSQL/10/bin:${PATH}`

Re-run `pg_config` to verify that our database works!

### Install dependencies

Install PostgreSQL database adapter for Django
`pip install psycopg2`
`pip install psycopg2-binary`

_If receive an Symbol not found error, reinstall psycopg2 and psycopg2-binary with the base Python version. (i.e. 2.7.7)_
`pip uninstall psycopg2`
`pip uninstall psycopg2-binary`
`pip install pyscopg2==2.7.7`
`pip install pyscopg2-binary==2.7.7`

Install Django
`pip install Django`

Install other requirements
`pip install -r requirements/local.txt` (Postgres has to be installed first)

Create Postgres database (make sure that the server is Running in Postgres app)
`export PATH=/Library/PostgreSQL/10/bin:${PATH}`
`createdb thetatauCMT`

Find the location of the Postgres server HBA file by going on the Postgres app -> Server Settings... -> HBA File

Check that your pg_hba.conf file has the following:
`# IPv4 local connections: host all all 127.0.0.1/32 trust`

If changes needed to be made, make sure to restart the Postgres service.

Setting up Django app and creating superuser:
`python manage.py migrate`

`python manage.py createsuperuser`

for dev we will use test as the superuser

`npm install compass`

### Setting up VSCode and virtual environments

Find directory of our virtualenv as set up with:
`cdvirtualenv` -> `pwd` -> output: `/Users/[username]/virtualenvs/cmt`

Change interpreter path in VSCode and replace it with your output.
To setup our debugger, click 'Run and Debug' and select 'Django' which will run our server

Install Black in your virtual environment, which can now be run directly in VSCode terminal. Make sure to do `workon cmt` to activate our virtual environment and that `(cmt)` appears in front of our command line.
(Follow instructions at https://dev.to/adamlombard/how-to-use-the-black-python-code-formatter-in-vscode-3lo0#:~:text=Open%20your%20VSCode%20settings%2C%20by,%3E%20Preferences%20%2D%3E%20Settings%27.&text=Black%20will%20now%20format%20your%20code%20whenever%20you%20save%20a%20*)

## Instructions for Windows

Install python 3.6

Install PostgreSQL 10.X (https://www.postgresql.org/download/)
**Remember where you set the data folder!**

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

edit wherever you installed postgress data folder: data\pg_hba.conf (For example: ""C:\Program Files\PostgreSQL\10\data\pg_hba.conf"") # IPv4 local connections:
host all all 127.0.0.1/32 md5
change to: # IPv4 local connections:
host all all 127.0.0.1/32 trust

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
