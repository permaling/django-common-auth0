# Generated by Django 3.2.20 on 2023-08-28 08:40

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0001_squashed_0024_auto_20230703_1632'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='ljorganization',
            name='apps_limit_number',
        ),
        migrations.RemoveField(
            model_name='ljorganization',
            name='jots_limit_number',
        ),
        migrations.RemoveField(
            model_name='ljorganization',
            name='play_apps_limit_number',
        ),
    ]
