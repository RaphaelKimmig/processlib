import six
from django.contrib import messages
from django.core.exceptions import ImproperlyConfigured, PermissionDenied
from django.db.models import Q
from django.http import HttpResponseRedirect
from django.template import TemplateDoesNotExist
from django.template.loader import get_template
from django.urls import reverse
from django.utils.translation import ugettext_lazy as _
from django.views import View
from django.views.generic import ListView, DetailView, UpdateView
from rest_framework import viewsets

from .flow import get_flows, get_flow
from .models import Process, ActivityInstance
from .serializers import ProcessSerializer
from .services import (
    get_activities_in_process,
    get_current_activities_in_process,
    get_user_processes,
    get_user_current_processes,
    get_activity_for_flow,
    user_has_activity_perm,
)
from .services import user_has_any_process_perm


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
        url = reverse(
            view_name, args=args, kwargs=kwargs, current_app=self.get_current_app()
        )
        return HttpResponseRedirect(url)


class ProcessListView(CurrentAppMixin, ListView):
    context_object_name = "process_list"
    queryset = Process.objects.all()
    detail_view_name = "processlib:process-detail"
    title = _("Processes")
    paginate_by = 10

    def get_title(self):
        return self.title

    def get_queryset(self):
        qs = super(ProcessListView, self).get_queryset()
        return self.filter_queryset(qs)

    def get_search_query(self):
        return self.request.GET.get("search", "").strip()

    def filter_queryset(self, qs):
        search = self.get_search_query()

        if search:
            qs = qs.filter(self.construct_search_filter(search))

        return qs

    def get_search_fields(self):
        by_model = {}
        for name, flow in get_flows():
            search_fields = flow.process_model.search_fields
            model_label = flow.process_model._meta.label
            if search_fields:
                by_model[model_label] = search_fields

        all_fields = []
        for name, fields in by_model.items():
            all_fields.extend(fields)

        return all_fields

    def construct_search_filter(self, query):
        q = Q()
        if not query:
            return q

        for field in self.get_search_fields():
            q |= Q(**{"{}__icontains".format(field): query})

        return q

    def get_context_data(self, **kwargs):
        kwargs["flows"] = get_flows()
        kwargs["search"] = self.get_search_query()
        kwargs["title"] = self.get_title()
        kwargs["detail_view_name"] = self.detail_view_name
        return super(ProcessListView, self).get_context_data(**kwargs)


class UserProcessListView(ProcessListView):
    title = _("My processes")

    def get_queryset(self):
        qs = get_user_processes(self.request.user)
        return self.filter_queryset(qs)


class UserCurrentProcessListView(ProcessListView):
    title = _("My current processes")

    def get_queryset(self):
        qs = get_user_current_processes(self.request.user)
        return self.filter_queryset(qs)


class ProcessDetailView(DetailView):
    context_object_name = "process"
    queryset = Process.objects.all()
    list_view_name = "processlib:process-list"

    def get_template_names(self):
        names = super(ProcessDetailView, self).get_template_names()
        names.append("processlib/process_detail.html")
        return names

    def get_object(self, queryset=None):
        process = super(ProcessDetailView, self).get_object(queryset)
        if not user_has_any_process_perm(self.request.user, process):
            raise PermissionDenied
        return process.flow.process_model.objects.get(pk=process.id)

    def get_extra_detail_template_name(self):
        template_name = "processlib/extra_detail_{}.html".format(self.object.flow.label)
        try:
            get_template(template_name)
        except TemplateDoesNotExist:
            return None
        return template_name

    def get_return_to_url(self):
        return_to = self.request.GET.get("return_to", "")
        if not return_to or not return_to.startswith("/"):
            return_to = reverse("processlib:process-list-user-current")
        return return_to

    def get_context_data(self, **kwargs):
        kwargs["list_view_name"] = self.list_view_name
        kwargs["return_to"] = self.get_return_to_url()
        kwargs["extra_detail_template_name"] = self.get_extra_detail_template_name()
        kwargs["activities"] = get_activities_in_process(self.object)
        return super(ProcessDetailView, self).get_context_data(**kwargs)


class ProcessCancelView(UpdateView):
    template_name = "processlib/process_cancel.html"
    context_object_name = "process"
    fields = []
    queryset = Process.objects.all()

    def get_success_url(self):
        return reverse("processlib:process-detail", kwargs={"pk": self.object.pk})

    def get_object(self, queryset=None):
        process = super(ProcessCancelView, self).get_object(queryset)
        if not user_has_any_process_perm(self.request.user, process):
            raise PermissionDenied
        return process.flow.process_model.objects.get(pk=process.id)

    def form_valid(self, form):
        if not self.object.can_cancel(self.request.user):
            messages.error(self.request, "You can't cancel that process at this time.")

        from .services import cancel_process

        user = self.request.user if self.request.user.is_authenticated else None
        cancel_process(self.object, user=user)

        return HttpResponseRedirect(self.get_success_url())


