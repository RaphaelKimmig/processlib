from django.urls import reverse
from django.views.generic import UpdateView


class ActivityMixin(object):
    activity = None

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
        return reverse('process-detail', args=(self.activity.process.pk, ))


class MatchOrganisationView(ActivityMixin, UpdateView):
    template_name = 'crm_inbox/match_organisation.html'
    fields = ['organisation']


class MatchPersonView(ActivityMixin, UpdateView):
    template_name = 'crm_inbox/match_organisation.html'
    fields = ['person']




