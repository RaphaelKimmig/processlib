# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import processlib.models


class Migration(migrations.Migration):

    dependencies = [
        ('processlib', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='process',
            name='flow_label',
            field=models.CharField(max_length=255, validators=[processlib.models.validate_flow_label]),
        ),
    ]
