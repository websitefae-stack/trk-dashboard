"""
A coach's or session worker's own affiliate link for the public
store/course site: one link per earner (not one per product), carrying
a short code that gets remembered by the shopper's browser (see
resilient_domains' cart.js) until they actually check out - whatever
they end up buying, not just whatever page the link first landed on.

Coach and Session Worker are two separate doctypes, so every earner-
facing lookup here resolves "whoever's actually logged in" via
_current_earner(), and every Affiliate Commission row carries exactly
one of a coach or a session_worker field (never both) - see
_earner_filter/_earner_label. Affiliate codes themselves are unique
across BOTH tables, enforced in _code_in_use since a DB-level unique
constraint on either table alone can't see across to the other one.

Which items/courses actually earn a commission, and how much, is set
up separately by the franchisor (Affiliate Product Setting) - this
module resolves a sale against those settings and records one
Affiliate Commission row per commission-eligible line, only ever for a
genuinely paid purchase (never for a click, and never for an invoice
that hasn't been paid), via record_affiliate_commission_for_invoice,
called from webshop_purchase._fulfil_checkout_session right after a
guest checkout is confirmed paid by Stripe.

Deliberately scoped to the public guest webshop checkout only - a
coach/session worker raising an invoice for their own client through
the normal dashboard flow isn't a sale that came through anyone's
affiliate link, so it's never considered here.
"""

import random
import re
import string
from urllib.parse import quote

import frappe
from frappe import _
from frappe.utils import flt, nowdate

from dashboard.api.shared.permissions import ensure_office_user, get_current_coach_name, get_current_session_worker_name
from dashboard.api.shared.utils import coalesce_str, coalesce_raw
from dashboard.api.shared.profile import PUBLIC_SITE_URL
from dashboard.api.shared.session_workers import (
    SESSION_WORKER_LABEL_FIELDS,
    get_first_value,
    get_session_worker_fields,
    get_session_worker_label,
    has_field,
)

AFFILIATE_SETTING_DOCTYPE = "Affiliate Product Setting"
AFFILIATE_COMMISSION_DOCTYPE = "Affiliate Commission"
COACH_DOCTYPE = "Coach"
SESSION_WORKER_DOCTYPE = "Session Worker"


def _coach_label(coach_name):
    if not coach_name:
        return ""
    return frappe.db.get_value("Coach", coach_name, "coach_name") or coach_name


def _earner_label(coach=None, session_worker=None):
    return _coach_label(coach) if coach else get_session_worker_label(session_worker)


def _current_earner():
    """Whichever identity the current logged-in user actually has -
    Coach checked first (the common case), falling back to Session
    Worker - same dual-resolution pattern testimonials.py's save_
    testimonial already uses. Throws if neither applies, same as
    get_current_coach_name(optional=False) did before this was
    generalised."""
    coach_name = get_current_coach_name(optional=True)
    if coach_name:
        return COACH_DOCTYPE, coach_name

    worker_name = get_current_session_worker_name(optional=True)
    if worker_name:
        return SESSION_WORKER_DOCTYPE, worker_name

    frappe.throw(_("No Coach or Session Worker profile is linked to your user."), frappe.PermissionError)


def _earner_filter(doctype, name):
    """The Affiliate Commission filter for one earner - coach and
    session_worker are separate Link fields (never a single generic
    one), so this is the one place that decides which column a given
    (doctype, name) pair actually means."""
    return {"coach": name} if doctype == COACH_DOCTYPE else {"session_worker": name}


# =====================================================
# AFFILIATE CODE / LINK
# =====================================================

def _slugify_label(label):
    slug = re.sub(r"[^a-z0-9]+", "", (label or "").lower())
    return slug[:16] or "coach"


def _code_in_use(candidate):
    """Affiliate codes must be unique across BOTH Coach and Session
    Worker, not just within whichever table a new one's being minted
    for - they're two separate tables, so a DB-level unique constraint
    on either only ever guards within that one table, and code
    resolution (record_affiliate_click, resolve_affiliate_earner)
    needs exactly one match regardless of which doctype it turns out
    to be."""
    return bool(
        frappe.db.exists(COACH_DOCTYPE, {"affiliate_code": candidate})
        or frappe.db.exists(SESSION_WORKER_DOCTYPE, {"affiliate_code": candidate})
    )


