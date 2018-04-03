from django import forms

from order.models import OrderProcess


class TokenForm(forms.ModelForm):
    token = forms.CharField(required=False, help_text='You can find your token on the print thing.')

    def __init__(self, **kwargs):
        instance = kwargs['instance']
        super(TokenForm, self).__init__(**kwargs)
        self.fields['token'].required = instance.config.require_token

    def clean(self):
        token = self.cleaned_data.get('token')
        if not token:
            return {}

        return

    class Meta:
        model = OrderProcess
        fields = ['token']


class ArticlesForm(forms.ModelForm):
    articles = forms.CharField()

    class Meta:
        model = OrderProcess
        fields = []


class RecipientForm(forms.ModelForm):
    name = forms.CharField()

    class Meta:
        model = OrderProcess
        fields = []


class ConfirmationForm(forms.ModelForm):
    accept_terms = forms.BooleanField(label='I accept the terms and conditions.')

    class Meta:
        model = OrderProcess
        fields = []
