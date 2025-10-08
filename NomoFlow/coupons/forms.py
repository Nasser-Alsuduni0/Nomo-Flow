from django import forms
from .models import Coupon
import re


class CouponForm(forms.ModelForm):
    class Meta:
        model = Coupon
        fields = [
            'code', 'discount_kind', 'amount', 'max_discount_amount',
            'start_date', 'expires_at', 'free_shipping', 'exclude_discounted',
            'min_cart', 'max_uses', 'per_customer_limit'
        ]
        widgets = {
            'code': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Coupon code (letters, numbers, no spaces)',
                'dir': 'ltr'
            }),
            'discount_kind': forms.Select(attrs={
                'class': 'form-select',
            }),
            'amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Discount amount',
                'step': '0.01',
                'min': '0'
            }),
            'max_discount_amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Maximum discount amount',
                'step': '0.01',
                'min': '0'
            }),
            'start_date': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local',
                'placeholder': 'Start date'
            }),
            'expires_at': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local',
                'placeholder': 'Expiry date'
            }),
            'free_shipping': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
            }),
            'exclude_discounted': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
            }),
            'min_cart': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Minimum cart value',
                'step': '0.01',
                'min': '0'
            }),
            'max_uses': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Maximum total uses',
                'min': '1'
            }),
            'per_customer_limit': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Maximum uses per customer',
                'min': '1'
            }),
        }
        labels = {
            'code': 'Coupon Code (letters, numbers, no spaces)',
            'discount_kind': 'Discount Type',
            'amount': 'Discount Amount / Percentage',
            'max_discount_amount': 'Maximum Discount Amount',
            'start_date': 'Start Date',
            'expires_at': 'Expiry Date',
            'free_shipping': 'Free Shipping?',
            'exclude_discounted': 'Exclude Discounted Products',
            'min_cart': 'Minimum Cart Value',
            'max_uses': 'Maximum Total Uses',
            'per_customer_limit': 'Maximum Uses Per Customer',
        }

    def clean_code(self):
        code = self.cleaned_data.get('code')
        
        # Check for spaces
        if ' ' in code:
            raise forms.ValidationError('Coupon code must not contain spaces')
        
        # Allow English letters, Arabic letters, and numbers only
        # Arabic Unicode range: \u0600-\u06FF
        # English letters and numbers: a-zA-Z0-9
        if not re.match(r'^[a-zA-Z0-9\u0600-\u06FF]+$', code):
            raise forms.ValidationError('Coupon code must contain only letters and numbers')
        
        return code

    def clean(self):
        cleaned_data = super().clean()
        discount_kind = cleaned_data.get('discount_kind')
        amount = cleaned_data.get('amount')
        
        # If percentage, validate that amount is between 0-100
        if discount_kind == Coupon.PERCENT and amount:
            if amount < 0 or amount > 100:
                raise forms.ValidationError('Discount percentage must be between 0 and 100')
        
        start_date = cleaned_data.get('start_date')
        expires_at = cleaned_data.get('expires_at')
        
        # Validate that end date is after start date
        if start_date and expires_at and expires_at <= start_date:
            raise forms.ValidationError('Expiry date must be after start date')
        
        return cleaned_data

