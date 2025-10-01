from django import forms
from .models import PopupNotification


class PopupNotificationForm(forms.ModelForm):
    class Meta:
        model = PopupNotification
        fields = [
            'title', 'message', 'notification_type', 'is_active',
            'show_delay', 'auto_close', 'auto_close_delay', 'position',
            'background_color', 'text_color', 'button_text', 'button_url',
            'target_pages'
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
            'notification_type': forms.Select(attrs={
                'class': 'form-select'
            }),
            'show_delay': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 0,
                'max': 60
            }),
            'auto_close_delay': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1,
                'max': 300
            }),
            'position': forms.Select(attrs={
                'class': 'form-select'
            }),
            'background_color': forms.TextInput(attrs={
                'class': 'form-control',
                'type': 'color'
            }),
            'text_color': forms.TextInput(attrs={
                'class': 'form-control',
                'type': 'color'
            }),
            'button_text': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., Learn More, Shop Now'
            }),
            'button_url': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'https://example.com'
            }),
            'target_pages': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'home, products, cart (leave empty for all pages)'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add custom choices for position
        self.fields['position'].choices = [
            ('top-left', 'Top Left'),
            ('top-right', 'Top Right'),
            ('bottom-left', 'Bottom Left'),
            ('bottom-right', 'Bottom Right'),
            ('top-center', 'Top Center'),
            ('bottom-center', 'Bottom Center'),
        ]