def _ensure_affiliate_code_for(doctype, name):
    """Idempotent - returns the existing code if one's already set,
    otherwise mints and saves a new one. Called lazily (the first time
    this coach/session worker's own link is actually requested), not
    backfilled up front - see add_coach_affiliate_code_field.py's own
    docstring for why."""
    existing = frappe.db.get_value(doctype, name, "affiliate_code")
    if existing:
        return existing

    label = _earner_label(name) if doctype == COACH_DOCTYPE else _earner_label(session_worker=name)
    base = _slugify_label(label)

    for _attempt in range(20):
        candidate = base + "".join(random.choices(string.digits, k=3))
        if not _code_in_use(candidate):
            frappe.db.set_value(doctype, name, "affiliate_code", candidate, update_modified=False)
            frappe.db.commit()
            return candidate

    # Vanishingly unlikely (20 random 3-digit suffixes all colliding),
    # but never leave this coach/session worker without a code - fall
    # back to something guaranteed unique.
    candidate = base + frappe.generate_hash(length=6)
    frappe.db.set_value(doctype, name, "affiliate_code", candidate, update_modified=False)
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
    """Coach or Session Worker - their own shareable link, generating a
    code the first time this is ever called for them."""
    doctype, name = _current_earner()
    code = _ensure_affiliate_code_for(doctype, name)

    return {"code": code, "link": _affiliate_link(code)}


@frappe.whitelist()
def get_my_affiliate_summary():
    """Coach or Session Worker - their own link plus running commission/
    click totals, for their dashboard's own affiliate section."""
    doctype, name = _current_earner()
    code = _ensure_affiliate_code_for(doctype, name)

    rows = frappe.get_all(
        AFFILIATE_COMMISSION_DOCTYPE,
        filters=_earner_filter(doctype, name),
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
        "click_count": frappe.db.get_value(doctype, name, "affiliate_click_count") or 0,
    }


@frappe.whitelist()
def get_my_affiliate_product_links():
    """Coach or Session Worker - get_earner_affiliate_links scoped to
    whichever identity is currently logged in."""
    doctype, name = _current_earner()
    return get_earner_affiliate_links(doctype, name)


def get_earner_affiliate_links(doctype, name):
    """
    One row per enabled Affiliate Product Setting, pointing straight at
    that specific item/course's own public page (not just the generic
    store-wide link get_my_affiliate_link gives) - so a coach/session
    worker can share "buy this exact course" rather than only "browse
    the whole store", still carrying their own code - alongside that
    one link's own clicks/earned/due, not just the earner-wide totals.
    Shared by the earner's own page (get_my_affiliate_product_links)
    and the franchisor's per-earner drill-down (get_affiliate_coach_links,
    despite its name - see its own docstring) - same shape either way,
    only who's allowed to ask for which earner differs.
    """
    code = _ensure_affiliate_code_for(doctype, name)

    settings = frappe.get_all(
        AFFILIATE_SETTING_DOCTYPE,
        filters={"enabled": 1},
        fields=["name", "item", "course", "click_count"],
    )
    if not settings:
        return []

    unlocks_course_field = "custom_unlocks_lms_course" if frappe.get_meta("Item").has_field("custom_unlocks_lms_course") else None

    commission_filters = _earner_filter(doctype, name)
    commission_filters["affiliate_setting"] = ["in", [s.name for s in settings]]
    commission_rows = frappe.get_all(
        AFFILIATE_COMMISSION_DOCTYPE,
        filters=commission_filters,
        fields=["affiliate_setting", "status", "commission_amount"],
    )
    earned_by_setting = {}
    due_by_setting = {}
    for row in commission_rows:
        earned_by_setting[row.affiliate_setting] = earned_by_setting.get(row.affiliate_setting, 0) + flt(row.commission_amount)
        if row.status == "Pending":
            due_by_setting[row.affiliate_setting] = due_by_setting.get(row.affiliate_setting, 0) + flt(row.commission_amount)

    links = []
    for setting in settings:
        if setting.item:
            # A course's own backing Item (store_products._ensure_course_item)
            # is never a second real product - skip it so a course with both
            # an Item-level and Course-level setting only ever shows one link,
            # not two for the same course (see disable_affiliate_settings_on_
            # course_backing_items.py, which cleans up any existing one of
            # these - this is just a defensive backstop against a new one).
            if unlocks_course_field and frappe.db.get_value("Item", setting.item, unlocks_course_field):
                continue

            label = frappe.db.get_value("Item", setting.item, "item_name") or setting.item
            link = "{0}/buy?item={1}&aff={2}".format(PUBLIC_SITE_URL, quote(setting.item), quote(code))
        else:
            label = frappe.db.get_value("LMS Course", setting.course, "title") or setting.course
            link = "{0}/trh-course-detail?slug={1}&aff={2}".format(PUBLIC_SITE_URL, quote(setting.course), quote(code))

        links.append({
            "label": label,
            "link": link,
            "clicks": setting.click_count or 0,
            "earned": earned_by_setting.get(setting.name, 0),
            "due": due_by_setting.get(setting.name, 0),
        })

    links.sort(key=lambda row: row["label"].lower())
    return links


