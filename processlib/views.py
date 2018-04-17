from django.contrib import messages
from django.http import HttpResponseRedirect
from django.template import TemplateDoesNotExist
from django.template.loader import get_template
from django.urls import reverse
from django.utils.translation import ugettext_lazy as _
from django.views import View
from django.views.generic import ListView, DetailView, UpdateView
from rest_framework import viewsets

from .flow import (get_flows, get_flow)
from .models import Process, ActivityInstance
from .serializers import ProcessSerializer
from .services import (get_process_for_flow, get_current_activities_in_process,
                       get_user_processes, get_user_current_processes, get_activity_for_flow)


class CurrentAppMixin(object):
    def get_current_app(self):
        try:
            current_app = self.request.current_app
        except AttributeError:
            try:
                current_app = self.request.resolver_match.namespace
            except AttributeError:
                current_app = None
        return current_app

    def redirect(self, view_name, *args, **kwargs):
        url = reverse(view_name, args=args, kwargs=kwargs, current_app=self.get_current_app())
        return HttpResponseRedirect(url)


class ProcessListView(CurrentAppMixin, ListView):
    context_object_name = 'process_list'
    queryset = Process.objects.all()
    detail_view_name = 'processlib:process-detail'
    title = _("Processes")

    def get_title(self):
        return self.title

    def get_queryset(self):
        qs = super(ProcessListView, self).get_queryset()
        status = self.request.GET.get('status', Process.STATUS_STARTED)

        if status:
            qs = qs.filter(status=status)

        return qs

    def get_context_data(self, **kwargs):
        kwargs['flows'] = get_flows()
        kwargs['title'] = self.get_title()
        kwargs['detail_view_name'] = self.detail_view_name
        return super(ProcessListView, self).get_context_data(**kwargs)


class UserProcessListView(ProcessListView):
    title = _("My processes")

    def get_queryset(self):
        qs = get_user_processes(self.request.user)
        status = self.request.GET.get('status', '')

        if status:
            qs = qs.filter(status=status)

        return qs


class UserCurrentProcessListView(ProcessListView):
    title = _("My current processes")

    def get_queryset(self):
        qs = get_user_current_processes(self.request.user)
        status = self.request.GET.get('status', '')

        if status:
            qs = qs.filter(status=status)

        return qs


class ProcessDetailView(DetailView):
    context_object_name = 'process'
    queryset = Process.objects.all()
    list_view_name = 'processlib:process-list'

    def get_template_names(self):
        names = super(ProcessDetailView, self).get_template_names()
        names.append("processlib/process_detail.html")
        return names

    def get_object(self, queryset=None):
        process = super(ProcessDetailView, self).get_object(queryset)
        return process.flow.process_model.objects.get(pk=process.pk)

    def get_extra_detail_template_name(self):
        template_name = "processlib/extra_detail_{}.html".format(self.object.flow.label)
        try:
            get_template(template_name)
        except TemplateDoesNotExist:
            return None
        return template_name

    def get_context_data(self, **kwargs):
        kwargs['list_view_name'] = self.list_view_name
        kwargs['current_activities'] = get_current_activities_in_process(self.object)
        kwargs['extra_detail_template_name'] = self.get_extra_detail_template_name()
        kwargs['activity_instances'] = (
            self.object.flow.activity_model._default_manager.filter(process_id=self.object.pk)
                .exclude(status=ActivityInstance.STATUS_CANCELED)
        )
        return super(ProcessDetailView, self).get_context_data(**kwargs)


class ProcessCancelView(UpdateView):
    template_name = 'processlib/process_cancel.html'
    context_object_name = 'process'
    fields = []
    queryset = Process.objects.all()

    def get_success_url(self):
        return reverse('processlib:process-detail', kwargs={'pk': self.object.pk})

    def get_object(self, queryset=None):
        process = super(ProcessCancelView, self).get_object(queryset)
        return process.flow.process_model.objects.get(pk=process.pk)

    def form_valid(self, form):
        if not self.object.can_cancel(self.request.user):
            messages.error(self.request, "You can't cancel that process at this time.")

        from .services import cancel_process
        cancel_process(self.object)

        return HttpResponseRedirect(self.get_success_url())


