Deploy
========

We are currently using pythonanywhere.com for hosting.

This means a lot of deployment steps are streamlined. [See instructions](https://help.pythonanywhere.com/pages/DeployExistingDjangoProject/)

For the requirements install step, must use:
`pip install -r requirements/production.txt`

#### Post activate files for environment variables in prod:
    - /home/Venturafranklin/.virtualenvs/thetatauCMT/bin/postactivate
    - files/var/www/cmt_thetatau_info_wsgi.py

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

### Database Setup
CREATE USER thetatau;
ALTER USER thetatau WITH PASSWORD 'XXXXX';
CREATE DATABASE thetatauCMT OWNER thetatau;

### Database dump;
```python manage.py dumpdata --natural-foreign \
   --exclude auth.permission --exclude contenttypes \
   --indent 4 > data.json```