@frappe.whitelist()
def get_affiliate_coach_links(coach=None):
    """Franchisor-only - get_earner_affiliate_links for any one coach OR
    session worker (despite the param name - affiliates.js's Performance
    table drill-down calls this same endpoint for either kind of row, so
    it resolves which doctype the given name actually belongs to rather
    than needing a second, separate endpoint the frontend would have to
    know to call instead)."""
    ensure_office_user()

    coach = (coach or "").strip()
    if coach and frappe.db.exists(COACH_DOCTYPE, coach):
        return get_earner_affiliate_links(COACH_DOCTYPE, coach)
    if coach and frappe.db.exists(SESSION_WORKER_DOCTYPE, coach):
        return get_earner_affiliate_links(SESSION_WORKER_DOCTYPE, coach)

    frappe.throw(_("A valid coach or session worker is required."))


@frappe.whitelist(allow_guest=True)
def record_affiliate_click(code=None, item=None, course=None):
    """
    Called once from resilient_domains' cart.js, the moment a genuine
    ?aff=<code> is actually found in the URL (not on every subsequent
    page view while it's just sitting in localStorage) - a simple
    running count per earner, for "how many clicks did my link get"
    rather than full click-by-click logging. Guest-accessible like the
    rest of the public checkout surface; silently does nothing for an
    unknown/mistyped code rather than throwing, same as
    resolve_affiliate_earner.

    item/course (whichever's in the landing URL - /buy?item=... or
    /trh-course-detail?slug=...) additionally bumps that one Affiliate
    Product Setting's own click_count, same resolution rules record_
    affiliate_commission_for_invoice already uses (variant falls back
    to its template) - so "Your Links" can show how many clicks each
    individual link got, not just the earner-wide total. Left blank for
    the generic /trh-store?aff= link, which isn't tied to any one
    product.
    """
    code = (code or "").strip()
    if not code:
        return {"ok": True}

    earner = resolve_affiliate_earner(code)
    doctype = earner["doctype"]
    name = earner["name"]
    if not name:
        return {"ok": True}

    # A single atomic UPDATE rather than read-then-write - two clicks
    # landing in the same instant must never both read the same stale
    # count and silently lose one increment.
    table = "tabCoach" if doctype == COACH_DOCTYPE else "tabSession Worker"
    frappe.db.sql(
        "UPDATE `{0}` SET affiliate_click_count = IFNULL(affiliate_click_count, 0) + 1 WHERE name = %s".format(table),
        (name,),
    )

    item = (item or "").strip()
    course = (course or "").strip()
    setting = _affiliate_setting_for_item(item) if item else (_affiliate_setting_for_course(course) if course else None)

    if setting:
        frappe.db.sql(
            "UPDATE `tabAffiliate Product Setting` SET click_count = IFNULL(click_count, 0) + 1 WHERE name = %s",
            (setting.name,),
        )

    frappe.db.commit()

    return {"ok": True}


