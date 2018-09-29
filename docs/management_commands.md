# Management Commands
### Update Balances
To update the balances of chapters

    python manage.py update_balances file_path
    # eg. python manage.py update_balances secrets/Balances090518.csv
### Export Forms
To send the central office the recent forms

    python manage.py export_forms %PASSWORD% date_start
    # python manage.py export_forms %PASSWORD% 20180917
Optional:

    # -date_end 20180920
    # Form to not send to central
    # -exclude 'mscr, init, depledge, coop, oer'
### Sync Members
To sync members with an export from the central office
The most recent export will automatically be found
in the google drive folder
    
    python manage.py sync_members
