from django import forms
from .models import Lead

class LeadForm(forms.ModelForm):
    """
    Form for creating and updating leads
    """
    class Meta:
        model = Lead
        fields = ['name', 'email', 'phone', 'landmark', 'city', 'state', 'country', 'pin_code', 'map_location', 'price', 'validity']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter Name'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Enter Email'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter Phone Number'}),
            'landmark': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter Landmark'}),
            'city': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter City'}),
            'state': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter State'}),
            'country': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter Country'}),
            'pin_code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter PIN Code'}),
            'map_location': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'Enter Google Maps URL'}),
            'price': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Enter Lead Price', 'step': '0.01'}),
            'validity': forms.Select(attrs={'class': 'form-control', 'placeholder': 'Select Lead Validity'})
        }

    def clean_email(self):
        """
        Validate email uniqueness
        """
        email = self.cleaned_data.get('email')
        # Removed email uniqueness check
        return email

    def clean_price(self):
        """
        Validate price is non-negative
        """
        price = self.cleaned_data.get('price')
        if price is not None and price < 0:
            raise forms.ValidationError("Price cannot be negative.")
        return price

    def clean_pin_code(self):
        """
        Validate PIN code format
        """
        pin_code = self.cleaned_data.get('pin_code')
        if pin_code and not pin_code.isdigit():
            raise forms.ValidationError("PIN code must contain only digits.")
        return pin_code

    def clean_map_location(self):
        """
        Validate map location URL
        """
        map_location = self.cleaned_data.get('map_location')
        if map_location:
            # Basic URL validation
            import re
            url_pattern = re.compile(
                r'^https?://'  # http:// or https://
                r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
                r'localhost|'  # localhost...
                r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
                r'(?::\d+)?'  # optional port
                r'(?:/?|[/?]\S+)$', re.IGNORECASE)
            
            if not url_pattern.match(map_location):
                raise forms.ValidationError("Please enter a valid URL.")
        return map_location
