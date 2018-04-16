from django.contrib.auth.models import User
from django.db import models


from processlib.models import Process


class Person(models.Model):
    pass


class Organisation(models.Model):
    pass


class DemoOrderProcess(Process):
    person = models.ForeignKey(Person, on_delete=models.SET_NULL, null=True)
    organisation = models.ForeignKey(Organisation, on_delete=models.SET_NULL, null=True)

    erp_order_id = models.CharField(max_length=255, default='', blank=True)


class CampaignParticipationProcess(Process):
    person = models.ForeignKey(Person, on_delete=models.SET_NULL, null=True)
    organisation = models.ForeignKey(Organisation, on_delete=models.SET_NULL, null=True)

    target_campaign_id = models.CharField(max_length=255, default='')
    target_step_id = models.CharField(max_length=255, default='')

    event_title = models.CharField(max_length=255, default='')
    event_text = models.CharField(max_length=255, default='')
    event_id = models.CharField(max_length=255, default='')

    def has_erp_order(self):
        return False
