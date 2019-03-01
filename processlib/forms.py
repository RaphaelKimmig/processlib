from django import forms
from django.core.exceptions import ValidationError
from .models import Process


class ProcessCancelForm(forms.ModelForm):
    def __init__(self, user=None, **kwargs):
        self.user = user
        super(ProcessCancelForm, self).__init__(**kwargs)

    def clean(self):
        data = super(ProcessCancelForm, self).clean()

        if not self.instance.can_cancel(user=self.user):
            raise ValidationError("You can't cancel that process at this time.")

        return data

    class Meta:
        model = Process
        fields = []
