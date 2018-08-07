from __future__ import unicode_literals

from collections import OrderedDict, defaultdict

import six
from django.utils import timezone
from six import python_2_unicode_compatible

from .models import Process, ActivityInstance

_FLOWS = {}


def get_flows():
    return _FLOWS.items()


def get_flow(label):
    return _FLOWS[label]


def flow_label(flow):
    return flow.name  # FIXME app label?


def register_flow(flow):
    if flow.label in _FLOWS:
        raise ValueError("Flow {} already registered".format(flow.label))
    _FLOWS[flow.label] = flow


@python_2_unicode_compatible
class Flow(object):
    def __init__(
        self,
        name,
        process_model=Process,
        activity_model=ActivityInstance,
        verbose_name="",
        description="",
        permission=None,
        auto_create_permission=True,
    ):
        self.name = name
        self.activity_model = activity_model
        self.verbose_name = verbose_name
        self.process_model = process_model
        self._activities = OrderedDict()
        self._activity_kwargs = {}
        self._in_edges = defaultdict(list)
        self._out_edges = defaultdict(list)
        self.label = flow_label(self)
        self.description = description
        self.permission = permission
        self.auto_create_permission = auto_create_permission

        register_flow(self)

    def has_any_permissions(self):
        return self.permission or any(
            self._get_activity_by_name(None, activity_name).permission
            for activity_name in self._activities
        )

    def __str__(self):
        return six.text_type(self.verbose_name or self.name)

    def start_with(self, activity_name, activity, **activity_kwargs):
        if self._activities:
            raise ValueError("start_with has to be the first activity added")

        self._activities[activity_name] = activity
        self._activity_kwargs[activity_name] = activity_kwargs
        return self

    def and_then(self, activity_name, activity, **activity_kwargs):
        predecessor = list(self._activities)[
            -1
        ]  # implicitly connect to previously added
        return self.add_activity(
            activity_name, activity, predecessor, **activity_kwargs
        )

    def add_activity(
        self, activity_name, activity, after=None, wait_for=None, **activity_kwargs
    ):
        if not self._activities:
            raise ValueError("A start activity has to be added first with start_with")

        if after is None:
            after = list(self._activities)[-1]  # implicitly connect to previously added

        predecessors = [after] if after else []

        if wait_for:
            if isinstance(wait_for, six.string_types):
                raise TypeError("wait_for should be a list or tuple")

            activity_kwargs["wait_for"] = wait_for

            for name in wait_for:
                if name not in predecessors:
                    predecessors.append(name)

                if self._activity_kwargs[name].get("skip_if"):
                    raise ValueError("Never wait for conditional activities.")

        for predecessor in predecessors:
            self._out_edges[predecessor].append(activity_name)
            self._in_edges[activity_name].append(predecessor)

        self._activities[activity_name] = activity
        self._activity_kwargs[activity_name] = activity_kwargs

        return self

    def _get_activity_by_name(self, process, activity_name):
        return self._activities[activity_name](
            flow=self,
            process=process,
            instance=None,
            name=activity_name,
            **self._activity_kwargs[activity_name]
        )

    def get_activity_by_instance(self, instance):
        activity_name = instance.activity_name
        process = self.process_model._default_manager.get(pk=instance.process_id)
        kwargs = self._activity_kwargs[activity_name]
        return self._activities[activity_name](
            flow=self, process=process, instance=instance, name=activity_name, **kwargs
        )

    def get_start_activity(
        self, process_kwargs=None, activity_instance_kwargs=None, request=None
    ):
        process = self.process_model(
            flow_label=self.label,
            started_at=timezone.now(),
            status=self.process_model.STATUS_STARTED,
            **(process_kwargs or {})
        )
        activity = self._get_activity_by_name(process, list(self._activities)[0])
        activity.instantiate(instance_kwargs=activity_instance_kwargs, request=request)
        return activity
