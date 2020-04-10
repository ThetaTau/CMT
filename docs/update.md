# Update

To turn on the maintenance mode create the file maintenance_active in main directory
> nano maintenance_active

> pip list --outdated

Update all packages listed in the requirements files.

Run for either production.txt or local.txt depending on environment

> pip install -r filename.txt

> pip freeze | cut -d'=' -f1 | xargs -n1 pip install -U

> pip install -r filename.txt

