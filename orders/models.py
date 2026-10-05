"""Order fulfilment models for the OTEC internal portal."""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import IntegrityError, models, transaction
from django.urls import reverse
from django.utils import timezone


class CommodityCategory(models.TextChoices):
    """Branch of the commodity tree. OTEC trades coal and iron ore."""

    COAL = 'coal', 'Coal'
    IRON_ORE = 'iron', 'Iron Ore'


class CommodityGrade(models.TextChoices):
    """
    Leaf of the commodity tree: commodity -> category -> grade.

    Values are namespaced with their parent category (``<category>.<grade>``)
    so a leaf can never be orphaned from its branch — the parent is read
    straight off the value rather than kept in a second lookup table that
    could drift out of sync.
    """

    # Coal
    COAL_HARD_COKING = 'coal.hard_coking', 'Hard Coking Coal (HCC)'
    COAL_SEMI_SOFT = 'coal.semi_soft', 'Semi-Soft Coking Coal (SSCC)'
    COAL_PCI = 'coal.pci', 'Pulverised Coal Injection (PCI)'
    COAL_THERMAL_6000 = 'coal.thermal_6000', 'Thermal Coal — 6000 kcal/kg NAR'
    COAL_THERMAL_5500 = 'coal.thermal_5500', 'Thermal Coal — 5500 kcal/kg NAR'
    COAL_ANTHRACITE = 'coal.anthracite', 'Anthracite'

    # Iron ore
    IRON_FINES_62 = 'iron.fines_62', 'Iron Ore Fines — 62% Fe'
    IRON_FINES_58 = 'iron.fines_58', 'Iron Ore Fines — 58% Fe'
    IRON_LUMP_65 = 'iron.lump_65', 'Iron Ore Lump — 65% Fe'
    IRON_PELLETS = 'iron.pellets', 'Iron Ore Pellets'
    IRON_CONCENTRATE = 'iron.concentrate', 'Iron Ore Concentrate'

    @property
    def category(self):
        """The parent branch this grade hangs off."""
        return CommodityCategory(self.value.split('.', 1)[0])


def category_of(grade_value):
    """Parent category for a raw grade value, or ``None`` if unparseable."""
    try:
        return CommodityCategory(str(grade_value).split('.', 1)[0])
    except ValueError:
        return None


def grades_for(category_value):
    """Every grade hanging off one category."""
    prefix = f'{category_value}.'
    return [g for g in CommodityGrade if g.value.startswith(prefix)]


def grouped_grade_choices():
    """
    Grade choices grouped by parent category, which Django renders as
    ``<optgroup>`` blocks — the tree made visible in a single select.
    """
    return [
        (cat.label, [(g.value, g.label) for g in grades_for(cat.value)])
        for cat in CommodityCategory
    ]


class OrderStatus(models.TextChoices):
    """Lifecycle of a cargo, in the order it normally travels."""

    DRAFT = 'draft', 'Draft'
    PROCESSING = 'processing', 'Processing'
    CONFIRMED = 'confirmed', 'Contract Confirmed'
    AWAITING_VESSEL = 'awaiting_vessel', 'Awaiting Vessel'
    LOADING = 'loading', 'Loading'
    SHIPPED = 'shipped', 'Shipped'
    IN_TRANSIT = 'in_transit', 'In Transit'
    DELIVERED = 'delivered', 'Delivered'
    DELAYED = 'delayed', 'Delayed'
    ON_HOLD = 'on_hold', 'On Hold'
    CANCELLED = 'cancelled', 'Cancelled'


#: Statuses no longer moving — used to grey the row and skip them in the
#: "open tonnage" figures on the list view.
TERMINAL_STATUSES = frozenset({OrderStatus.DELIVERED, OrderStatus.CANCELLED})

#: Statuses that need an operator's attention rather than just time.
ATTENTION_STATUSES = frozenset({OrderStatus.DELAYED, OrderStatus.ON_HOLD})


class OrderQuerySet(models.QuerySet):
    def open(self):
        return self.exclude(status__in=TERMINAL_STATUSES)

    def needing_attention(self):
        return self.filter(status__in=ATTENTION_STATUSES)


