# Install

You can use docker or install locally for development.

## Docker

See notes on using docker for this project as a part of the cookiecutter django project at:
[Getting Up and Running Locally With Docker](https://cookiecutter-django.readthedocs.io/en/latest/developing-locally-docker.html)

Build the docker image

    docker-compose -f docker-compose.local.yml build

Run the image for the first time

    docker-compose -f docker-compose.local.yml up

Kill the image with ctrl+c

Run the database reset command. This will perform migrations, generate static files, create a superuser with natoff privileges, and preload the database with essential items. When this command is run, enter 'yes' whenever prompted, and enter any username/email/password for the superuser.

    docker-compose -f docker-compose.local.yml run --rm django python manage.py dbreset

Finally, to run the application run:

    docker-compose -f docker-compose.local.yml up

In order to perform all operations smoothly, you should promote your superuser to a national officer position.
To do this, navigate to the users page in the admin page (http://localhost:8000/admin/users/user).

Click on the username of your superuser.

Navigate to "Groups" (under "Permissions"). You should see the "officer" and "natoff" groups. Click on one of them and
then the right arrow button to move it from "Available Groups" to "Chosen Groups". Do this for the other group as well
so that they are both in "Chosen Groups". Scroll to the bottom of the page and press "Save".

Now navigate to the national officer election report page (http://localhost:8000/forms/national-officer/).

Set the superuser to a national officer title (e.g. Grand Regent). Make sure the start date is in the past and the
end date is far in the future, and press "Submit".

You are now all set up!

If you want to run a jupyter notebook, you can run:

    docker-compose -f docker-compose.local.yml run --rm -p 8888:8888 django python manage.py shell_plus --notebook

Then navigate to localhost:8000/admin, log in with your superuser go to:
http://localhost:8000/admin/socialaccount/socialapp/ click on "Add Social Application"
Set following:
Provider: Facebook
Name: Facebook
Client ID: 1234
Secret Key: 1234
Add cmt.thetatau.org to the chosen sites (click the right arrow after selecting)

I also have a pycharm run configuration that I use that should be in git.

## Instructions for Installing Locally Windows/MacOS

### Get the code

- [Install git if you don't already have it.](https://git-scm.com/book/en/v2/Getting-Started-Installing-Git)
- Open a folder or cd to location where you want to clone the code. (For example: `cd E:\workspace\` or `cd ~/Desktop`)

      git clone https://github.com/VenturaFranklin/thetatauCMT.git

### Install Python

The latest version of python should be fine, nothing older than 3.6 as we use f-strings

Verify python version with `python --version` and you should get output `Python 3.X.X`

#### Mac

    brew update && brew upgrade

    brew install python # (This will install python3 by default)

To make python3 the default python in your environment, do either one of the following:

**temporarily modify PATH:**
`export PATH="/usr/local/opt/python/libexec/bin:/usr/local/sbin:$PATH"`

**permanently modify PATH:**
`echo 'export PATH="/usr/local/opt/python/libexec/bin:/usr/local/sbin:$PATH"' >> ~/.bashrc`

#### Windows

    Make sure to select the option "Add to Path" or know how to do it yourself

    Download and install from executable: https://www.python.org/downloads/windows/

### Install and configure virtualenvwrapper

_NOT WINDOWS_: `pip install virtualenvwrapper` (_WINDOWS_: `pip install virtualenvwrapper-win`)

Add the following Windows environment variables or Mac add the following lines to the shell startup file (.bashrc):

```
export WORKON_HOME=~/virtualenvs                    WINDOWS: setx WORKON_HOME %HOME%\virtualenvs
export VIRTUALENVWRAPPER_PYTHON=/usr/bin/python     WINDOWS: skip this
source /usr/local/bin/virtualenvwrapper.sh          WINDOWS: skip this
```

Then, either restart cmd/Terminal window or do `source ~/.bashrc` to put these changes into effect

To create virtual environment for our project, if this doesn't work then virtualenvwrapper was not successfully installed:

    mkvirtualenv cmt

    workon cmt

cd to location where you cloned project repository (For example: `cd ~/Desktop/thetatauCMT`)

    setprojectdir {Your_project_dir} # (WHERE YOU CLONED THE REPO For example: setprojectdir E:\workspace\thetatauCMT)

Add files to virtualenv path THIS IS NOT THE SAME FOLDER AS ABOVE, BUT A SUBDIRECTORY For example: add2virtualenv E:\workspace\thetatauCMT\thetatauCMT

    add2virtualenv {Your_project_dir}/thetatauCMT # NOTE: THIS IS NOT THE SAME FOLDER AS ABOVE, BUT A SUBDIRECTORY For example: setprojectdir E:\workspace\thetatauCMT\thetatauCMT

    workon cmt

### Install PostgreSQL

Production is currently running Postgres server version: 12.
I have 10.X and 12.X installed with no issues pulling data from production to debug

You do not need stackbuilder.

Install PostgreSQL at https://www.postgresql.org/download/
**Remember where you set the data folder! For example: `/Library/PostgreSQL/10`**

In order to verify that postgres was install, try to run `pg_config`, if you get a _not found_ error, then you need to find the path of this command with:

This will add all of the postgres commands to your command line

    mac: `sudo find / -name pg_config` -> output: `/Library/PostgreSQL/10/bin`

windows: `export PATH=/Library/PostgreSQL/10/bin:${PATH}`

And then to get the environment
or Windows run from commandline

    "C:\Program Files\PostgreSQL\10\pg_env.bat" (your postgres version will be different!)

Re-run `pg_config` to verify that our database works!

Find the location of the Postgres server HBA file by going on the Postgres app -> Server Settings... -> HBA File This is
generally in your data folder. The default is normally C:\Program Files\PostgreSQL\13\data\pg_hba.conf or
/etc/postgresql/13/main/pg_hba.conf Check that your pg_hba.conf file has the following:

    # IPv4 local connections:
    host all all all trust

Make sure to restart the Postgres service!

Create Postgres database (make sure that the server is Running in Postgres app).
If you get a "createdb is not a command" error, you need to make sure the path is properly set, see instructions above for editing path.

    createdb thetatauCMT

  If coming from the prod database need the thetatau user:

    psql
    CREATE USER thetatau;

### Install dependencies

Install requirements

    pip install -r requirements/local.txt

## Setting up Django app and creating superuser:

Activate the virtual environment created above

    workon cmt

Setup the database

    python manage.py migrate

Then you will need to create a superuser, generally locally I use
user test and email test@gmail.com and a password easy to remember (I use test)

    python manage.py createsuperuser

#### Running the server:

First you need to set the postgres variables, if you don't want to run this every time see the environment section below

    "C:\Program Files\PostgreSQL\10\pg_env.bat"

and then

    python manage.py runserver

## Environments

Find directory of our virtualenv as set up with:

    workon cmt

    cdvirtualenv

    pwd

-> output something like: `/Users/[username]/virtualenvs/cmt` or `C:\Users\[username]\Envs\cmt`

I don't want to run pg_env.bat every time so I edit the post activation file for the virtualenv

In the folder above, go to the Scripts folder and find the activate.bat file.
Add the lines at the bottom of the activate file:

```
# User defined
"C:\Program Files\PostgreSQL\10\pg_env.bat"
```

### VSCode and virtual environments

Change interpreter path in VSCode and replace it with your output from environments above.
To setup our debugger, click 'Run and Debug' and select 'Django' which will run our server

Install Black in your virtual environment, which can now be run directly in VSCode terminal.
Make sure to do `workon cmt` to activate our virtual environment and that `(cmt)` appears in front of our command line.

### To setup pycharm:

    - Add project from existing pycharm files in cloned directory
    - Ignore Django facet issue (unless you have pycharm pro)
    - File --> Settings --> Project: thetatauCMT --> Project Interpreter
        Add virtualenv configured above, set as env for project

## [Now see helpful functions](useful_functions.md)