class ProcessStartView(CurrentAppMixin, View):
    flow_label = None

    def get_activity(self):
        flow_label = self.kwargs['flow_label']
        flow = get_flow(flow_label)
        return flow.get_start_activity()

    def dispatch(self, request, *args, **kwargs):
        self.activity = self.get_activity()
        if self.activity.has_view():
            return self.activity.dispatch(self.activity, request, *args, **kwargs)
        else:
            return super(ProcessStartView, self).dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        self.activity.start()
        self.activity.finish()
        return self.redirect('processlib:process-detail', pk=self.activity.process.pk)


class ProcessActivityView(View):
    queryset = ActivityInstance.objects.all()
    activity_id = None
    flow_label = None

    def get_activity(self):
        return get_activity_for_flow(self.kwargs['flow_label'], self.kwargs['activity_id'])

    def dispatch(self, request, *args, **kwargs):
        self.activity = self.get_activity()
        return self.activity.dispatch(request, *args, **kwargs)


class ActivityUndoView(CurrentAppMixin, View):
    queryset = ActivityInstance.objects.all()

    activity_id = None
    flow_label = None

    def get_activity(self):
        return get_activity_for_flow(self.kwargs['flow_label'], self.kwargs['activity_id'])

    def post(self, request, *args, **kwargs):
        self.activity = self.get_activity()
        self.activity.undo()
        return self.redirect('processlib:process-detail', pk=self.activity.process.pk)


class ActivityRetryView(CurrentAppMixin, View):
    queryset = ActivityInstance.objects.all()

    activity_id = None
    flow_label = None

    def get_activity(self):
        return get_activity_for_flow(self.kwargs['flow_label'], self.kwargs['activity_id'])

    def post(self, request, *args, **kwargs):
        self.activity = self.get_activity()
        if hasattr(self.activity, 'retry'):
            messages.success(request, "Retrying {}".format(self.activity))
            self.activity.retry()
        return self.redirect('processlib:process-detail', pk=self.activity.process.pk)


class ActivityCancelView(CurrentAppMixin, View):
    queryset = ActivityInstance.objects.all()

    activity_id = None
    flow_label = None

    def get_activity(self):
        return get_activity_for_flow(self.kwargs['flow_label'], self.kwargs['activity_id'])

    def post(self, request, *args, **kwargs):
        self.activity = self.get_activity()
        self.activity.cancel()
        return self.redirect('processlib:process-detail', pk=self.activity.process.pk)


class ActivityMixin(CurrentAppMixin):
    activity = None

    def get_template_names(self):
        names = super(CurrentAppMixin, self).get_template_names()
        return names + ['processlib/view_activity.html']

    def get_context_data(self, **kwargs):
        kwargs['activity'] = self.activity
        return super(ActivityMixin, self).get_context_data(**kwargs)

    def get_object(self, queryset=None):
        return self.activity.process

    def form_valid(self, *args, **kwargs):
        response = super(ActivityMixin, self).form_valid(*args, **kwargs)
        self.activity.finish()
        return response

    def dispatch(self, request, *args, **kwargs):
        self.activity = kwargs['activity']
        self.activity.start()
        return super(ActivityMixin, self).dispatch(request, *args, **kwargs)

    def get_success_url(self):
        return reverse('processlib:process-detail', args=(self.activity.process.pk, ),
                       current_app=self.get_current_app())


class ProcessViewSet(viewsets.ModelViewSet):
    queryset = Process.objects.all()

    # a dict mapping flow labels to serializer classes to allow overriding those
    serializer_class_overrides = {}

    def get_process_model(self):
        if 'flow_label' in self.request.data:
            try:
                flow = get_flow(self.request.data['flow_label'])
            except KeyError:
                return Process
            return flow.process_model
        return Process

    def get_queryset(self):
        return self.get_process_model()._default_manager.all()

    def get_serializer_class(self):
        if self.request.data.get('flow_label') in self.serializer_class_overrides:
            return self.serializer_class_overrides[self.request.data['flow_label']]
        class DynamicSerializer(ProcessSerializer):
            class Meta(ProcessSerializer.Meta):
                model = self.get_process_model()
        return DynamicSerializer