def resolve_affiliate_earner(affiliate_code):
    """Used by webshop_purchase.create_checkout_session to resolve a
    raw code (from the shopper's cart, carried via localStorage - see
    resilient_domains' cart.js) to a real Coach or Session Worker at
    the moment the checkout doc is created. Returns {"doctype": "",
    "name": ""} for anything that doesn't match either - an expired/
    mistyped/tampered code should just mean no attribution, never a
    broken checkout. _code_in_use guarantees a code never belongs to
    both tables at once, so at most one of the two lookups ever hits."""
    affiliate_code = (affiliate_code or "").strip()
    if not affiliate_code:
        return {"doctype": "", "name": ""}

    coach_name = frappe.db.get_value(COACH_DOCTYPE, {"affiliate_code": affiliate_code}, "name")
    if coach_name:
        return {"doctype": COACH_DOCTYPE, "name": coach_name}

    worker_name = frappe.db.get_value(SESSION_WORKER_DOCTYPE, {"affiliate_code": affiliate_code}, "name")
    if worker_name:
        return {"doctype": SESSION_WORKER_DOCTYPE, "name": worker_name}

    return {"doctype": "", "name": ""}


# =====================================================
# COMMISSION SETTINGS (franchisor)
# =====================================================

@frappe.whitelist()
def get_affiliate_commission_catalog():
    """
    Franchisor-only - every eligible Item (not disabled, not itself a
    variant - a variant template is the one to set, see
    AffiliateProductSetting.validate) and every Course, each annotated
    with its existing Affiliate Product Setting if it has one. Replaces
    the earlier search-as-you-type picker - confirmed live that
    selecting a datalist suggestion doesn't reliably commit the exact
    expected value in every browser, which kept throwing "Pick a
    course/item from the list" even on a real selection. Listing
    everything up front removes the need to match a typed string
    against anything at all.
    """
    ensure_office_user()

    existing_settings = frappe.get_all(
        AFFILIATE_SETTING_DOCTYPE,
        fields=["name", "item", "course", "enabled", "commission_type", "commission_percent", "commission_flat_amount"],
    )
    settings_by_item = {row.item: row for row in existing_settings if row.item}
    settings_by_course = {row.course: row for row in existing_settings if row.course}

    def _setting_fields(setting):
        if not setting:
            return {
                "setting_name": None, "enabled": 0, "commission_type": "Percentage",
                "commission_percent": 0, "commission_flat_amount": 0,
            }
        return {
            "setting_name": setting.name, "enabled": setting.enabled,
            "commission_type": setting.commission_type,
            "commission_percent": setting.commission_percent, "commission_flat_amount": setting.commission_flat_amount,
        }

    # custom_store_enabled - same flag store_products.get_store_products()
    # filters on - is what actually distinguishes a real Store product
    # from a Service (bookable coaching sessions etc, never something a
    # shared link sells to the public) - plain disabled=0 pulled in
    # every service Item too, which Ashley doesn't want listed here at
    # all.
    item_filters = {"disabled": 0, "variant_of": ["in", ["", None]]}
    if frappe.get_meta("Item").has_field("custom_store_enabled"):
        item_filters["custom_store_enabled"] = 1

    items = frappe.get_all(
        "Item",
        filters=item_filters,
        fields=["name", "item_name", "has_variants"],
        order_by="item_name asc",
    )
    item_rows = []
    for item in items:
        row = {"type": "item", "code": item.name, "label": item.item_name + (" (has variants)" if item.has_variants else "")}
        row.update(_setting_fields(settings_by_item.get(item.name)))
        item_rows.append(row)

    course_rows = []
    if frappe.db.exists("DocType", "LMS Course"):
        courses = frappe.get_all("LMS Course", fields=["name", "title"], order_by="title asc")
        for course in courses:
            row = {"type": "course", "code": course.name, "label": course.title}
            row.update(_setting_fields(settings_by_course.get(course.name)))
            course_rows.append(row)

    return {"items": item_rows, "courses": course_rows}


