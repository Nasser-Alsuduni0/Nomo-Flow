from django import forms
from .models import PopupNotification


class PopupNotificationForm(forms.ModelForm):
    class Meta:
        model = PopupNotification
        fields = [
            'title', 'message', 'is_active',
            'button_text', 'button_url'
        ]
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter notification title'
            }),
            'message': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Enter notification message'
            }),
            'button_text': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., Learn More, Shop Now'
            }),
            'button_url': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'https://example.com'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
