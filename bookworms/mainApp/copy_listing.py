"""BookCopy multi-flag listing (checkboxes + sale/gift radio exclusivity)."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError

from .models import BookCopy

LISTING_FLAG_FIELDS = (
    "is_fee_sharing",
    "is_hidden",
    "is_for_sale",
    "is_for_rent",
    "is_as_gift",
    "is_for_exchange",
    "is_free_of_deposit",
)

LISTING_CHECKBOX_FLAGS = (
    ("is_fee_sharing", "Fee sharing"),
    ("is_hidden", "Hidden"),
    ("is_for_rent", "For rent"),
    ("is_for_exchange", "For exchange"),
    ("is_free_of_deposit", "Free of deposit"),
)

SALE_GIFT_RADIO = (
    ("", "Neither"),
    ("for_sale", "For sale"),
    ("as_gift", "As a gift"),
)


def parse_money(raw) -> Decimal | None:
    if raw is None:
        return None
    s = str(raw).strip().replace(",", ".")
    if not s:
        return None
    try:
        return Decimal(s)
    except (InvalidOperation, TypeError, ValueError):
        raise ValidationError("Некоректна сума.")


def _truthy(raw) -> bool:
    if raw is True:
        return True
    if raw is False or raw is None:
        return False
    return str(raw).strip().lower() in ("1", "true", "on", "yes", "y")


def apply_copy_listing(
    copy: BookCopy,
    *,
    flags: dict | None = None,
    sale_gift: str | None = None,
    sale_price=None,
    rent_price_per_day=None,
    listing_status: str | None = None,
) -> BookCopy:
    """
    Update listing flags.

    Prefer ``flags`` + ``sale_gift`` ("" | for_sale | as_gift).
    Legacy ``listing_status`` still accepted.
    """
    data = {f: getattr(copy, f) for f in LISTING_FLAG_FIELDS}

    if listing_status and flags is None and sale_gift is None:
        status = str(listing_status).strip()
        data = {f: False for f in LISTING_FLAG_FIELDS}
        mapping = {
            "fee_sharing": {"is_fee_sharing": True},
            "hidden": {"is_fee_sharing": True, "is_hidden": True},
            "for_sale": {"is_for_sale": True},
            "for_rent": {"is_for_rent": True},
            "as_gift": {"is_as_gift": True},
            "for_exchange": {"is_for_exchange": True},
            "free_of_deposit": {"is_fee_sharing": True, "is_free_of_deposit": True},
        }
        if status not in mapping:
            raise ValidationError("Невідомий статус примірника.")
        data.update(mapping[status])
        sale_gift = "for_sale" if data["is_for_sale"] else ("as_gift" if data["is_as_gift"] else "")

    if flags:
        for name in LISTING_FLAG_FIELDS:
            if name in flags:
                data[name] = _truthy(flags[name])

    sg = "" if sale_gift is None else str(sale_gift).strip()
    if sale_gift is not None:
        if sg == "for_sale":
            data["is_for_sale"] = True
            data["is_as_gift"] = False
        elif sg == "as_gift":
            data["is_for_sale"] = False
            data["is_as_gift"] = True
        elif sg == "":
            data["is_for_sale"] = False
            data["is_as_gift"] = False
        else:
            raise ValidationError("sale_gift: очікується '', for_sale або as_gift.")

    if data["is_for_sale"] and data["is_as_gift"]:
        raise ValidationError("For sale і As a gift несумісні — оберіть лише один.")

    for name in LISTING_FLAG_FIELDS:
        setattr(copy, name, bool(data[name]))

    sale = parse_money(sale_price)
    rent = parse_money(rent_price_per_day)
    copy.sale_price = sale if copy.is_for_sale else None
    copy.rent_price_per_day = rent if copy.is_for_rent else None

    if not any(getattr(copy, f) for f in LISTING_FLAG_FIELDS):
        copy.is_fee_sharing = True

    copy.full_clean()
    copy.save(
        update_fields=[*LISTING_FLAG_FIELDS, "sale_price", "rent_price_per_day"]
    )
    return copy


def serialize_copy_listing(copy: BookCopy | None) -> dict | None:
    if not copy:
        return None
    labels = copy.listing_labels()
    return {
        "is_fee_sharing": copy.is_fee_sharing,
        "is_hidden": copy.is_hidden,
        "is_for_sale": copy.is_for_sale,
        "is_for_rent": copy.is_for_rent,
        "is_as_gift": copy.is_as_gift,
        "is_for_exchange": copy.is_for_exchange,
        "is_free_of_deposit": copy.is_free_of_deposit,
        "listing_labels": labels,
        "sale_gift": (
            "for_sale"
            if copy.is_for_sale
            else ("as_gift" if copy.is_as_gift else "")
        ),
        "sale_price": str(copy.sale_price) if copy.sale_price is not None else None,
        "rent_price_per_day": (
            str(copy.rent_price_per_day) if copy.rent_price_per_day is not None else None
        ),
        "requires_deposit": copy.requires_deposit,
        "is_publicly_listed": copy.is_publicly_listed,
        "listing_status_display": ", ".join(labels),
    }
