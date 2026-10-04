"""Forms for the internal order fulfilment portal."""

from django import forms

from .models import (
    CommodityCategory,
    CommodityGrade,
    Order,
    OrderStatus,
    category_of,
    grouped_grade_choices,
)


class GradeSelect(forms.Select):
    """
    Grade picker that tags every option with its parent category.

    The tag is what lets the browser narrow the grade list to the chosen
    commodity without a round trip; the server still validates the pair, so
    the filtering is a convenience and never the enforcement.
    """

    def create_option(self, name, value, *args, **kwargs):
        option = super().create_option(name, value, *args, **kwargs)
        parent = category_of(value)
        if parent:
            option['attrs']['data-category'] = parent.value
        return option


class OrderForm(forms.ModelForm):
    """
    Create/edit form for a cargo.

    ``created_by`` and ``reference`` are absent by design — the view stamps
    the signed-in operator and the model allocates the reference.
    """

    class Meta:
        model = Order
        fields = [
            'commodity_category',
            'commodity_grade',
            'tonnage',
            'purchase_price',
            'sale_price',
            'status',
            'counterparty',
            'phone',
            'email',
            'website',
        ]
        widgets = {
            'commodity_category': forms.Select(attrs={
                'class': 'form-input',
                'id': 'id_commodity_category',
            }),
            'tonnage': forms.NumberInput(attrs={
                'class': 'form-input',
                'step': '0.01',
                'min': '0',
                'placeholder': '75000',
            }),
            'purchase_price': forms.NumberInput(attrs={
                'class': 'form-input',
                'step': '0.01',
                'min': '0',
                'placeholder': '182.50',
            }),
            'sale_price': forms.NumberInput(attrs={
                'class': 'form-input',
                'step': '0.01',
                'min': '0',
                'placeholder': '196.00',
            }),
            'status': forms.Select(attrs={'class': 'form-input'}),
            'counterparty': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Buyer / mill / trading house',
            }),
            'phone': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': '+61 400 000 000',
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-input',
                'placeholder': 'desk@counterparty.com',
            }),
            'website': forms.URLInput(attrs={
                'class': 'form-input',
                'placeholder': 'https://counterparty.com',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Grouped choices render as <optgroup> blocks, so the select itself
        # shows the tree: Coal -> its grades, Iron Ore -> its grades.
        self.fields['commodity_grade'].widget = GradeSelect(attrs={
            'class': 'form-input',
            'id': 'id_commodity_grade',
        })
        self.fields['commodity_grade'].choices = (
            [('', 'Select a grade')] + grouped_grade_choices()
        )
        self.fields['commodity_category'].choices = (
            [('', 'Select a commodity')] + list(CommodityCategory.choices)
        )
        self.fields['status'].choices = list(OrderStatus.choices)

        self.fields['tonnage'].label = 'Tonnage (t)'
        self.fields['purchase_price'].label = 'Purchase price (USD/t)'
        self.fields['sale_price'].label = 'Sale price (USD/t)'

    def clean(self):
        cleaned = super().clean()
        category = cleaned.get('commodity_category')
        grade = cleaned.get('commodity_grade')

        if category and grade:
            parent = category_of(grade)
            if parent and parent.value != category:
                self.add_error(
                    'commodity_grade',
                    f'{CommodityGrade(grade).label} is a '
                    f'{parent.label} grade, not '
                    f'{CommodityCategory(category).label}.',
                )
        return cleaned


class OrderFilterForm(forms.Form):
    """Search / filter / sort controls above the order register."""

    SORT_CHOICES = [
        ('-created_at', 'Newest first'),
        ('created_at', 'Oldest first'),
        ('-tonnage', 'Tonnage — high to low'),
        ('tonnage', 'Tonnage — low to high'),
        ('reference', 'Reference A–Z'),
        ('status', 'Status'),
        ('counterparty', 'Counterparty A–Z'),
    ]

    #: Whitelist for the ORDER BY clause — never trust the raw query string.
    SORT_FIELDS = {value for value, _label in SORT_CHOICES}

    q = forms.CharField(
        required=False,
        label='Search',
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Reference, counterparty, email…',
        }),
    )
    commodity_category = forms.ChoiceField(
        required=False,
        label='Commodity',
        choices=[('', 'All commodities')] + list(CommodityCategory.choices),
        widget=forms.Select(attrs={'class': 'form-input'}),
    )
    commodity_grade = forms.ChoiceField(
        required=False,
        label='Grade',
        choices=[],
        widget=forms.Select(attrs={'class': 'form-input'}),
    )
    status = forms.ChoiceField(
        required=False,
        label='Status',
        choices=[('', 'All statuses')] + list(OrderStatus.choices),
        widget=forms.Select(attrs={'class': 'form-input'}),
    )
    sort = forms.ChoiceField(
        required=False,
        label='Sort',
        choices=SORT_CHOICES,
        widget=forms.Select(attrs={'class': 'form-input'}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['commodity_grade'].widget = GradeSelect(attrs={'class': 'form-input'})
        self.fields['commodity_grade'].choices = (
            [('', 'All grades')] + grouped_grade_choices()
        )

    def clean_sort(self):
        sort = self.cleaned_data.get('sort')
        return sort if sort in self.SORT_FIELDS else '-created_at'
