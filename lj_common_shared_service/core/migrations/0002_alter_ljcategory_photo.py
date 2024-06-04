# Generated by Django 3.2.20 on 2023-08-28 08:40

from django.db import migrations, models
import lj_common_shared_service.utils.file


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0001_squashed_0009_auto_20230703_1643'),
    ]

    operations = [
        migrations.AlterField(
            model_name='ljcategory',
            name='photo',
            field=models.ImageField(blank=True, default=None, null=True, upload_to=lj_common_shared_service.utils.file.LJRandomFileName(''), verbose_name='Preview photo'),
        ),
    ]
