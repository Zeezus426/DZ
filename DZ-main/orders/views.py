"""Internal order fulfilment portal — every view is behind authentication."""

import csv

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.core.paginator import Paginator
from django.db.models import Count, F, Q, Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from home.forms import ContactForm

from .forms import OrderFilterForm, OrderForm
from .models import Order

#: Rows per page on the register.
PAGE_SIZE = 20


def _portal_context(**extra):
    """
    Shared context for portal pages.

    ``home/base.html`` carries the site-wide enquiry modal, so every page
    that extends it needs the contact form in context or the modal renders
    with empty inputs.
    """
    context = {'contact_form': ContactForm()}
    context.update(extra)
    return context


class PortalLoginView(LoginView):
    """
    Sign-in for the portal.

    The template extends the public site chrome, which carries the enquiry
    modal — so the contact form has to be in context here too or the modal
    renders with no inputs.
    """

    redirect_authenticated_user = True

    def get_context_data(self, **kwargs):
        return super().get_context_data(contact_form=ContactForm(), **kwargs)


def _filtered_orders(request):
    """Apply search / filter / sort from the query string. Returns (qs, form)."""
    form = OrderFilterForm(request.GET or None)
    queryset = Order.objects.select_related('created_by')

    if not form.is_valid():
        return queryset, form

    data = form.cleaned_data

    if data.get('q'):
        term = data['q'].strip()
        queryset = queryset.filter(
            Q(reference__icontains=term)
            | Q(counterparty__icontains=term)
            | Q(email__icontains=term)
            | Q(phone__icontains=term)
            | Q(website__icontains=term)
        )

    if data.get('commodity_category'):
        queryset = queryset.filter(commodity_category=data['commodity_category'])

    if data.get('commodity_grade'):
        queryset = queryset.filter(commodity_grade=data['commodity_grade'])

    if data.get('status'):
        queryset = queryset.filter(status=data['status'])

    return queryset.order_by(data.get('sort') or '-created_at'), form


@login_required
def order_list(request):
    """The order register: search, filter, sort, paginate, export."""
    queryset, filter_form = _filtered_orders(request)

    if request.GET.get('export') == 'csv':
        return _export_csv(queryset)

    # Totals describe the filtered set, not the page, so they stay honest
    # when the operator narrows the register.
    # Aliases are prefixed because an alias that shadows a field name makes
    # the later expressions resolve against the aggregate instead of the column.
    totals = queryset.aggregate(
        total_count=Count('id'),
        total_tonnage=Sum('tonnage'),
        total_sale_value=Sum(F('tonnage') * F('sale_price')),
        total_margin=Sum(F('tonnage') * (F('sale_price') - F('purchase_price'))),
    )
    open_tonnage = queryset.open().aggregate(t=Sum('tonnage'))['t'] or 0

    paginator = Paginator(queryset, PAGE_SIZE)
    page = paginator.get_page(request.GET.get('page'))

    # Preserve the active filters when paginating.
    params = request.GET.copy()
    params.pop('page', None)
    querystring = params.urlencode()

    return render(request, 'orders/order_list.html', _portal_context(
        page_obj=page,
        orders=page.object_list,
        filter_form=filter_form,
        totals=totals,
        open_tonnage=open_tonnage,
        attention_count=queryset.needing_attention().count(),
        querystring=querystring,
        has_filters=any(
            request.GET.get(key)
            for key in ('q', 'commodity_category', 'commodity_grade', 'status')
        ),
    ))


@login_required
def order_create(request):
    form = OrderForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        order = form.save(commit=False)
        # Authorship is stamped, never submitted — the form has no field for it.
        order.created_by = request.user
        order.save()
        messages.success(request, f'Order {order.reference} created.')
        return redirect(order.get_absolute_url())

    return render(request, 'orders/order_form.html', _portal_context(
        form=form,
        order=None,
        heading='New Order',
        submit_label='Create Order',
    ))


@login_required
def order_update(request, pk):
    order = get_object_or_404(Order.objects.select_related('created_by'), pk=pk)
    form = OrderForm(request.POST or None, instance=order)

    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, f'Order {order.reference} updated.')
        return redirect(order.get_absolute_url())

    return render(request, 'orders/order_form.html', _portal_context(
        form=form,
        order=order,
        heading=f'Edit {order.reference}',
        submit_label='Save Changes',
    ))


@login_required
def order_detail(request, pk):
    order = get_object_or_404(Order.objects.select_related('created_by'), pk=pk)
    return render(request, 'orders/order_detail.html', _portal_context(order=order))


def _export_csv(queryset):
    """Stream the filtered register out as CSV."""
    stamp = timezone.localtime().strftime('%Y%m%d-%H%M')
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = (
        f'attachment; filename="otec-orders-{stamp}.csv"'
    )

    writer = csv.writer(response)
    writer.writerow([
        'Reference', 'Commodity', 'Grade', 'Tonnage (t)',
        'Purchase (USD/t)', 'Sale (USD/t)', 'Purchase total (USD)',
        'Sale total (USD)', 'Margin (USD)', 'Status', 'Counterparty',
        'Phone', 'Email', 'Website', 'Created by', 'Created at',
    ])

    for order in queryset.iterator():
        writer.writerow([
            order.reference,
            order.get_commodity_category_display(),
            order.get_commodity_grade_display(),
            order.tonnage,
            order.purchase_price,
            order.sale_price,
            round(order.purchase_total, 2),
            round(order.sale_total, 2),
            round(order.margin_total, 2),
            order.get_status_display(),
            order.counterparty,
            order.phone,
            order.email,
            order.website,
            order.created_by.get_username(),
            timezone.localtime(order.created_at).strftime('%Y-%m-%d %H:%M'),
        ])

    return response
