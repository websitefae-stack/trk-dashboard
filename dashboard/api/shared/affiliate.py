"""
A coach's own affiliate link for the public store/course site: one
link per coach (not one per product), carrying a short code that gets
remembered by the shopper's browser (see resilient_domains' cart.js)
until they actually check out - whatever they end up buying, not just
whatever page the link first landed on.

Which items/courses actually earn a commission, and how much, is set
up separately by the franchisor (Affiliate Product Setting) - this
module resolves a sale against those settings and records one
Affiliate Commission row per commission-eligible line, only ever for a
genuinely paid purchase (never for a click, and never for an invoice
that hasn't been paid), via record_affiliate_commission_for_invoice,
called from webshop_purchase._fulfil_checkout_session right after a
guest checkout is confirmed paid by Stripe.

Deliberately scoped to the public guest webshop checkout only - a
coach raising an invoice for their own client through the normal
dashboard flow isn't a sale that came through anyone's affiliate link,
so it's never considered here.
"""

import random
import re
import string

import frappe
from frappe import _
from frappe.utils import flt, nowdate

from dashboard.api.shared.permissions import ensure_office_user, get_current_coach_name
from dashboard.api.shared.utils import coalesce_str, coalesce_raw
from dashboard.api.shared.profile import PUBLIC_SITE_URL

AFFILIATE_SETTING_DOCTYPE = "Affiliate Product Setting"
AFFILIATE_COMMISSION_DOCTYPE = "Affiliate Commission"


def _coach_label(coach_name):
    if not coach_name:
        return ""
    return frappe.db.get_value("Coach", coach_name, "coach_name") or coach_name


# =====================================================
# AFFILIATE CODE / LINK
# =====================================================

def _slugify_coach_name(coach_name):
    label = _coach_label(coach_name) or coach_name
    slug = re.sub(r"[^a-z0-9]+", "", label.lower())
    return slug[:16] or "coach"


def _ensure_affiliate_code(coach_name):
    """Idempotent - returns the existing code if one's already set,
    otherwise mints and saves a new one. Called lazily (the first time
    a coach's own link is actually requested), not backfilled for every
    coach up front - see add_coach_affiliate_code_field.py's own
    docstring for why."""
    existing = frappe.db.get_value("Coach", coach_name, "affiliate_code")
    if existing:
        return existing

    base = _slugify_coach_name(coach_name)

    for _attempt in range(20):
        candidate = base + "".join(random.choices(string.digits, k=3))
        if not frappe.db.exists("Coach", {"affiliate_code": candidate}):
            frappe.db.set_value("Coach", coach_name, "affiliate_code", candidate, update_modified=False)
            frappe.db.commit()
            return candidate

    # Vanishingly unlikely (20 random 3-digit suffixes all colliding),
    # but never leave this coach without a code - fall back to
    # something guaranteed unique.
    candidate = base + frappe.generate_hash(length=6)
    frappe.db.set_value("Coach", coach_name, "affiliate_code", candidate, update_modified=False)
    frappe.db.commit()
    return candidate


def _affiliate_link(code):
    # Deliberately NOT frappe.utils.get_url() - this code runs on the
    # dashboard's own site, a different host entirely from the public
    # store (/trh-store lives on resilient_domains' site), so get_url()
    # built a link back to the dashboard's own internal hostname instead
    # of a real, shareable public URL (confirmed live). PUBLIC_SITE_URL
    # is the same hardcoded public hostname every other coach/client-
    # facing link in this app already uses (see profile.py).
    return "{0}/trh-store?aff={1}".format(PUBLIC_SITE_URL, code)


@frappe.whitelist()
def get_my_affiliate_link():
    """Coach-only - their own shareable link, generating a code the
    first time this is ever called for them."""
    coach_name = get_current_coach_name(optional=False)
    code = _ensure_affiliate_code(coach_name)

    return {"code": code, "link": _affiliate_link(code)}


@frappe.whitelist()
def get_my_affiliate_summary():
    """Coach-only - their own link plus running commission/click totals,
    for the coach dashboard's own affiliate section."""
    coach_name = get_current_coach_name(optional=False)
    code = _ensure_affiliate_code(coach_name)

    rows = frappe.get_all(
        AFFILIATE_COMMISSION_DOCTYPE,
        filters={"coach": coach_name},
        fields=["status", "commission_amount"],
    )

    pending_total = sum(flt(row.commission_amount) for row in rows if row.status == "Pending")
    paid_total = sum(flt(row.commission_amount) for row in rows if row.status == "Paid")

    return {
        "code": code,
        "link": _affiliate_link(code),
        "pending_total": pending_total,
        "paid_total": paid_total,
        "sale_count": len(rows),
        "click_count": frappe.db.get_value("Coach", coach_name, "affiliate_click_count") or 0,
    }


