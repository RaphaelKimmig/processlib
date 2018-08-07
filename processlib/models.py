import uuid
import string

import six
from django.conf import settings
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import ugettext_lazy as _


from six import python_2_unicode_compatible


def validate_flow_label(value):
    from .flow import _FLOWS

    if value not in _FLOWS:
        raise ValidationError(
            "Unknown flow label {}, available: ".format(value, ", ".join(_FLOWS.keys()))
        )
    return value


def is_format_string(value):
    try:
        parsed = next(string.Formatter().parse(six.text_type(value)))
    except ValueError:
        return False

    return parsed[1] is not None


@python_2_unicode_compatible
class Process(models.Model):
    STATUS_STARTED = "started"
    STATUS_CANCELED = "canceled"
    STATUS_DONE = "done"

    STATUS_CHOICES = (
        (STATUS_STARTED, _("started")),
        (STATUS_CANCELED, _("canceled")),
        (STATUS_DONE, _("done")),
    )

    search_fields = ["id"]

    status = models.CharField(
        default=STATUS_STARTED, max_length=16, choices=STATUS_CHOICES
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    flow_label = models.CharField(max_length=255, validators=[validate_flow_label])

    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    @property
    def activity_instances(self):
        return self.flow.activity_model._default_manager.filter(process_id=self.pk)

    def __str__(self):
        if not self.flow:
            return six.text_type(self.id)
        if self.flow.verbose_name:
            return six.text_type(self.flow.verbose_name)
        return self.flow.name

    @property
    def full(self):
        return self.flow.process_model._default_manager.get(pk=self.pk)

    def can_cancel(self, user=None):
        return (
            self.status not in (self.STATUS_DONE, self.STATUS_CANCELED)
            and not
            # FIXME allow cancelation of scheduled instances
            self._activity_instances.filter(
                status=ActivityInstance.STATUS_SCHEDULED
            ).exists()
        )

    @property
    def description(self):
        flow_description = six.text_type(self.flow.description or self.flow)
        if not is_format_string(flow_description):
            return flow_description
        try:
            return flow_description.format(process=self)
        except (AttributeError, KeyError):
            return flow_description.format(process=self.full)

    @property
    def flow(self):
        """
        :rtype: processlib.flow.Flow
        """
        from .flow import get_flow

        return get_flow(self.flow_label)

    class Meta:
        verbose_name = _("Process")
        ordering = ("-finished_at", "-started_at")


class ActivityInstance(models.Model):
    STATUS_INSTANTIATED = "instantiated"
    STATUS_SCHEDULED = "scheduled"
    STATUS_STARTED = "started"
    STATUS_CANCELED = "canceled"
    STATUS_DONE = "done"
    STATUS_ERROR = "error"

    STATUS_CHOICES = (
        (STATUS_INSTANTIATED, _("instantiated")),
        (STATUS_SCHEDULED, _("scheduled")),
        (STATUS_STARTED, _("started")),
        (STATUS_CANCELED, _("canceled")),
        (STATUS_DONE, _("done")),
        (STATUS_ERROR, _("error")),
    )

    status = models.CharField(
        default=STATUS_INSTANTIATED, max_length=16, choices=STATUS_CHOICES
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    process = models.ForeignKey(
        Process, related_name="_activity_instances", on_delete=models.CASCADE
    )
    activity_name = models.CharField(max_length=255)

    predecessors = models.ManyToManyField(
        "self", related_name="successors", symmetrical=False
    )

    instantiated_at = models.DateTimeField(auto_now_add=True)
    scheduled_at = models.DateTimeField(null=True)
    started_at = models.DateTimeField(null=True)
    finished_at = models.DateTimeField(null=True)

    modified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )

    assigned_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True
    )
    assigned_group = models.ForeignKey(Group, on_delete=models.SET_NULL, null=True)

    def __repr__(self):
        return '{}(activity_name="{}")'.format(
            self.__class__.__name__, self.activity_name
        )

    def save(
        self, force_insert=False, force_update=False, using=None, update_fields=None
    ):
        if not self.activity_name:
            raise ValueError("Missing activity name")
        super(ActivityInstance, self).save(
            force_insert, force_update, using, update_fields
        )

    @property
    def has_active_successors(self):
        return self.successors.exclude(status=self.STATUS_CANCELED).exists()

    @property
    def activity(self):
        return self.process.flow.get_activity_by_instance(self)
