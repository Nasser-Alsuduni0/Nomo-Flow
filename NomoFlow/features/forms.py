from django import forms
from core.models import EmailSubscriber


class EmailSubscriberForm(forms.ModelForm):
    class Meta:
        model = EmailSubscriber
        fields = ['email', 'name']
        widgets = {
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter your email address',
                'required': True
            }),
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter your name (optional)'
            }),
        }