@frappe.whitelist()
def save_affiliate_commission_catalog(rows=None):
    """
    Franchisor-only - bulk save from the catalog list (ticked/enabled +
    an amount per row, no separate add-new form). Only ever writes a row
    that's either enabled or already has a real setting to update/turn
    off - a row left blank and unticked across the whole catalog (most
    of it, realistically) never creates an empty Affiliate Product
    Setting just because it was listed.
    """
    ensure_office_user()

    rows = coalesce_raw("rows", rows)
    if isinstance(rows, str):
        import json
        rows = json.loads(rows)

    updated = 0

    for row in rows or []:
        row_type = (row.get("type") or "").strip()
        code = (row.get("code") or "").strip()
        enabled = 1 if row.get("enabled") else 0
        commission_type = (row.get("commission_type") or "Percentage").strip()
        commission_percent = flt(row.get("commission_percent") or 0)
        commission_flat_amount = flt(row.get("commission_flat_amount") or 0)

        if row_type not in ("item", "course") or not code:
            continue

        has_amount = (commission_type == "Percentage" and commission_percent > 0) or (
            commission_type == "Flat Amount" and commission_flat_amount > 0
        )

        filters = {"item": code} if row_type == "item" else {"course": code}
        existing_name = frappe.db.exists(AFFILIATE_SETTING_DOCTYPE, filters)

        if not existing_name and not (enabled and has_amount):
            # Nothing on file for this one, and nothing meaningful was
            # entered - skip rather than create a disabled, zero-amount
            # row for every untouched item/course in the catalog.
            continue

        doc = frappe.get_doc(AFFILIATE_SETTING_DOCTYPE, existing_name) if existing_name else frappe.new_doc(AFFILIATE_SETTING_DOCTYPE)
        doc.item = code if row_type == "item" else None
        doc.course = code if row_type == "course" else None
        doc.commission_type = commission_type
        doc.commission_percent = commission_percent
        doc.commission_flat_amount = commission_flat_amount
        # Ticking it on with no amount set isn't meaningful (nothing to
        # pay out) - don't let the franchisor accidentally "enable" a
        # row that still earns nothing.
        doc.enabled = 1 if (enabled and has_amount) else 0
        doc.save(ignore_permissions=True)
        updated += 1

    frappe.db.commit()

    return {"ok": True, "updated": updated}


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


def record_affiliate_commission_for_invoice(
    invoice, affiliate_coach=None, affiliate_session_worker=None, client_full_name=None, client_email=None,
):
    """
    Called from webshop_purchase._fulfil_checkout_session right after a
    guest checkout is confirmed paid - never from anywhere an invoice
    might still be unpaid. One Affiliate Commission row per invoice
    line that matches an enabled Affiliate Product Setting (by the
    item directly, its item's variant template, or the LMS course it
    unlocks) - an invoice can earn commission on more than one line.

    Exactly one of affiliate_coach/affiliate_session_worker is ever
    set (see resolve_affiliate_earner) - both are accepted here rather
    than a single generic param so the two Affiliate Commission fields
    they end up on stay unambiguous.

    Best-effort: never allowed to raise, since this runs after the
    customer has already been charged and the order already recorded -
    a commission-recording problem must never look like a failed
    purchase.
    """
    if not affiliate_coach and not affiliate_session_worker:
        return

    try:
        _record_affiliate_commission_for_invoice(
            invoice, affiliate_coach, affiliate_session_worker, client_full_name, client_email,
        )
    except Exception:
        frappe.log_error(frappe.get_traceback(), f"Affiliate Commission Recording Failed - {invoice.name}")


