# Generated by Django 2.2.3 on 2019-11-11 01:21

import address.models
import django.core.validators
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
import forms.models


class Migration(migrations.Migration):

    dependencies = [
        ('address', '0002_auto_20160213_1726'),
        ('chapters', '0013_auto_20191110_1821'),
        ('forms', '0019_riskmanagement_role'),
    ]

    operations = [
        migrations.AlterField(
            model_name='audit',
            name='debit_card_access',
            field=forms.models.MultiSelectField(choices=[('None', 'None'), ('adviser', 'Adviser'), ('board member', 'Board Member'), ('committee chair', 'Committee Chair'), ('corresponding secretary', 'Corresponding Secretary'), ('employer/ee', 'Employer/Ee'), ('events chair', 'Events Chair'), ('faculty adviser', 'Faculty Adviser'), ('fundraising chair', 'Fundraising Chair'), ('house corporation president', 'House Corporation President'), ('house corporation treasurer', 'House Corporation Treasurer'), ('housing chair', 'Housing Chair'), ('other appointee', 'Other Appointee'), ('parent', 'Parent'), ('pd chair', 'Pd Chair'), ('pledge/new member educator', 'Pledge/New Member Educator'), ('project chair', 'Project Chair'), ('recruitment chair', 'Recruitment Chair'), ('regent', 'Regent'), ('risk management chair', 'Risk Management Chair'), ('rube goldberg chair', 'Rube Goldberg Chair'), ('scholarship chair', 'Scholarship Chair'), ('scribe', 'Scribe'), ('service chair', 'Service Chair'), ('social/brotherhood chair', 'Social/Brotherhood Chair'), ('treasurer', 'Treasurer'), ('vice regent', 'Vice Regent'), ('website/social media chair', 'Website/Social Media Chair')], max_length=447, verbose_name='Which members have access to the chapter debit card? Select all that apply.'),
        ),
        migrations.CreateModel(
            name='Pledge',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', models.DateTimeField(default=django.utils.timezone.now)),
                ('modified', models.DateTimeField(auto_now=True)),
                ('signature', models.CharField(help_text='Please sign using your proper/legal name', max_length=255)),
                ('title', models.CharField(choices=[('mr', 'Mr.'), ('miss', 'Miss'), ('ms', 'Ms'), ('mrs', 'Mrs')], max_length=5)),
                ('first_name', models.CharField(max_length=30, verbose_name='Legal First Name')),
                ('middle_name', models.CharField(blank=True, max_length=30, verbose_name='Full Middle Name')),
                ('last_name', models.CharField(max_length=30, verbose_name='Legal Last Name')),
                ('suffix', models.CharField(blank=True, max_length=10, verbose_name='Suffix (such as Jr., III)')),
                ('nickname', models.CharField(blank=True, help_text="If different than your first name - eg Buddy, Skip, or Mike. Do NOT indicate 'pledge names'", max_length=30)),
                ('parent_name', models.CharField(max_length=60, verbose_name='Parent / Guardian Name')),
                ('email_school', models.EmailField(help_text='We will send an acknowledgement message. (ends in .edu)', max_length=254, verbose_name='School Email')),
                ('email_personal', models.EmailField(help_text='Personal email address like @gmail.com, @yahoo.com, @outlook.com, etc', max_length=254, verbose_name='Personal Email')),
                ('phone_mobile', models.CharField(blank=True, max_length=17, validators=[django.core.validators.RegexValidator(message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed.", regex='^\\+?1?\\d{9,15}$')], verbose_name='Mobile Phone')),
                ('phone_home', models.CharField(blank=True, max_length=17, validators=[django.core.validators.RegexValidator(message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed.", regex='^\\+?1?\\d{9,15}$')], verbose_name='Home Phone')),
                ('birth_date', models.DateField()),
                ('birth_place', models.CharField(help_text='City and state or province is sufficient', max_length=50, verbose_name='Place of Birth')),
                ('grad_date', models.DateField(help_text='The year closest to your expected date of graduation', verbose_name='Expected date of graduation')),
                ('other_degrees', models.CharField(blank=True, help_text='Name of Major/Field of that Degree. If none, leave blank', max_length=60, verbose_name='College degrees already received')),
                ('relative_members', models.CharField(blank=True, help_text='Include relationship, chapter, and graduation year, if known. If none, leave blank', max_length=60, verbose_name='Indicate the names of any relatives you have who are members of Theta Tau below')),
                ('other_greeks', models.CharField(blank=True, help_text='If none, leave blank', max_length=60, verbose_name='Of which Greek Letter Honor Societies are you a member?')),
                ('other_tech', models.CharField(blank=True, help_text='If none, leave blank', max_length=60)),
                ('other_frat', models.CharField(blank=True, help_text='Other than Theta Tau -- If no other, leave blank', max_length=60)),
                ('other_college', models.CharField(blank=True, max_length=60)),
                ('explain_expelled_org', models.TextField(blank=True)),
                ('explain_expelled_college', models.TextField(blank=True)),
                ('explain_crime', models.TextField(blank=True)),
                ('loyalty', models.BooleanField(choices=[(True, 'Yes'), (False, 'No')], default=False, verbose_name='The purpose of Theta Tau shall be to develop and maintain a high standard of professional interest among its members and to unite them in a strong bond of fraternal fellowship. The members are pledged to help one another professionally and personally in a practical way, as students and as alumni, advising as to opportunities for service and advancement, warning against unethical practices and persons. Do you believe that such a fraternity is entitled to your continued support and loyalty?')),
                ('not_honor', models.BooleanField(choices=[(True, 'Yes'), (False, 'No')], default=False, verbose_name='Theta Tau is a fraternity, not an honor society. It aims to elect no one to any class of membership solely in recognition of his scholastic or professional achievements. Do you subscribe to this doctrine?')),
                ('accountable', models.BooleanField(choices=[(True, 'Yes'), (False, 'No')], default=False, verbose_name='Do you understand, if you become a member of Theta Tau, that the other members will have the right to hold you accountable for your conduct? Do you further understand that the Fraternity has Risk Management policies (hazing, alcohol, etc) with which you are expected to comply and to which you should expect others to comply?')),
                ('life', models.BooleanField(choices=[(True, 'Yes'), (False, 'No')], default=False, verbose_name='When you assume the oaths or obligations required during initiation, will you agree that they are binding on the member for life?')),
                ('unlawful', models.BooleanField(choices=[(True, 'Yes'), (False, 'No')], default=False, verbose_name='Do you promise that you will not permit the use of a Theta Tau headquarters or meeting place for unlawful purposes?')),
                ('unlawful_org', models.BooleanField(choices=[(True, 'Yes'), (False, 'No')], default=False, verbose_name='This Fraternity requires of its initiates that they shall not be members of any sect or organization which teaches or practices activities in violation of the laws of the state or the nation. Do you subscribe to this requirement?')),
                ('brotherhood', models.BooleanField(choices=[(True, 'Yes'), (False, 'No')], default=False, verbose_name='The strength of the Fraternity depends largely on the character of its members and the close and loyal friendship uniting them. Do you realize you have no right to join if you do not act on this belief?')),
                ('engineering', models.BooleanField(choices=[(True, 'Yes'), (False, 'No')], default=False, verbose_name='Theta Tau is an engineering fraternity whose student membership is limited to those regularly enrolled in a course leading to a degree in an approved engineering curriculum. Members of other fraternities that restrict their membership to any, or several engineering curricula are generally not eligible to Theta Tau, nor may our members join such fraternities. Engineering honor societies such as Tau Beta Pi, Eta Kappa Nu, etc., are not included in this classification. Do you fully understand and subscribe to that policy?')),
                ('engineering_grad', models.BooleanField(choices=[(True, 'Yes'), (False, 'No')], default=False, verbose_name='Is it your intention to practice engineering after graduation?')),
                ('payment', models.BooleanField(choices=[(True, 'Yes'), (False, 'No')], default=False, verbose_name='The Fraternity has a right to demand from you prompt payment of bills. Do you understand, and are you ready to accept, the financial obligations of becoming a member?')),
                ('attendance', models.BooleanField(choices=[(True, 'Yes'), (False, 'No')], default=False, verbose_name='The Fraternity has a right to demand from you regular attendance at meetings and faithful performance of duties entrusted to you. Are you ready to accept such obligations?')),
                ('harmless', models.BooleanField(choices=[(True, 'Yes'), (False, 'No')], default=False, verbose_name='Do you agree hereby to fully and completely release, discharge, and hold harmless the Chapter, House Corporation, Theta Tau (the national Fraternity), and their respective members, officers, agents, and any other entity whose liability is derivative by or through said released parties from all past, present and future claims, causes of action and liabilities of any nature whatsoever, regardless of the cause of the damage or loss, and including, but not limited to, claims and losses covered by insurance, claims and damages for property, for personal injury, for premises liability, for torts of any nature, and claims for compensatory damages, consequential damages or punitive/exemplary damages? Your affirmative answer binds you, under covenant, not to sue any of the previously named entities.')),
                ('alumni', models.BooleanField(choices=[(True, 'Yes'), (False, 'No')], default=False, verbose_name='As an alumnus, you should join with other alumni in the formation and support of alumni clubs or associations. Furthermore, on October 15th of each year, celebrations are held throughout the country to recall the founding of our Fraternity and to honor the Founders. Members of Theta Tau are encouraged to send some form of greeting to their chapters on or about October 15th. If several members are located in the same vicinity they could gather for an informal meeting. Will you endeavor to do these things, as circumstances permit, after you are initiated into Theta Tau?')),
                ('honest', models.BooleanField(choices=[(True, 'Yes'), (False, 'No')], default=False, verbose_name='My answers to these questions are my honest and sincere convictions.')),
                ('address', address.models.AddressField(on_delete=django.db.models.deletion.PROTECT, to='address.Address')),
                ('major', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='pledges', to='chapters.ChapterCurricula')),
                ('school_name', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='pledge_forms_full', to='chapters.Chapter', to_field='school')),
            ],
            options={
                'abstract': False,
            },
        ),
    ]