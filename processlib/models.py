import uuid

from django.conf import settings
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import ugettext_lazy as _

from six import python_2_unicode_compatible


def validate_flow_label(value):
    from .flow import _FLOWS
    if value not in _FLOWS:
        raise ValidationError("Unknown flow label {}, available: ".format(
            value, ', '.join(_FLOWS.keys())
        ))
    return value


@python_2_unicode_compatible
class Process(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    flow_label = models.CharField(max_length=255, validators=[validate_flow_label])

    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    @property
    def activity_instances(self):
        return self.flow.activity_model._default_manager.filter(process_id=self.pk)

    def __str__(self):
        if self.flow:
            return "{} {}".format(str(self.flow), str(self.id))
        return str(self.id)

    @property
    def full(self):
        return self.flow.process_model._default_manager.get(pk=self.pk)

    @property
    def description(self):
        try:
            return self.flow.description.format(process=self)
        except KeyError:
            try:
                return self.flow.description.format(process=self.full)
            except KeyError:
                pass
        return self.flow.description

    @property
    def flow(self):
        """
        :rtype: processlib.flow.Flow
        """
        from .flow import get_flow
        return get_flow(self.flow_label)

    class Meta:
        verbose_name = _("Process")


class ActivityInstance(models.Model):
    STATUS_INSTANTIATED = 'instantiated'
    STATUS_STARTED = 'started'
    STATUS_CANCELED = 'canceled'
    STATUS_FINISHED = 'finished'
    STATUS_ERROR = 'ERROR'

    status = models.CharField(default=STATUS_INSTANTIATED, max_length=16)

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    process = models.ForeignKey(Process, related_name='_activity_instances',
                                on_delete=models.CASCADE)
    activity_name = models.CharField(max_length=255)

    predecessors = models.ManyToManyField('self', related_name='successors', symmetrical=False)

    instantiated_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True)
    finished_at = models.DateTimeField(null=True)

    assigned_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                      null=True)
    assigned_group = models.ForeignKey(Group, on_delete=models.SET_NULL, null=True)

    def __repr__(self):
        return '{}(activity_name="{}")'.format(self.__class__.__name__, self.activity_name)

    def save(self, force_insert=False, force_update=False, using=None, update_fields=None):
        if not self.activity_name:
            raise ValueError("Missing")
        super(ActivityInstance, self).save(force_insert, force_update, using, update_fields)

    @property
    def activity(self):
        return self.process.flow.get_activity_by_instance(self)