def _record_affiliate_commission_for_invoice(invoice, affiliate_coach, affiliate_session_worker, client_full_name, client_email):
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
        commission.coach = affiliate_coach or None
        commission.session_worker = affiliate_session_worker or None
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
    """Franchisor-only - drives the Commissions table's filter dropdown.
    Session workers are appended under the same "name"/"coach_name"
    shape the dropdown already renders, so a franchisor can filter
    commissions down to one session worker without the dropdown (or
    get_affiliate_commissions below) needing a separate concept of
    "worker" vs "coach" options."""
    ensure_office_user()

    options = frappe.get_all("Coach", fields=["name", "coach_name"], order_by="coach_name asc")

    if has_field(SESSION_WORKER_DOCTYPE, "affiliate_code"):
        workers = frappe.get_all(SESSION_WORKER_DOCTYPE, fields=get_session_worker_fields())
        for worker in workers:
            options.append({
                "name": worker.name,
                "coach_name": (get_first_value(worker, SESSION_WORKER_LABEL_FIELDS) or worker.name) + " (Session Worker)",
            })
        options.sort(key=lambda row: (row["coach_name"] or row["name"]).lower())

    return options


def _commission_date_filters(from_date, to_date):
    if from_date and to_date:
        return {"creation": ["between", [from_date, to_date + " 23:59:59"]]}
    if from_date:
        return {"creation": [">=", from_date]}
    if to_date:
        return {"creation": ["<=", to_date + " 23:59:59"]}
    return {}


@frappe.whitelist()
def get_affiliate_coach_performance(from_date=None, to_date=None):
    """Franchisor-only - one row per coach/session worker who has ever
    had a click or a commission, for the Affiliates page's own "who's
    actually driving sales" summary (link clicks are otherwise
    invisible anywhere in the per-sale Commissions table below).
    from_date/to_date filter the sale figures only (sale_count/
    pending_total/paid_total) by when each commission was earned -
    click_count is always the earner's all-time total, since clicks
    are only ever kept as a running count, not individually dated.

    Session workers are unioned into the exact same "coach"/"coach_
    label" result keys as an additional set of rows (purely for
    display - affiliates.js's franchisor table needs no changes to
    show them) rather than a parallel field, since the frontend only
    ever renders one flat performance table either way.
    """
    ensure_office_user()

    from_date = coalesce_str("from_date", from_date)
    to_date = coalesce_str("to_date", to_date)

    date_filters = _commission_date_filters(from_date, to_date)

    coach_commission_filters = dict(date_filters)
    coach_commission_rows = frappe.get_all(
        AFFILIATE_COMMISSION_DOCTYPE,
        filters=coach_commission_filters,
        fields=["coach", "status", "commission_amount"],
    )
    by_coach = {}
    for row in coach_commission_rows:
        if not row.coach:
            continue
        bucket = by_coach.setdefault(row.coach, {"sale_count": 0, "pending_total": 0, "paid_total": 0})
        bucket["sale_count"] += 1
        if row.status == "Pending":
            bucket["pending_total"] += flt(row.commission_amount)
        else:
            bucket["paid_total"] += flt(row.commission_amount)

    worker_commission_rows = frappe.get_all(
        AFFILIATE_COMMISSION_DOCTYPE,
        filters=date_filters,
        fields=["session_worker", "status", "commission_amount"],
    )
    by_worker = {}
    for row in worker_commission_rows:
        if not row.session_worker:
            continue
        bucket = by_worker.setdefault(row.session_worker, {"sale_count": 0, "pending_total": 0, "paid_total": 0})
        bucket["sale_count"] += 1
        if row.status == "Pending":
            bucket["pending_total"] += flt(row.commission_amount)
        else:
            bucket["paid_total"] += flt(row.commission_amount)

    results = []

    coaches = frappe.get_all(
        "Coach", filters={"affiliate_code": ["is", "set"]},
        fields=["name", "coach_name", "affiliate_click_count"],
    )
    for coach in coaches:
        bucket = by_coach.get(coach.name, {"sale_count": 0, "pending_total": 0, "paid_total": 0})
        if not coach.affiliate_click_count and not bucket["sale_count"]:
            continue
        results.append({
            "coach": coach.name,
            "coach_label": coach.coach_name or coach.name,
            "is_session_worker": 0,
            "click_count": coach.affiliate_click_count or 0,
            "sale_count": bucket["sale_count"],
            "pending_total": bucket["pending_total"],
            "paid_total": bucket["paid_total"],
        })

    workers = []
    if has_field(SESSION_WORKER_DOCTYPE, "affiliate_code"):
        worker_fields = get_session_worker_fields()
        if has_field(SESSION_WORKER_DOCTYPE, "affiliate_click_count"):
            worker_fields = worker_fields + ["affiliate_click_count"]
        workers = frappe.get_all(
            SESSION_WORKER_DOCTYPE, filters={"affiliate_code": ["is", "set"]},
            fields=worker_fields,
        )
    for worker in workers:
        bucket = by_worker.get(worker.name, {"sale_count": 0, "pending_total": 0, "paid_total": 0})
        if not worker.affiliate_click_count and not bucket["sale_count"]:
            continue
        results.append({
            "coach": worker.name,
            "coach_label": get_first_value(worker, SESSION_WORKER_LABEL_FIELDS) or worker.name,
            "is_session_worker": 1,
            "click_count": worker.affiliate_click_count or 0,
            "sale_count": bucket["sale_count"],
            "pending_total": bucket["pending_total"],
            "paid_total": bucket["paid_total"],
        })

    results.sort(key=lambda r: r["click_count"], reverse=True)
    return results


