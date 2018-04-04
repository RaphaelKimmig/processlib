from django.utils import timezone

from processlib.tasks import run_async_activity


class Activity(object):
    def __init__(self, flow, process, instance, name, description=None, permissions=None,
                 skip_if=None):
        self.flow = flow
        self.process = process
        self.description = description
        self.permissions = permissions
        self.name = name
        self.instance = instance
        self._skip = skip_if

    def should_skip(self):
        if not self._skip:
            return False
        return self._skip(self)

    def should_wait(self):
        return False

    def has_view(self):
        return False

    def __str__(self):
        return self.name

    def __repr__(self):
        return '{}(name="{}")'.format(self.__class__.__name__, self.name)

    def instantiate(self, predecessor=None):
        assert not self.instance
        self.instance = self.flow.activity_model(
            process=self.process,
            activity_name=self.name,
        )
        self.instance.save()
        if predecessor:
            self.instance.predecessors.add(predecessor.instance)

    def start(self):
        assert self.instance.status == self.instance.STATUS_INSTANTIATED
        if not self.instance.started_at:
            self.instance.started_at = timezone.now()
        self.instance.status = self.instance.STATUS_STARTED

    def finish(self):
        assert self.instance.status == self.instance.STATUS_STARTED
        if not self.instance.finished_at:
            self.instance.finished_at = timezone.now()
        self.instance.status = self.instance.STATUS_FINISHED
        self.instance.save()
        self._instantiate_next_activities()

    def cancel(self):
        assert self.instance.status == self.instance.STATUS_INSTANTIATED
        self.instance.status = self.instance.STATUS_CANCELED
        self.instance.save()

    def undo(self):
        assert self.instance.status == self.instance.STATUS_FINISHED
        self.instance.finished_at = None
        self.instance.status = self.instance.STATUS_INSTANTIATED
        self.instance.save()

    def _get_next_activities(self):
        for activity_name in self.flow._out_edges[self.name]:
            activity = self.flow._get_activity_by_name(
                process=self.process, activity_name=activity_name
            )
            if activity.should_skip():
                for later_activity in activity._get_next_activities():
                    yield later_activity
            else:
                yield activity

    def _instantiate_next_activities(self):
        for activity in self._get_next_activities():
            activity.instantiate(predecessor=self)


class State(Activity):
    """
    An activity that simple serves as a marker for a certain state being reached, e.g.
    if the activity before it was conditional.
    """
    def instantiate(self, predecessor=None):
        super(State, self).instantiate(predecessor)
        self.start()
        self.finish()


class ViewActivity(Activity):
    def __init__(self, view=None, **kwargs):
        self.view = view
        super(ViewActivity, self).__init__(**kwargs)

    def has_view(self):
        return True

    def dispatch(self, request, *args, **kwargs):
        kwargs['activity'] = self
        return self.view(request, *args, **kwargs)


class FunctionActivity(Activity):
    def __init__(self, callback=None, **kwargs):
        self.callback = callback
        super(FunctionActivity, self).__init__(**kwargs)

    def instantiate(self, predecessor=None):
        super(FunctionActivity, self).instantiate(predecessor)
        self.start()

    def start(self):
        super(FunctionActivity, self).start()
        self.callback(self)
        self.finish()


class AsyncActivity(Activity):
    def __init__(self, callback=None, **kwargs):
        self.callback = callback
        super(AsyncActivity, self).__init__(**kwargs)

    def instantiate(self, predecessor=None):
        super(AsyncActivity, self).instantiate(predecessor)
        run_async_activity.delay(self.flow.label, self.instance.pk)

    def start(self):
        super(AsyncActivity, self).start()
        self.callback(self)


class StartMixin(Activity):
    def instantiate(self, predecessor=None):
        assert not self.instance
        assert not predecessor
        self.instance = self.flow.activity_model(
            process=self.process,
            activity_name=self.name,
        )

    def finish(self):
        assert self.instance.status == self.instance.STATUS_STARTED
        if not self.instance.finished_at:
            self.instance.finished_at = timezone.now()

        self.process.save()
        self.instance.process = self.process
        self.instance.status = self.instance.STATUS_FINISHED
        self.instance.save()
        self._instantiate_next_activities()


class StartActivity(StartMixin, Activity):
    pass


class StartViewActivity(StartMixin, ViewActivity):
    pass


class EndActivity(Activity):
    def instantiate(self, predecessor=None):
        super(EndActivity, self).instantiate(predecessor)
        self.start()
        self.finish()

    def finish(self):
        super(EndActivity, self).finish()

        if not self.process.finished_at:
            self.process.finished_at = self.instance.finished_at
            self.process.save(update_fields=['finished_at'])


class FormActivity(Activity):
    def __init__(self, form_class=None, **kwargs):
        self.form_class = form_class
        super(FormActivity, self).__init__(**kwargs)

    def get_form(self, **kwargs):
        return self.form_class(**kwargs)


class StartFormActivity(StartMixin, FormActivity):
    pass


class IfElse(Activity):
    def __init__(self, flow, process, instance, name, description=None, permissions=None,
                 skip_if=None):
        super(IfElse, self).__init__(flow, process, instance, name, description, permissions, skip_if)


class Wait(Activity):
    def __init__(self, flow, process, instance, name, description=None, permissions=None,
                 skip_if=None, wait_for=None):
        super(Wait, self).__init__(flow, process, instance, name, description, permissions, skip_if)

        if not wait_for:
            raise ValueError("Wait activity needs to wait for something.")


        self._wait_for = set(wait_for) if wait_for else None

    def _find_existing_instance(self, predecessor):
        candidates = list(self.flow.activity_model.objects.filter(
            process=self.process,
            activity_name=self.name,
        ))

        for candidate in candidates:
            # FIXME this only corrects for simple loops, may fail with more complex scenarios
            if not candidate.successors.filter(status=candidate.STATUS_FINISHED,
                                               activity_name=self.name ).exists():
                return candidate

        raise self.flow.activity_model.DoesNotExist()

    def instantiate(self, predecessor=None):
        if predecessor is None:
            raise ValueError("Can't wait for something without a predecessor.")

        # find the instance
        try:
            self.instance = self._find_existing_instance(predecessor)
        except self.flow.activity_model.DoesNotExist:
            self.instance = self.flow.activity_model(
                process=self.process,
                activity_name=self.name,
            )
            self.instance.save()

        self.instance.predecessors.add(predecessor.instance)
        self.start()

    def start(self):
        if not self.instance.started_at:
            self.instance.started_at = timezone.now()

        self.instance.status = self.instance.STATUS_STARTED
        self.instance.save()

        predecessor_names = {instance.activity_name for instance in self.instance.predecessors.all()}
        if self._wait_for.issubset(predecessor_names):
            self.finish()