class Order(models.Model):
    """
    A single physical cargo OTEC has bought and is selling on.

    Prices are held per tonne (the way the market quotes them); the totals
    and the margin are derived so the two can never disagree.
    """

    reference = models.CharField(
        max_length=20,
        unique=True,
        editable=False,
        help_text='Auto-generated trade reference, e.g. OTEC-2026-0001.',
    )

    # --- Commodity tree ---------------------------------------------------
    commodity_category = models.CharField(
        'commodity',
        max_length=16,
        choices=CommodityCategory.choices,
        db_index=True,
    )
    commodity_grade = models.CharField(
        'grade',
        max_length=32,
        choices=CommodityGrade.choices,
        db_index=True,
    )

    # --- Commercials ------------------------------------------------------
    tonnage = models.FloatField(
        validators=[MinValueValidator(0.0)],
        help_text='Metric tonnes.',
    )
    sale_price = models.FloatField(
        'sale price',
        validators=[MinValueValidator(0.0)],
        help_text='USD per tonne the cargo is being sold for.',
    )
    purchase_price = models.FloatField(
        'purchase price',
        validators=[MinValueValidator(0.0)],
        help_text='USD per tonne the cargo is being bought for.',
    )

    status = models.CharField(
        max_length=24,
        choices=OrderStatus.choices,
        default=OrderStatus.DRAFT,
        db_index=True,
    )

    # --- Counterparty -----------------------------------------------------
    counterparty = models.CharField(
        max_length=160,
        help_text='Buyer, mill or trading house this cargo is placed with.',
    )
    phone = models.CharField(max_length=32, blank=True)
    email = models.EmailField(blank=True)
    website = models.URLField(blank=True)

    # --- Provenance -------------------------------------------------------
    # Deliberately not on the form: the portal stamps the signed-in operator
    # so authorship cannot be typed in, or typed in wrongly.
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='orders',
        editable=False,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = OrderQuerySet.as_manager()

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['status', '-created_at']),
        ]

    def __str__(self):
        return f'{self.reference} — {self.get_commodity_grade_display()}'

    def get_absolute_url(self):
        return reverse('orders:order_detail', args=[self.pk])

    # --- Validation -------------------------------------------------------
    def clean(self):
        parent = category_of(self.commodity_grade)
        if self.commodity_category and parent and parent != self.commodity_category:
            raise ValidationError({
                'commodity_grade': (
                    f'{self.get_commodity_grade_display()} is not a '
                    f'{CommodityCategory(self.commodity_category).label} grade.'
                )
            })

    def save(self, *args, **kwargs):
        # The grade is the authority: keep the stored branch derived from the
        # leaf so a stale category can never survive an edit.
        parent = category_of(self.commodity_grade)
        if parent:
            self.commodity_category = parent

        if self.reference:
            return super().save(*args, **kwargs)

        # `reference` is unique, so a race loses on the insert rather than
        # silently issuing a duplicate. Retry with a freshly read sequence.
        for _attempt in range(5):
            try:
                with transaction.atomic():
                    self.reference = self._next_reference()
                    return super().save(*args, **kwargs)
            except IntegrityError:
                self.reference = ''
        raise IntegrityError('Could not allocate a unique order reference.')

    @staticmethod
    def _next_reference():
        prefix = f'OTEC-{timezone.localdate().year}-'
        last = (
            Order.objects.filter(reference__startswith=prefix)
            .order_by('-reference')
            .values_list('reference', flat=True)
            .first()
        )
        seq = int(last.rsplit('-', 1)[1]) + 1 if last else 1
        return f'{prefix}{seq:04d}'

    # --- Derived commercials ---------------------------------------------
    @property
    def sale_total(self):
        return (self.tonnage or 0) * (self.sale_price or 0)

    @property
    def purchase_total(self):
        return (self.tonnage or 0) * (self.purchase_price or 0)

    @property
    def margin_per_tonne(self):
        return (self.sale_price or 0) - (self.purchase_price or 0)

    @property
    def margin_total(self):
        return self.sale_total - self.purchase_total

    @property
    def margin_pct(self):
        """Margin over cost, or ``None`` when the cargo was bought at zero."""
        if not self.purchase_price:
            return None
        return self.margin_per_tonne / self.purchase_price * 100

    # --- Presentation helpers --------------------------------------------
    @property
    def is_terminal(self):
        return self.status in TERMINAL_STATUSES

    @property
    def needs_attention(self):
        return self.status in ATTENTION_STATUSES

    @property
    def status_tone(self):
        """CSS modifier for the status pill — see the portal stylesheet."""
        if self.status in ATTENTION_STATUSES:
            return 'alert'
        if self.status == OrderStatus.DELIVERED:
            return 'done'
        if self.status == OrderStatus.CANCELLED:
            return 'dead'
        if self.status == OrderStatus.DRAFT:
            return 'draft'
        return 'live'