def _get_affiliate_sale_items(commission_name, restrict_to_earner=None):
    if not commission_name or not frappe.db.exists(AFFILIATE_COMMISSION_DOCTYPE, commission_name):
        frappe.throw(_("Commission record not found."))

    commission = frappe.get_doc(AFFILIATE_COMMISSION_DOCTYPE, commission_name)

    if restrict_to_earner:
        doctype, name = restrict_to_earner
        owns = (commission.coach == name) if doctype == COACH_DOCTYPE else (commission.session_worker == name)
        if not owns:
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
    """Coach or Session Worker, and only for their own commission - same
    shape as get_affiliate_sale_items, for their dashboard's own
    drill-down."""
    earner = _current_earner()

    commission = coalesce_str("commission", commission)
    return _get_affiliate_sale_items(commission, restrict_to_earner=earner)


@frappe.whitelist()
def get_my_affiliate_commissions():
    """Coach or Session Worker - their own sale list (customer, price,
    commission), for their dashboard's own affiliate section."""
    doctype, name = _current_earner()

    rows = frappe.get_all(
        AFFILIATE_COMMISSION_DOCTYPE,
        filters=_earner_filter(doctype, name),
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
def get_affiliate_commissions(coach=None, status=None, from_date=None, to_date=None):
    """Franchisor-only. The "coach" param (kept under its original name
    for the frontend - see get_affiliate_coach_links' own docstring)
    may actually be a session worker's name - resolved the same way,
    against whichever doctype it really belongs to, since the filter
    dropdown that supplies it now lists both (get_coach_options_for_
    affiliates)."""
    ensure_office_user()

    coach = coalesce_str("coach", coach)
    status = coalesce_str("status", status)
    from_date = coalesce_str("from_date", from_date)
    to_date = coalesce_str("to_date", to_date)

    filters = _commission_date_filters(from_date, to_date)
    if coach:
        if frappe.db.exists(SESSION_WORKER_DOCTYPE, coach) and not frappe.db.exists(COACH_DOCTYPE, coach):
            filters["session_worker"] = coach
        else:
            filters["coach"] = coach
    if status:
        filters["status"] = status

    rows = frappe.get_all(
        AFFILIATE_COMMISSION_DOCTYPE,
        filters=filters,
        fields=[
            "name", "coach", "session_worker", "item", "course", "sales_invoice", "sale_amount",
            "commission_rate_snapshot", "commission_amount", "client_full_name",
            "client_email", "status", "paid_on", "creation",
        ],
        order_by="coach asc, session_worker asc, creation desc",
    )

    for row in rows:
        row["coach_label"] = _earner_label(coach=row.coach, session_worker=row.session_worker)
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