@frappe.whitelist(allow_guest=True)
def record_affiliate_click(code=None):
    """
    Called once from resilient_domains' cart.js, the moment a genuine
    ?aff=<code> is actually found in the URL (not on every subsequent
    page view while it's just sitting in localStorage) - a simple
    running count per coach, for "how many clicks did my link get"
    rather than full click-by-click logging. Guest-accessible like the
    rest of the public checkout surface; silently does nothing for an
    unknown/mistyped code rather than throwing, same as
    resolve_affiliate_coach.
    """
    code = (code or "").strip()
    if not code:
        return {"ok": True}

    coach_name = frappe.db.get_value("Coach", {"affiliate_code": code}, "name")
    if not coach_name:
        return {"ok": True}

    # A single atomic UPDATE rather than read-then-write - two clicks
    # landing in the same instant must never both read the same stale
    # count and silently lose one increment.
    frappe.db.sql(
        "UPDATE `tabCoach` SET affiliate_click_count = IFNULL(affiliate_click_count, 0) + 1 WHERE name = %s",
        (coach_name,),
    )
    frappe.db.commit()

    return {"ok": True}


def resolve_affiliate_coach(affiliate_code):
    """Used by webshop_purchase.create_checkout_session to resolve a
    raw code (from the shopper's cart, carried via localStorage - see
    resilient_domains' cart.js) to a real Coach at the moment the
    checkout doc is created. Returns "" for anything that doesn't
    match a real coach, rather than throwing - an expired/mistyped/
    tampered code should just mean no attribution, never a broken
    checkout."""
    affiliate_code = (affiliate_code or "").strip()
    if not affiliate_code:
        return ""

    return frappe.db.get_value("Coach", {"affiliate_code": affiliate_code}, "name") or ""


# =====================================================
# COMMISSION SETTINGS (franchisor)
# =====================================================

@frappe.whitelist()
def get_affiliate_product_settings():
    ensure_office_user()

    rows = frappe.get_all(
        AFFILIATE_SETTING_DOCTYPE,
        fields=["name", "item", "course", "enabled", "commission_type", "commission_percent", "commission_flat_amount"],
        order_by="modified desc",
    )

    for row in rows:
        if row.item:
            row["label"] = frappe.db.get_value("Item", row.item, "item_name") or row.item
        elif row.course:
            row["label"] = frappe.db.get_value("LMS Course", row.course, "title") or row.course
        else:
            row["label"] = row.name

    return rows


@frappe.whitelist()
def search_affiliate_items(query=None):
    """Franchisor-only item picker for the Affiliate Settings form -
    deliberately excludes variants (has_variants items are the ones to
    pick; a variant itself can never carry its own setting, see
    AffiliateProductSetting.validate)."""
    ensure_office_user()

    query = coalesce_str("query", query)
    filters = {"disabled": 0, "variant_of": ["in", ["", None]]}
    if query:
        filters["item_name"] = ["like", f"%{query}%"]

    return frappe.get_all(
        "Item", filters=filters, fields=["name", "item_name", "has_variants"],
        order_by="item_name asc", limit_page_length=20,
    )


@frappe.whitelist()
def search_affiliate_courses(query=None):
    """Franchisor-only course picker for the Affiliate Settings form."""
    ensure_office_user()

    if not frappe.db.exists("DocType", "LMS Course"):
        return []

    query = coalesce_str("query", query)
    filters = {}
    if query:
        filters["title"] = ["like", f"%{query}%"]

    return frappe.get_all(
        "LMS Course", filters=filters, fields=["name", "title"],
        order_by="title asc", limit_page_length=20,
    )


