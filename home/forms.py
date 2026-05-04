from django import forms


class ContactForm(forms.Form):
    """
    Contact form for visitors to submit inquiries.
    Validates name, email, phone, subject, and message fields.
    """
    name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Your Name',
            'required': 'required'
        }),
        required=True
    )

    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'form-input',
            'placeholder': 'your@email.com',
            'required': 'required'
        }),
        required=True
    )

    phone = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': '+61 400 000 000'
        })
    )

    company = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Company Name (Optional)'
        })
    )

    subject = forms.ChoiceField(
        choices=[
            ('general', 'General Inquiry'),
            ('sales', 'Sales - Hard Coking Coal'),
            ('sales_iron', 'Sales - Iron Ore'),
            ('sales_thermal', 'Sales - Thermal Coal'),
            ('sales_wheat', 'Sales - Wheat'),
            ('partnership', 'Partnership Opportunity'),
            ('other', 'Other'),
        ],
        widget=forms.Select(attrs={
            'class': 'form-input',
            'required': 'required'
        }),
        required=True
    )

    message = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-input textarea',
            'placeholder': 'Tell us about your inquiry...',
            'rows': 5,
            'required': 'required'
        }),
        required=True,
        max_length=2000
    )
