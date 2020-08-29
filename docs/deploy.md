Deploy
========

We are currently using pythonanywhere.com for hosting.

This means a lot of deployment steps are streamlined. [See instructions](https://help.pythonanywhere.com/pages/DeployExistingDjangoProject/)

For the requirements install step, must use:
`pip install -r requirements/production.txt`

on pythonanywhere setvirtualenvproject was needed with no arguments in the app directory

Setup database:
-----
From: https://help.pythonanywhere.com/pages/PostgresGettingStarted/
````
CREATE DATABASE myappdb;

CREATE USER myappuser WITH PASSWORD 'a-nice-random-password';

ALTER ROLE myappuser SET client_encoding TO 'utf8';
ALTER ROLE myappuser SET default_transaction_isolation TO 'read committed';
ALTER ROLE myappuser SET timezone TO 'UTC';

GRANT ALL PRIVILEGES ON DATABASE myappdb TO myappuser ;
````

#### Post activate files for environment variables in prod:
    - /home/Venturafranklin/.virtualenvs/thetatauCMT/bin/postactivate
    - files/var/www/cmt_thetatau_info_wsgi.py

Settings needed in postactivate:
````
export WEB_CONCURRENCY=4
export DJANGO_SETTINGS_MODULE='config.settings.production'
export DJANGO_SECRET_KEY=''  # https://www.miniwebtool.com/django-secret-key-generator/
export DJANGO_ALLOWED_HOSTS='cmt.thetatau.org'
export DJANGO_ADMIN_URL=''  # Unique url
export MAILJET_API_KEY=''
export MAILJET_SECRET_KEY=''
export ROLLBAR_ACCESS=''
export DATABASE_URL='postgres://{user}:{password}@{postgres-url}:{postgres-port}/{database_name}'
export GOOGLE_APPLICATION_CREDENTIALS=''
````
In the wsgi file (with the settings copied from above):
````
import os
import sys
path = '/home/Venturafranklin/thetatauCMT'
if path not in sys.path:
    sys.path.append(path)

os.environ["DJANGO_SETTINGS_MODULE"] = 'config.settings.production'
os.environ["DJANGO_SECRET_KEY"] = ""
os.environ["DJANGO_ALLOWED_HOSTS"] = 'cmt.thetatau.org'
os.environ["DJANGO_ADMIN_URL"] = ""
os.environ["MAILJET_API_KEY"] = ""
os.environ["MAILJET_SECRET_KEY"] = ""
os.environ["DJANGO_AWS_ACCESS_KEY_ID"] = ""
os.environ["DJANGO_AWS_SECRET_ACCESS_KEY"] = ""
os.environ["DJANGO_AWS_STORAGE_BUCKET_NAME"] = ""
os.environ["ROLLBAR_ACCESS"] = ""
os.environ["DATABASE_URL"] = ""
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = ""

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
````
Extra
------
Need to add files to secrets folder
- secrets/GOOGLE_API_KEY
- secrets/ChapterManagementTool-b239bceff1a7.json

#### To update
    - Start virtualenv
    - git pull origin master
    - restart the app

#### SSL Certificates: https://help.pythonanywhere.com/pages/LetsEncrypt/

#### Check date:
    openssl x509 -enddate -noout -in ~/letsencrypt/cmt.thetatau.org/cert.pem

#### Renew:
    cd ~/letsencrypt
    ~/dehydrated/dehydrated --cron --domain cmt.thetatau.org --out . --challenge http-01