@frappe.whitelist()
def save_affiliate_product_setting(name=None, item=None, course=None, commission_type=None, commission_percent=None, commission_flat_amount=None, enabled=1):
    ensure_office_user()

    name = coalesce_str("name", name)
    item = coalesce_str("item", item)
    course = coalesce_str("course", course)
    commission_type = coalesce_str("commission_type", commission_type) or "Percentage"

    if bool(item) == bool(course):
        frappe.throw(_("Choose exactly one Item or Course."))

    if item:
        if not frappe.db.exists("Item", item):
            frappe.throw(_("Item not found."))
        # A variant template (has_variants=1) is deliberately allowed
        # here - that's the whole point, setting it once covers every
        # variant (see _affiliate_setting_for_item's own fallback).
        existing = frappe.db.exists(AFFILIATE_SETTING_DOCTYPE, {"item": item, "name": ["!=", name or ""]})
        if existing:
            frappe.throw(_("{0} already has an affiliate setting.").format(item))
    else:
        if not frappe.db.exists("LMS Course", course):
            frappe.throw(_("Course not found."))
        existing = frappe.db.exists(AFFILIATE_SETTING_DOCTYPE, {"course": course, "name": ["!=", name or ""]})
        if existing:
            frappe.throw(_("{0} already has an affiliate setting.").format(course))

    doc = frappe.get_doc(AFFILIATE_SETTING_DOCTYPE, name) if name and frappe.db.exists(AFFILIATE_SETTING_DOCTYPE, name) else frappe.new_doc(AFFILIATE_SETTING_DOCTYPE)

    doc.item = item or None
    doc.course = course or None
    doc.commission_type = commission_type
    doc.commission_percent = flt(coalesce_raw("commission_percent", commission_percent))
    doc.commission_flat_amount = flt(coalesce_raw("commission_flat_amount", commission_flat_amount))
    doc.enabled = 1 if int(coalesce_raw("enabled", enabled) or 0) else 0

    doc.save(ignore_permissions=True)
    frappe.db.commit()

    return {"ok": True, "name": doc.name}


@frappe.whitelist()
def delete_affiliate_product_setting(name=None):
    ensure_office_user()

    name = coalesce_str("name", name)
    if not name or not frappe.db.exists(AFFILIATE_SETTING_DOCTYPE, name):
        frappe.throw(_("Affiliate setting not found."))

    if frappe.db.exists(AFFILIATE_COMMISSION_DOCTYPE, {"affiliate_setting": name}):
        frappe.throw(_(
            "This setting already has commissions recorded against it - disable it instead of deleting, so "
            "the history stays intact."
        ))

    frappe.delete_doc(AFFILIATE_SETTING_DOCTYPE, name, ignore_permissions=True)
    frappe.db.commit()

    return {"ok": True}


# =====================================================
# COMMISSION CALCULATION (checkout-time)
# =====================================================

def _affiliate_setting_for_item(item_code):
    if not item_code:
        return None

    setting_name = frappe.db.get_value(AFFILIATE_SETTING_DOCTYPE, {"item": item_code, "enabled": 1}, "name")
    if setting_name:
        return frappe.get_doc(AFFILIATE_SETTING_DOCTYPE, setting_name)

    # No direct setting on this exact item - if it's a variant, fall
    # back to whatever's set on its own template, per Ashley's own
    # instruction: "set the affiliate on the main product and it pulls
    # through to all the variations".
    template = frappe.db.get_value("Item", item_code, "variant_of")
    if not template:
        return None

    setting_name = frappe.db.get_value(AFFILIATE_SETTING_DOCTYPE, {"item": template, "enabled": 1}, "name")
    return frappe.get_doc(AFFILIATE_SETTING_DOCTYPE, setting_name) if setting_name else None


def _affiliate_setting_for_course(course):
    if not course:
        return None

    setting_name = frappe.db.get_value(AFFILIATE_SETTING_DOCTYPE, {"course": course, "enabled": 1}, "name")
    return frappe.get_doc(AFFILIATE_SETTING_DOCTYPE, setting_name) if setting_name else None


def _compute_commission(setting, sale_amount):
    sale_amount = flt(sale_amount)

    if setting.commission_type == "Flat Amount":
        return flt(setting.commission_flat_amount), "£{0:.2f} flat".format(flt(setting.commission_flat_amount))

    rate = flt(setting.commission_percent)
    return flt(sale_amount * rate / 100, 2), "{0:g}%".format(rate)


