"""Tests for the invariants the order portal is built on."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .forms import OrderForm
from .models import Order, OrderStatus

VALID_PAYLOAD = {
    'commodity_category': 'coal',
    'commodity_grade': 'coal.hard_coking',
    'tonnage': '75000',
    'purchase_price': '182.50',
    'sale_price': '196.00',
    'status': OrderStatus.PROCESSING,
    'counterparty': 'Nippon Steel',
    'phone': '',
    'email': 'desk@nsc.co.jp',
    'website': '',
}


class OrderPortalAccessTests(TestCase):
    """Nothing in the portal is reachable without a session."""

    def test_every_view_redirects_anonymous_users_to_login(self):
        order = Order.objects.create(
            commodity_category='coal', commodity_grade='coal.pci',
            tonnage=1, purchase_price=1, sale_price=2,
            status=OrderStatus.DRAFT, counterparty='X',
            created_by=get_user_model().objects.create_user('op', password='pw'),
        )
        for url in (
            reverse('orders:order_list'),
            reverse('orders:order_create'),
            reverse('orders:order_detail', args=[order.pk]),
            reverse('orders:order_update', args=[order.pk]),
        ):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertRedirects(
                    response, f'/accounts/login/?next={url}',
                    fetch_redirect_response=False,
                )


class PortalPrefixGuardTests(TestCase):
    """The whole /portal/ prefix fails closed, decorator or not."""

    def test_portal_root_redirects_anonymous_users_to_login(self):
        response = self.client.get('/portal/')
        self.assertRedirects(
            response, '/accounts/login/?next=/portal/',
            fetch_redirect_response=False,
        )

    def test_portal_root_reaches_the_register_once_signed_in(self):
        self.client.force_login(
            get_user_model().objects.create_user('op', password='pw12345!x')
        )
        self.assertRedirects(self.client.get('/portal/'), reverse('orders:order_list'))

    def test_an_undecorated_portal_url_is_still_gated(self):
        """
        The middleware, not the decorator, is what answers here — this path
        matches no view, so a 302 to login (rather than a 404) proves the
        prefix is guarded before routing.
        """
        response = self.client.get('/portal/anything-added-later/')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response['Location'], '/accounts/login/?next=/portal/anything-added-later/'
        )

    def test_the_query_string_survives_the_redirect(self):
        """Same ?next= encoding @login_required produces, so the two agree."""
        response = self.client.get('/portal/orders/', {'status': 'delayed'})
        self.assertEqual(
            response['Location'],
            '/accounts/login/?next=/portal/orders/%3Fstatus%3Ddelayed',
        )

    def test_public_pages_are_untouched(self):
        for path in ('/', '/about/'):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 200)


class OrderCreationTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('jdesk', password='pw12345!x')
        self.client.force_login(self.user)

    def test_authorship_is_stamped_not_submitted(self):
        """The form carries no created_by field; the view supplies it."""
        self.assertNotIn('created_by', OrderForm().fields)

        # Even a forged created_by in the POST body is ignored.
        other = get_user_model().objects.create_user('imposter', password='pw12345!x')
        self.client.post(
            reverse('orders:order_create'),
            dict(VALID_PAYLOAD, created_by=other.pk),
        )
        self.assertEqual(Order.objects.get().created_by, self.user)

    def test_references_are_allocated_in_sequence(self):
        for expected in ('0001', '0002', '0003'):
            self.client.post(reverse('orders:order_create'), VALID_PAYLOAD)
            self.assertTrue(Order.objects.first().reference.endswith(expected))

    def test_reference_survives_an_edit(self):
        self.client.post(reverse('orders:order_create'), VALID_PAYLOAD)
        order = Order.objects.get()
        self.client.post(
            reverse('orders:order_update', args=[order.pk]),
            dict(VALID_PAYLOAD, status=OrderStatus.DELAYED),
        )
        order.refresh_from_db()
        self.assertEqual(order.reference, Order.objects.get().reference)
        self.assertEqual(order.status, OrderStatus.DELAYED)
        self.assertEqual(order.created_by, self.user)


class CommodityTreeTests(TestCase):
    """A grade may only be filed under the branch it hangs off."""

    def test_grade_from_the_wrong_branch_is_rejected(self):
        form = OrderForm(dict(VALID_PAYLOAD, commodity_grade='iron.fines_62'))
        self.assertFalse(form.is_valid())
        self.assertIn('commodity_grade', form.errors)

    def test_save_re_derives_the_branch_from_the_grade(self):
        user = get_user_model().objects.create_user('op', password='pw12345!x')
        order = Order.objects.create(
            commodity_category='coal',           # deliberately wrong
            commodity_grade='iron.lump_65',
            tonnage=10, purchase_price=1, sale_price=2,
            status=OrderStatus.DRAFT, counterparty='Drift Co', created_by=user,
        )
        self.assertEqual(order.commodity_category, 'iron')


class OrderCommercialsTests(TestCase):
    def test_totals_and_margin_derive_from_the_per_tonne_prices(self):
        user = get_user_model().objects.create_user('op', password='pw12345!x')
        order = Order.objects.create(
            commodity_category='coal', commodity_grade='coal.hard_coking',
            tonnage=75000, purchase_price=182.50, sale_price=196.00,
            status=OrderStatus.PROCESSING, counterparty='Nippon Steel',
            created_by=user,
        )
        self.assertAlmostEqual(order.purchase_total, 13_687_500, places=2)
        self.assertAlmostEqual(order.sale_total, 14_700_000, places=2)
        self.assertAlmostEqual(order.margin_per_tonne, 13.50, places=2)
        self.assertAlmostEqual(order.margin_total, 1_012_500, places=2)
        self.assertAlmostEqual(order.margin_pct, 7.397, places=3)

    def test_margin_pct_is_none_when_nothing_was_paid(self):
        order = Order(purchase_price=0, sale_price=10, tonnage=5)
        self.assertIsNone(order.margin_pct)


class OrderRegisterTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('jdesk', password='pw12345!x')
        self.client.force_login(self.user)
        self.coal = Order.objects.create(
            commodity_category='coal', commodity_grade='coal.hard_coking',
            tonnage=75000, purchase_price=182.5, sale_price=196.0,
            status=OrderStatus.PROCESSING, counterparty='Nippon Steel',
            created_by=self.user,
        )
        self.iron = Order.objects.create(
            commodity_category='iron', commodity_grade='iron.pellets',
            tonnage=50000, purchase_price=110.0, sale_price=104.0,
            status=OrderStatus.DELIVERED, counterparty='Baosteel',
            created_by=self.user,
        )

    def test_filters_narrow_the_register(self):
        url = reverse('orders:order_list')
        cases = [
            ({'commodity_category': 'iron'}, [self.iron]),
            ({'commodity_grade': 'coal.hard_coking'}, [self.coal]),
            ({'status': OrderStatus.DELIVERED}, [self.iron]),
            ({'q': 'baosteel'}, [self.iron]),
            ({'q': 'nsc.co.jp'}, []),
        ]
        for params, expected in cases:
            with self.subTest(params=params):
                response = self.client.get(url, params)
                self.assertEqual(list(response.context['orders']), expected)

    def test_an_unknown_sort_key_falls_back_instead_of_reaching_the_orm(self):
        response = self.client.get(
            reverse('orders:order_list'), {'sort': 'created_by__password'}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context['orders']), [self.iron, self.coal])

    def test_open_tonnage_excludes_terminal_orders(self):
        response = self.client.get(reverse('orders:order_list'))
        self.assertEqual(response.context['totals']['total_tonnage'], 125000)
        self.assertEqual(response.context['open_tonnage'], 75000)

    def test_csv_export_respects_the_active_filters(self):
        response = self.client.get(
            reverse('orders:order_list'), {'export': 'csv', 'commodity_category': 'iron'}
        )
        self.assertEqual(response['Content-Type'], 'text/csv')
        body = response.content.decode().strip().splitlines()
        self.assertEqual(len(body), 2)          # header + one row
        self.assertIn('Baosteel', body[1])
