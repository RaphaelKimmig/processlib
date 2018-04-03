import uuid

from django.db import models
from six import python_2_unicode_compatible


@python_2_unicode_compatible
class Process(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    flow_label = models.CharField(max_length=255)

    started_at = models.DateTimeField(null=True)
    finished_at = models.DateTimeField(null=True)

    @property
    def activity_instances(self):
        return self.flow.activity_model._default_manager.filter(process_id=self.pk)

    def __str__(self):
        if self.flow:
            return "{} {}".format(self.flow, self.id)
        return str(self.id)

    def save(self, force_insert=False, force_update=False, using=None, update_fields=None):
        assert self.flow_label
        super(Process, self).save(force_insert, force_update, using, update_fields)

    @property
    def flow(self):
        """
        :rtype: processlib.flow.Flow
        """
        from processlib.flow import get_flow
        return get_flow(self.flow_label)


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

    def __repr__(self):
        return '{}(activity_name="{}")'.format(self.__class__.__name__, self.activity_name)

    def save(self, force_insert=False, force_update=False, using=None, update_fields=None):
        if not self.activity_name:
            raise ValueError("Missing")
        super(ActivityInstance, self).save(force_insert, force_update, using, update_fields)

    @property
    def activity(self):
        return self.process.flow.get_activity_by_instance(self)