def record_affiliate_commission_for_invoice(invoice, affiliate_coach, client_full_name=None, client_email=None):
    """
    Called from webshop_purchase._fulfil_checkout_session right after a
    guest checkout is confirmed paid - never from anywhere an invoice
    might still be unpaid. One Affiliate Commission row per invoice
    line that matches an enabled Affiliate Product Setting (by the
    item directly, its item's variant template, or the LMS course it
    unlocks) - an invoice can earn commission on more than one line.

    Best-effort: never allowed to raise, since this runs after the
    customer has already been charged and the order already recorded -
    a commission-recording problem must never look like a failed
    purchase.
    """
    if not affiliate_coach:
        return

    try:
        _record_affiliate_commission_for_invoice(invoice, affiliate_coach, client_full_name, client_email)
    except Exception:
        frappe.log_error(frappe.get_traceback(), f"Affiliate Commission Recording Failed - {invoice.name}")


def _record_affiliate_commission_for_invoice(invoice, affiliate_coach, client_full_name, client_email):
    if not frappe.db.exists(AFFILIATE_SETTING_DOCTYPE):
        return

    # Idempotent against a Stripe webhook retry re-delivering the same
    # already-fulfilled checkout - _fulfil_checkout_session's own
    # "already Paid" guard normally prevents this function being
    # called twice for the same invoice at all, but this is a second,
    # independent safety net specific to this doctype.
    if frappe.db.exists(AFFILIATE_COMMISSION_DOCTYPE, {"sales_invoice": invoice.name}):
        return

    item_meta = frappe.get_meta("Item")
    unlocks_course_field = "custom_unlocks_lms_course" if item_meta.has_field("custom_unlocks_lms_course") else None

    for row in invoice.items or []:
        if not row.item_code:
            continue

        setting = _affiliate_setting_for_item(row.item_code)

        matched_item = row.item_code if setting else None
        matched_course = None

        if not setting and unlocks_course_field:
            course = frappe.db.get_value("Item", row.item_code, unlocks_course_field)
            if course:
                setting = _affiliate_setting_for_course(course)
                matched_course = course if setting else None

        if not setting:
            continue

        sale_amount = flt(row.amount)
        commission_amount, rate_snapshot = _compute_commission(setting, sale_amount)

        if commission_amount <= 0:
            continue

        commission = frappe.new_doc(AFFILIATE_COMMISSION_DOCTYPE)
        commission.coach = affiliate_coach
        commission.affiliate_setting = setting.name
        commission.item = matched_item or (row.item_code if setting.item else None)
        commission.course = matched_course or setting.course
        commission.sales_invoice = invoice.name
        commission.sale_amount = sale_amount
        commission.commission_rate_snapshot = rate_snapshot
        commission.commission_amount = commission_amount
        commission.client_full_name = client_full_name or ""
        commission.client_email = client_email or ""
        commission.status = "Pending"
        commission.insert(ignore_permissions=True)

    frappe.db.commit()


# =====================================================
# COMMISSIONS (franchisor)
# =====================================================

@frappe.whitelist()
def get_coach_options_for_affiliates():
    ensure_office_user()

    return frappe.get_all("Coach", fields=["name", "coach_name"], order_by="coach_name asc")


@frappe.whitelist()
def get_affiliate_coach_performance():
    """Franchisor-only - one row per coach who has ever had a click or a
    commission, for the Affiliates page's own "who's actually driving
    sales" summary (link clicks are otherwise invisible anywhere in the
    per-sale Commissions table below)."""
    ensure_office_user()

    coaches = frappe.get_all(
        "Coach", filters={"affiliate_code": ["is", "set"]},
        fields=["name", "coach_name", "affiliate_click_count"],
    )

    commission_rows = frappe.get_all(
        AFFILIATE_COMMISSION_DOCTYPE, fields=["coach", "status", "commission_amount"],
    )
    by_coach = {}
    for row in commission_rows:
        bucket = by_coach.setdefault(row.coach, {"sale_count": 0, "pending_total": 0, "paid_total": 0})
        bucket["sale_count"] += 1
        if row.status == "Pending":
            bucket["pending_total"] += flt(row.commission_amount)
        else:
            bucket["paid_total"] += flt(row.commission_amount)

    results = []
    for coach in coaches:
        bucket = by_coach.get(coach.name, {"sale_count": 0, "pending_total": 0, "paid_total": 0})
        if not coach.affiliate_click_count and not bucket["sale_count"]:
            continue
        results.append({
            "coach": coach.name,
            "coach_label": coach.coach_name or coach.name,
            "click_count": coach.affiliate_click_count or 0,
            "sale_count": bucket["sale_count"],
            "pending_total": bucket["pending_total"],
            "paid_total": bucket["paid_total"],
        })

    results.sort(key=lambda r: r["click_count"], reverse=True)
    return results


