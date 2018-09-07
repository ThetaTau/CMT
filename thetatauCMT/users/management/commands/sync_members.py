# Generated by Django 2.0.3 on 2018-06-15 18:31
import io
import os
import csv
import re
import datetime
import warnings
from django.core.management import BaseCommand
from django.utils import timezone
from django.conf import settings
from users.models import User, UserRoleChange, UserStatusChange
from django.db import models, transaction
from django.db.utils import IntegrityError
from core.models import ALL_OFFICERS, TODAY_END, forever
from chapters.models import Chapter
from pydrive.drive import GoogleDrive
from pydrive.auth import GoogleAuth, AuthenticationError
from django.core.mail import send_mail


class Command(BaseCommand):
    # Show this when the user types help
    help = "Sync members with an export from the CRM from central"

    # A command must define handle()
    def handle(self, *args, **options):
        run_time = datetime.datetime.now()
        change_messages = []
        id_file = os.path.join(settings.ROOT_DIR.root, r'secrets/GoogleSheetsClient_id.json')
        id_file_out = os.path.join(settings.ROOT_DIR.root, r'secrets/GoogleSheetsClient_id_out.json')
        GoogleAuth.DEFAULT_SETTINGS['client_config_file'] = id_file
        GoogleAuth.DEFAULT_SETTINGS['save_credentials_backend'] = 'file'
        GoogleAuth.DEFAULT_SETTINGS['save_credentials'] = True
        GoogleAuth.DEFAULT_SETTINGS['save_credentials_file'] = id_file_out
        GoogleAuth.DEFAULT_SETTINGS['oauth_scope'].append(
            'https://www.googleapis.com/auth/drive.file')
        GAUTH = GoogleAuth()
        GAUTH.LocalWebserverAuth()
        DRIVE = GoogleDrive(GAUTH)
        FOLDER_ID = '0BwvK5gYQ6D4nV0pNSnlhd1Z5Z2M'
        results = DRIVE.ListFile({
            'q': f"'{FOLDER_ID}' in parents"}).GetList()
        items = results
        if not items:
            print('No files found in folder.')
            return
        last_date = datetime.datetime.today() - datetime.timedelta(days=30)
        for item in items:
            file_name = item['title']
            if file_name.startswith('2'):
                this_date = datetime.datetime.strptime(file_name[:8], '%Y%m%d')
                if this_date > last_date:
                    last_date = this_date
                    final_file = file_name
                    file = item
        change_messages.append(f"Update file: {final_file} id: {file}")
        content = file.GetContentString(mimetype='text/csv', encoding='latin_1')
        reader = csv.DictReader(io.StringIO(content))
        trans = {
            'badge2': 'Constituent Specific Attributes ChapRoll Description',
            'badge': 'Constituent ID',
            'chapter': 'Constituent Specific Attributes Chapter Name Description',
            'roll': 'Constituent Specific Attributes Roll Number Description',
            'status': 'Constituency Code',
            'first': 'First Name',
            'middle': 'Middle Name',
            'last': 'Last Name',
            'phone': 'Mobile Phone Number',
            'email': 'Email Address Number',
            'school': 'Primary Education School Name',
            'major': 'Constituent Specific Attributes y_Major Description',
            'grad': 'Primary Education Class of',
            'start': 'Organization Relation From Date',
            'end': 'Organization Relation To Date',
            'role': 'Organization Relation Relationship',
            'role2': 'Organization Relation Position'}
        alumni_pending = []
        active_list = []
        for id_obj, row in enumerate(reader):
            print(id_obj)
            user_id = row[trans['badge']]
            check_badge = False
            if user_id.startswith('UA'):
                user_id = user_id.replace('UA', 'Albany')
            elif user_id.startswith('CFS'):
                user_id = user_id.replace('CFS', 'CSF')
            try:
                user_obj = User.objects.get(user_id=user_id,
                                            first_name=row[trans['first']])
            except User.DoesNotExist:
                # Maybe the user was a pledge last? Check if badge number
                try:
                    int(user_id)
                    user_obj = User.objects.get(
                        badge_number=user_id, first_name=row[trans['first']])
                except (User.DoesNotExist, ValueError):
                    try:
                        # Let's try to get by email
                        user_obj = User.objects.get(username=row[trans['email']])
                        check_badge = True
                    except User.DoesNotExist:
                        try:
                            # Maybe something has been mixed up and the badge2 is right?
                            user_obj = User.objects.get(user_id=row[trans['badge2']])
                        except User.DoesNotExist:
                            user_obj = None
            phone = row[trans['phone']]
            if phone != "" and 'x' not in phone and (8 < len(phone) < 18):
                rep = {"_": "", "(": "", ")": " ", "-": "", ' ': '', '1 ': '', '+': '', " ": ""}
                rep = dict((re.escape(k), v) for k, v in rep.items())
                pattern = re.compile("|".join(rep.keys()))
                phone = pattern.sub(lambda m: rep[re.escape(m.group(0))], phone)
                phone = phone.replace(" ", "")
                try:
                    phone = int(phone)
                    phone = str(phone)
                except ValueError:
                    phone = ''
            else:
                phone = ''
            if row[trans['grad']]:
                graduation = int(row[trans['grad']])
            else:
                graduation = datetime.date.today().year + 1
            try:
                chapter_obj = Chapter.objects.get(name=row[trans['chapter']])
            except Chapter.DoesNotExist:
                chapter_obj = Chapter.objects.get(school=row[trans['school']])
            roll = row[trans['roll']]
            if roll == '':
                # This is likely a pledge, need to get value from badge
                # This is b/c colonies have auto added char abbreviation
                roll = user_id
                roll = ''.join([s for s in list(roll) if s.isdigit()])
                if roll:
                    roll = int(roll)
            if user_obj is None:
                change_messages.append(f"No user found, create one now: {row}")
                if row[trans['email']] == '':
                    # warnings.warn(f"No email for user: {row}")
                    continue
                user_obj = User(
                    username=row[trans['email']],
                    first_name=row[trans['first']],
                    last_name=row[trans['last']],
                    email=row[trans['email']],
                    name=row[trans['first']] + ' ' + row[trans['last']],
                    badge_number=roll,
                    major=row[trans['major']],
                    graduation_year=graduation,
                    phone_number=phone,
                    chapter=chapter_obj,
                )
                user_obj.save()
            else:
                email = row[trans['email']]
                if user_obj.email != email and email != '':
                    change_messages.append(f"Update User: {user_obj}"
                                           f" Change: email, username; old: {user_obj.email} new: {email}")
                    user_obj.email = email
                if user_obj.phone_number != phone and phone != '':
                    change_messages.append(f"Update User: {user_obj}"
                                           f" Change: phone; old: {user_obj.phone_number} new: {phone}")
                    user_obj.phone_number = phone
                major = row[trans['major']]
                if user_obj.major != major and major != '':
                    change_messages.append(f"Update User: {user_obj}"
                                           f" Change: major; old: {user_obj.major} new: {major}")
                    user_obj.major = major
                if user_obj.graduation_year != graduation and graduation != '':
                    change_messages.append(f"Update User: {user_obj}"
                                           f" Change: graduation_year; "
                                           f" old: {user_obj.graduation_year} new: {graduation}")
                    user_obj.graduation_year = graduation
                if check_badge:
                    if user_obj.user_id != user_id:
                        if user_obj.user_id != f"{chapter_obj.greek}{roll}":
                            user_obj.user_id = f"{chapter_obj.greek}{roll}"
                            user_obj.badge_number = roll
                            change_messages.append(f"Update User: {user_obj}"
                                                   f" Change: user_id, badge_number;"
                                                   f" old: {user_id} new: {user_obj.user_id}")
                            try:
                                with transaction.atomic():
                                    user_obj.save()
                            except IntegrityError as e:
                                pass
                else:
                    user_obj.save()
            status = row[trans['status']]
            if 'pledge' in status.lower():
                status = 'pnm'
            else:
                status = 'active'
            if status == 'active':
                active_list.append(user_obj.pk)
            end = datetime.date(graduation, 7, 1)
            try:
                status_obj = UserStatusChange.objects.get(
                    user=user_obj,
                    status=status
                )
            except UserStatusChange.DoesNotExist:
                change_messages.append(f"New status for user {user_obj} {status}")
                status_obj = UserStatusChange(
                    user=user_obj,
                    status=status,
                    start=timezone.now(),
                    end=end
                )
                status_obj.save()
            else:
                # status_obj.start = timezone.now(),
                if status_obj.end != end:
                    change_messages.append(f"Update Status: {status_obj} for {status_obj.user}"
                                           f" Change: end; old: {status_obj.end} new: {end}")
                status_obj.end = end
                status_obj.save()
            # Need to find other status that is not this one
            # and update it if it is a current status
            other_statuss = user_obj.status.filter(
                ~models.Q(pk=status_obj.pk),
                # start__lte=TODAY_END,
                # end__gte=TODAY_END
            )
            # at the end we need to check all alumnipend not kept to update to alumni?
            for other_status in other_statuss:
                if other_status.status.lower() == 'colony':
                    other_status.delete()
                    continue
                if other_status.status == 'alumnipend':
                    # If the central status is active
                    # and the current status is alumnipend, keep alumnipend
                    alumni_pending.append(user_obj.pk)
                    if status_obj.status == 'active':
                        status_obj.end = other_status.start - datetime.timedelta(days=1)
                        status_obj.save()
                        other_status.end = forever()
                        other_status.save()
                        change_messages.append(f"Remove active status because alumnipend {user_obj}")
                        continue
                elif other_status.status == 'activepend':
                    # If the central status is pledge
                    # and the current status is activepend, keep activepend
                    if status_obj.status == 'pnm':
                        status_obj.end = other_status.start - datetime.timedelta(days=1)
                        status_obj.save()
                        other_status.end = forever()
                        other_status.save()
                        change_messages.append(f"Remove pledge status because activepend {user_obj}")
                        continue
                elif other_status.status == 'alumni':
                    # A current active/pledge should not have alumni status
                    other_status.delete()
                    continue
                elif other_status.status == 'active':
                    if status_obj.status == 'pnm':
                        # A current pledge should not have other active status
                        other_status.delete()
                        continue
                # The remaining status should be pledge or
                # activepend that is no longer pending
                # If the central is active and current is activepend; update
                other_status.end = status_obj.start - datetime.timedelta(days=1)
                other_status.save()
                change_messages.append(f"Remove old status {other_status} for new {status_obj} for {user_obj}")
            if row[trans['role']] != '':
                if row[trans['start']] == '':
                    start = datetime.datetime.now()
                else:
                    start = datetime.datetime.strptime(row[trans['start']], '%m/%d/%Y')
                start = start.date()
                if row[trans['end']] == '':
                    end = datetime.datetime.now() + datetime.timedelta(days=90)
                else:
                    end = datetime.datetime.strptime(row[trans['end']], '%m/%d/%Y')
                end = end.date()
                final_role = row[trans['role']].lower()
                if final_role not in ALL_OFFICERS:
                    # Find the best matching name
                    if 'employer' in final_role:
                        final_role = 'employer/ee'
                        user_obj.employer_position = row[trans['role2']]
                    elif 'alumni' in final_role:
                        final_role = 'adviser'
                    else:
                        warnings.warn(f"Role {final_role} does not exist!")
                        continue
                try:
                    # We need to check if similar role already exists
                    role_obj = UserRoleChange.objects.get(
                        user=user_obj,
                        role=final_role)
                except UserRoleChange.DoesNotExist:
                    role_obj = None
                except UserRoleChange.MultipleObjectsReturned:
                    try:
                        # See if same start will narrow down
                        role_obj = UserRoleChange.objects.get(
                            user=user_obj,
                            role=final_role,
                            start=start)
                    except UserRoleChange.DoesNotExist:
                        role_obj = None
                    except UserRoleChange.MultipleObjectsReturned:
                        try:
                            role_obj = UserRoleChange.objects.get(
                                user=user_obj,
                                role=final_role,
                                start=start,
                                end=end)
                            continue
                        except UserRoleChange.DoesNotExist:
                            role_obj = None
                        except UserRoleChange.MultipleObjectsReturned:
                            continue
                if role_obj is None:
                    change_messages.append(f"New role for user {user_obj} {final_role}")
                    role_obj = UserRoleChange(
                        user=user_obj,
                        role=final_role,
                        start=start,
                        end=end
                    )
                    role_obj.save()
                else:
                    if role_obj.start != start:
                        change_messages.append(f"Update Role: {role_obj} for {role_obj.user}"
                                               f" Change: start; old: {role_obj.start} new: {start}")
                    role_obj.start = start
                    if role_obj.end != end:
                        change_messages.append(f"Update Role: {role_obj} for {role_obj.user}"
                                               f" Change: end; old: {role_obj.end} new: {end}")
                    role_obj.end = end
                    role_obj.save()
            alumnipends = UserStatusChange.objects.filter(
                ~models.Q(user__pk__in=alumni_pending),
                status='alumnipend',
                start__lte=TODAY_END,
                end__gte=TODAY_END)
            # If we are not keeping alumni_pending, need to add as alumni
            for alumnipend in alumnipends:
                UserStatusChange(
                    user=alumnipend.user,
                    status='alumni',
                    start=datetime.date.today(),
                    end=forever()
                ).save()
                change_messages.append(f"Removing left alumnipend {alumnipend.user}")
                alumnipend.end = datetime.date.today() - datetime.timedelta(days=1)
                alumnipend.save()
            all_old_actives = UserStatusChange.objects.filter(
                ~models.Q(user__pk__in=active_list),
                status='active',
                start__lte=TODAY_END,
                end__gte=TODAY_END)
            # If actives are not in CRM export, and in CMT as active, need to alumni
            for active in all_old_actives:
                UserStatusChange(
                    user=active.user,
                    status='alumni',
                    start=datetime.date.today(),
                    end=forever()
                ).save()
                change_messages.append(f"Removing left active {active.user}")
                active.end = datetime.date.today() - datetime.timedelta(days=1)
                active.save()
        change_message = '\n'.join(change_messages)
        send_mail(f'CMT Sync {run_time}',
                  f'Updated:\n{change_message}',
                  'cmt@thetatau.org',
                  ['cmt@thetatau.org'],
                  fail_silently=True)
