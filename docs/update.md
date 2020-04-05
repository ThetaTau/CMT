# Update Packages

> pip list --outdated

Update all packages listed in the requirements files.

> pip install -r filename.txt

> pip freeze | cut -d'=' -f1 | xargs -n1 pip install -U

> pip install -r filename.txt

