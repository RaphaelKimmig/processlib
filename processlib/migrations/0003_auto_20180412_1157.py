# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('processlib', '0002_auto_20180403_1633'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='process',
            options={'verbose_name': 'Process'},
        ),
        migrations.AlterField(
            model_name='process',
            name='finished_at',
            field=models.DateTimeField(null=True, blank=True),
        ),
        migrations.AlterField(
            model_name='process',
            name='started_at',
            field=models.DateTimeField(null=True, blank=True),
        ),
    ]
