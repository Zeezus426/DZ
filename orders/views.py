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
from .models import Order, OrderStatus

#: Rows per page on the register.
PAGE_SIZE = 20

MAP_COORDINATES = {
    'Australia': {'city': 'Sydney', 'x': 850, 'y': 420},
    'Japan': {'city': 'Tokyo', 'x': 820, 'y': 240},
    'China': {'city': 'Qingdao', 'x': 760, 'y': 290},
    'South Korea': {'city': 'Busan', 'x': 790, 'y': 265},
    'India': {'city': 'Mumbai', 'x': 700, 'y': 335},
    'Vietnam': {'city': 'Hai Phong', 'x': 780, 'y': 345},
    'Middle East': {'city': 'Jebel Ali', 'x': 640, 'y': 315},
    'Europe': {'city': 'Rotterdam', 'x': 560, 'y': 200},
    'North America': {'city': 'Houston', 'x': 330, 'y': 260},
    'South America': {'city': 'Santos', 'x': 360, 'y': 420},
    'Africa': {'city': 'Durban', 'x': 600, 'y': 395},
}

STATUS_STYLE_MAP = {
    OrderStatus.DRAFT: 'pending',
    OrderStatus.PROCESSING: 'pending',
    OrderStatus.CONFIRMED: 'confirmed',
    OrderStatus.AWAITING_VESSEL: 'confirmed',
    OrderStatus.LOADING: 'in_transit',
    OrderStatus.SHIPPED: 'in_transit',
    OrderStatus.IN_TRANSIT: 'in_transit',
    OrderStatus.DELIVERED: 'completed',
    OrderStatus.DELAYED: 'delayed',
    OrderStatus.ON_HOLD: 'delayed',
    OrderStatus.CANCELLED: 'completed',
}

LEGEND_LABELS = {
    'pending': 'Pending',
    'confirmed': 'Confirmed',
    'in_transit': 'In transit',
    'completed': 'Completed',
    'delayed': 'Delayed',
}


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


def _counterparty_country(counterparty):
    """Best-effort geography derived from the live counterparty name."""
    text = (counterparty or '').lower()
    for country in ('Japan', 'China', 'South Korea', 'India', 'Vietnam', 'Middle East', 'Europe', 'North America', 'South America', 'Africa'):
        if country.lower() in text:
            return country

    if any(token in text for token in ('nippon', 'mitsubishi', 'sumitomo', 'toshiba', 'jfe', 'japan')):
        return 'Japan'
    if any(token in text for token in ('baosteel', 'china', 'minmetals', 'hebei', 'shagang', 'tata', 'shougang')):
        return 'China'
    if any(token in text for token in ('posco', 'korea', 'hyundai')):
        return 'South Korea'
    if any(token in text for token in ('jsw', 'steel authority', 'india', 'tata')):
        return 'India'
    if any(token in text for token in ('vietnam', 'vinacoke', 'seaport')):
        return 'Vietnam'
    if any(token in text for token in ('uae', 'saudi', 'dubai', 'oman', 'qatar')):
        return 'Middle East'
    if any(token in text for token in ('europe', 'germany', 'france', 'italy', 'netherlands', 'rotterdam')):
        return 'Europe'
    if any(token in text for token in ('usa', 'america', 'houston', 'mill', 'steel')):
        return 'North America'
    if any(token in text for token in ('brazil', 'argentina', 'chile', 'santos')):
        return 'South America'
    if any(token in text for token in ('south africa', 'africa', 'durban')):
        return 'Africa'

    return 'China' if 'iron' in (counterparty or '').lower() else 'Japan'


def _status_class(value):
    return STATUS_STYLE_MAP.get(value, 'pending')


def _trade_map_data(queryset):
    """Return a lightweight map payload from actual order records."""
    routes = []
    seen_statuses = set()
    seller = {'country': 'Australia', 'city': 'Sydney', 'x': 180, 'y': 395, 'kind': 'seller'}

    for order in queryset[:12]:
        country = _counterparty_country(order.counterparty)
        coords = MAP_COORDINATES.get(country, {'city': 'Shanghai', 'x': 760, 'y': 300})
        status = _status_class(order.status)
        seen_statuses.add(status)
        routes.append({
            'id': order.pk,
            'reference': order.reference,
            'counterparty': order.counterparty,
            'country': country,
            'city': coords['city'],
            'commodity': order.get_commodity_grade_display(),
            'status': status,
            'status_label': order.get_status_display(),
            'tonnage': order.tonnage,
            'margin': order.margin_total,
            'value': order.sale_total,
            'seller_x': seller['x'],
            'seller_y': seller['y'],
            'buyer_x': coords['x'],
            'buyer_y': coords['y'],
            'mid_x': (seller['x'] + coords['x']) / 2,
            'mid_y': min(seller['y'], coords['y']) - 40,
            'origin': 'Sydney, Australia',
            'destination': f"{coords['city']}, {country}",
        })

    active_routes = queryset.exclude(status__in={OrderStatus.DELIVERED, OrderStatus.CANCELLED}).count()
    total_value = queryset.aggregate(v=Sum(F('tonnage') * F('sale_price')))['v'] or 0
    total_margin = queryset.aggregate(m=Sum(F('tonnage') * (F('sale_price') - F('purchase_price'))))['m'] or 0

    return {
        'seller': seller,
        'routes': routes,
        'legend': [
            {'key': key, 'label': LEGEND_LABELS[key]}
            for key in ('pending', 'confirmed', 'in_transit', 'completed', 'delayed')
            if key in seen_statuses or key == 'pending'
        ],
        'total_routes': len(routes),
        'active_routes': active_routes,
        'total_value': total_value,
        'total_margin': total_margin,
    }


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

    map_data = _trade_map_data(queryset)

    return render(request, 'orders/order_list.html', _portal_context(
        page_obj=page,
        orders=page.object_list,
        filter_form=filter_form,
        totals=totals,
        open_tonnage=open_tonnage,
        attention_count=queryset.needing_attention().count(),
        querystring=querystring,
        map_data=map_data,
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
