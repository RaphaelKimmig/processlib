from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.views import View
from django.views.generic import ListView, DetailView
from rest_framework import viewsets

from .flow import (Flow, get_flows, get_flow)
from .models import Process, ActivityInstance
from .services import (get_process_for_flow, get_current_activities_in_process,
                       get_activity_for_flow)
from .serializers import ProcessSerializer


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


class LinearFormFlowView(CurrentAppMixin, View):
    process_id = None
    flow = None
    template_name = 'processlib/step.html'
    view_name = None
    process = None

    def get_start_activity(self, process_kwargs):
        return self.flow.get_start_activity(process_kwargs=process_kwargs)

    def get_next_activity(self, **kwargs):
        if self.kwargs.get('process_id'):
            # FIXME breaks for multiple
            process = get_process_for_flow(self.flow.label, self.kwargs['process_id'])
            candidates = get_current_activities_in_process(process)
            activity = next(candidates)
        else:
            activity = self.get_start_activity(process_kwargs=kwargs)
        return activity

    def get(self, request, **kwargs):
        activity = self.get_next_activity()
        activity.start()

        form = activity.get_form(instance=activity.process)

        return render(request, self.template_name, {'process': activity.process, 'form': form})

    def post(self, request, **kwargs):
        activity = self.get_next_activity()
        activity.start()

        form = activity.get_form(data=request.POST, instance=activity.process)

        if not form.is_valid():
            return render(request, self.template_name, {'process': activity.process, 'form': form})

        form.save()
        activity.finish()

        return self.redirect(self.get_next_url(activity))  # FIXME success page and so on?

    def get_next_url(self, control):
        return reverse(self.view_name, kwargs={
            'process_id': control.process.id,
        }, current_app=self.get_current_app())


class ProcessListView(CurrentAppMixin, ListView):
    context_object_name = 'process_list'
    queryset = Process.objects.all()
    detail_view_name = 'processlib:process-detail'

    def get_context_data(self, **kwargs):
        kwargs['flows'] = get_flows()
        kwargs['detail_view_name'] = self.detail_view_name
        return super(ProcessListView, self).get_context_data(**kwargs)


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

    def get_context_data(self, **kwargs):
        kwargs['list_view_name'] = self.list_view_name
        kwargs['current_activities'] = get_current_activities_in_process(self.object)
        kwargs['activity_instances'] = (
            self.object.flow.activity_model._default_manager.filter(process_id=self.object.pk)
                .exclude(status=ActivityInstance.STATUS_CANCELED)
        )
        return super(ProcessDetailView, self).get_context_data(**kwargs)


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
