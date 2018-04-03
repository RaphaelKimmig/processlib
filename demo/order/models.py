from django.db import models

from processlib.models import Process


class OrderConfig(models.Model):
    """Configure which articles should be available when ordering."""
    ask_for_token = models.BooleanField()
    require_token = models.BooleanField()

    available_articles = models.TextField()


class OrderProcess(Process):
    config = models.ForeignKey(OrderConfig, on_delete=models.CASCADE)

    token = models.CharField(max_length=255, default='')
    organization_id = models.CharField(max_length=255, default='')
    person_id = models.CharField(max_length=255, default='')

    recipient = models.TextField()
    articles = models.TextField()