class ProcessStartView(CurrentAppMixin, View):
    flow_label = None

    def get_activity(self):
        flow_label = self.kwargs["flow_label"]
        flow = get_flow(flow_label)
        activity = flow.get_start_activity(request=self.request)
        if not user_has_activity_perm(self.request.user, activity):
            raise PermissionDenied
        return activity

    def dispatch(self, request, *args, **kwargs):
        self.activity = self.get_activity()
        if self.activity.has_view():
            return self.activity.dispatch(request, *args, **kwargs)
        else:
            return super(ProcessStartView, self).dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        user = request.user if request.user.is_authenticated else None
        self.activity.start()
        self.activity.finish(user=user)
        return self.redirect("processlib:process-detail", pk=self.activity.process.id)


class ActivityByLabelAndIdMixin(object):
    queryset = ActivityInstance.objects.all()
    activity_id = None
    flow_label = None

    def get_activity(self):
        activity = get_activity_for_flow(
            self.kwargs["flow_label"], self.kwargs["activity_id"]
        )
        if not user_has_activity_perm(self.request.user, activity):
            raise PermissionDenied
        return activity


class ProcessActivityView(ActivityByLabelAndIdMixin, View):
    def dispatch(self, request, *args, **kwargs):
        self.activity = self.get_activity()
        return self.activity.dispatch(request, *args, **kwargs)


class ActivityUndoView(CurrentAppMixin, ActivityByLabelAndIdMixin, View):
    def post(self, request, *args, **kwargs):
        self.activity = self.get_activity()
        user = self.request.user if self.request.user.is_authenticated else None
        self.activity.undo(user=user)
        return self.redirect("processlib:process-detail", pk=self.activity.process.id)


class ActivityRetryView(CurrentAppMixin, ActivityByLabelAndIdMixin, View):
    def post(self, request, *args, **kwargs):
        self.activity = self.get_activity()
        if hasattr(self.activity, "retry"):
            messages.success(request, "Retrying {}".format(self.activity))
            self.activity.retry()
        return self.redirect("processlib:process-detail", pk=self.activity.process.id)


class ActivityCancelView(CurrentAppMixin, ActivityByLabelAndIdMixin, View):
    def post(self, request, *args, **kwargs):
        self.activity = self.get_activity()
        user = self.request.user if self.request.user.is_authenticated else None
        self.activity.cancel(user=user)
        return self.redirect("processlib:process-detail", pk=self.activity.process.id)


class ActivityMixin(CurrentAppMixin):
    """
    Mixin used by view activities, e.g. those defined as an ActivityView.
    """

    activity = None

    def user_has_perm(self):
        return user_has_activity_perm(self.request.user, self.activity)

    def get_template_names(self):
        try:
            names = super(CurrentAppMixin, self).get_template_names()
        except ImproperlyConfigured:
            names = []
        return names + ["processlib/view_activity.html"]

    def get_context_data(self, **kwargs):
        kwargs["activity"] = self.activity
        return super(ActivityMixin, self).get_context_data(**kwargs)

    def get_object(self, queryset=None):
        return self.activity.process

    def get_queryset(self, queryset=None):
        return self.activity.flow.process_model._default_manager.all()

    def form_valid(self, *args, **kwargs):
        user = self.request.user if self.request.user.is_authenticated else None
        self.activity.finish(user=user)
        return super(ActivityMixin, self).form_valid(*args, **kwargs)

    def dispatch(self, request, *args, **kwargs):
        self.activity = kwargs["activity"]

        if not self.user_has_perm():
            raise PermissionDenied

        if self.activity.instance.status == self.activity.instance.STATUS_DONE:
            messages.info(
                request,
                _("The activity {} has already been done.").format(
                    six.text_type(self.activity)
                ),
            )
            return HttpResponseRedirect(
                reverse(
                    "processlib:process-detail",
                    args=(self.activity.process.id,),
                    current_app=self.get_current_app(),
                )
            )

        self.activity.start()
        return super(ActivityMixin, self).dispatch(request, *args, **kwargs)

    def get_success_url(self):
        if "_go_to_next" in self.request.POST:
            for activity in get_current_activities_in_process(self.activity.process):
                if activity.has_view() and user_has_activity_perm(
                    self.request.user, activity
                ):
                    return reverse(
                        "processlib:process-activity",
                        kwargs={
                            "flow_label": activity.flow.label,
                            "activity_id": activity.instance.pk,
                        },
                        current_app=self.get_current_app(),
                    )
        return reverse(
            "processlib:process-detail",
            args=(self.activity.process.id,),
            current_app=self.get_current_app(),
        )


class ProcessViewSet(viewsets.ModelViewSet):
    queryset = Process.objects.all()

    # a dict mapping flow labels to serializer classes to allow overriding those
    serializer_class_overrides = {}

    def get_process_model(self):
        if "flow_label" in self.request.data:
            try:
                flow = get_flow(self.request.data["flow_label"])
            except KeyError:
                return Process
            return flow.process_model
        return Process

    def get_queryset(self):
        return self.get_process_model()._default_manager.all()

    def get_serializer_class(self):
        if self.request.data.get("flow_label") in self.serializer_class_overrides:
            return self.serializer_class_overrides[self.request.data["flow_label"]]

        class DynamicSerializer(ProcessSerializer):
            class Meta(ProcessSerializer.Meta):
                model = self.get_process_model()

        return DynamicSerializer


class ProcessUpdateView(ActivityMixin, UpdateView):
    pass
