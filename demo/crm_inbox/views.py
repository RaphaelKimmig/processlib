from django.views.generic import UpdateView

from processlib.views import ActivityMixin


class MatchOrganisationView(ActivityMixin, UpdateView):
    template_name = 'crm_inbox/match_organisation.html'
    fields = ['organisation']


class MatchPersonView(ActivityMixin, UpdateView):
    template_name = 'crm_inbox/match_organisation.html'
    fields = ['person']




