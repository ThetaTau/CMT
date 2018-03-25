Install
=========

Install python 3.6
Install PostgreSQL 10.3
pip install virtualenv
pip install virtualenvwrapper (Windows: pip install virtualenvwrapper-win)
    export WORKON_HOME=~/Envs

mkvirtualenv cmt
cd to location to clone (cd E:\workspace\CMT)
git clone https://github.com/VenturaFranklin/thetatauCMT.git
setprojectdir E:\workspace\CMT\thetatauCMT

Download MailHog to thetatauCMT folder

workon cmt
pip install Django
pip install -r requirements/local.txt

"C:\Program Files\PostgreSQL\10\pg_env.bat"
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