def _get_affiliate_sale_items(commission_name, restrict_to_coach=None):
    if not commission_name or not frappe.db.exists(AFFILIATE_COMMISSION_DOCTYPE, commission_name):
        frappe.throw(_("Commission record not found."))

    commission = frappe.get_doc(AFFILIATE_COMMISSION_DOCTYPE, commission_name)

    if restrict_to_coach and commission.coach != restrict_to_coach:
        frappe.throw(_("You do not have permission to view this."), frappe.PermissionError)

    if not commission.sales_invoice or not frappe.db.exists("Sales Invoice", commission.sales_invoice):
        return {"items": [], "grand_total": 0}

    items = frappe.get_all(
        "Sales Invoice Item",
        filters={"parent": commission.sales_invoice},
        fields=["item_code", "item_name", "qty", "rate", "amount"],
        order_by="idx asc",
    )
    grand_total = frappe.db.get_value("Sales Invoice", commission.sales_invoice, "grand_total") or 0

    return {"items": items, "grand_total": grand_total}


@frappe.whitelist()
def get_affiliate_sale_items(commission=None):
    """Franchisor-only - every line on the sale this commission came
    from (not just the commissioned line), so "what did this person
    buy" is answerable without going into Desk."""
    ensure_office_user()

    commission = coalesce_str("commission", commission)
    return _get_affiliate_sale_items(commission)


@frappe.whitelist()
def get_my_affiliate_sale_items(commission=None):
    """Coach-only, and only for their own commission - same shape as
    get_affiliate_sale_items, for the coach dashboard's own drill-down."""
    coach_name = get_current_coach_name(optional=False)

    commission = coalesce_str("commission", commission)
    return _get_affiliate_sale_items(commission, restrict_to_coach=coach_name)


@frappe.whitelist()
def get_my_affiliate_commissions():
    """Coach-only - their own sale list (customer, price, commission),
    for the coach dashboard's own affiliate section."""
    coach_name = get_current_coach_name(optional=False)

    rows = frappe.get_all(
        AFFILIATE_COMMISSION_DOCTYPE,
        filters={"coach": coach_name},
        fields=[
            "name", "item", "course", "sale_amount", "commission_rate_snapshot",
            "commission_amount", "client_full_name", "client_email", "status", "creation",
        ],
        order_by="creation desc",
    )

    for row in rows:
        if row.item:
            row["product_label"] = frappe.db.get_value("Item", row.item, "item_name") or row.item
        elif row.course:
            row["product_label"] = frappe.db.get_value("LMS Course", row.course, "title") or row.course
        else:
            row["product_label"] = ""

    return rows


@frappe.whitelist()
def get_affiliate_commissions(coach=None, status=None):
    ensure_office_user()

    filters = {}
    coach = coalesce_str("coach", coach)
    status = coalesce_str("status", status)

    if coach:
        filters["coach"] = coach
    if status:
        filters["status"] = status

    rows = frappe.get_all(
        AFFILIATE_COMMISSION_DOCTYPE,
        filters=filters,
        fields=[
            "name", "coach", "item", "course", "sales_invoice", "sale_amount",
            "commission_rate_snapshot", "commission_amount", "client_full_name",
            "client_email", "status", "paid_on", "creation",
        ],
        order_by="creation desc",
    )

    for row in rows:
        row["coach_label"] = _coach_label(row.coach)
        if row.item:
            row["product_label"] = frappe.db.get_value("Item", row.item, "item_name") or row.item
        elif row.course:
            row["product_label"] = frappe.db.get_value("LMS Course", row.course, "title") or row.course
        else:
            row["product_label"] = ""

    return rows


@frappe.whitelist()
def mark_affiliate_commissions_paid(names=None):
    ensure_office_user()

    names = coalesce_raw("names", names)
    if isinstance(names, str):
        import json
        try:
            names = json.loads(names)
        except Exception:
            names = [names]

    names = [n for n in (names or []) if n and frappe.db.exists(AFFILIATE_COMMISSION_DOCTYPE, n)]
    if not names:
        frappe.throw(_("Nothing to mark paid."))

    for name in names:
        frappe.db.set_value(AFFILIATE_COMMISSION_DOCTYPE, name, {"status": "Paid", "paid_on": nowdate()})

    frappe.db.commit()

    return {"ok": True, "updated": len(names)}
