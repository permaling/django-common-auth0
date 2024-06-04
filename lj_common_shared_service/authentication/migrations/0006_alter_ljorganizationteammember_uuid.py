# Generated by Django 3.2.20 on 2023-09-11 17:05

from django.db import migrations, models
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0005_ljorganizationteammember_uuid'),
    ]

    operations = [
        migrations.AlterField(
            model_name='ljorganizationteammember',
            name='uuid',
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True, verbose_name='Unique UUID hash'),
        ),
    ]
