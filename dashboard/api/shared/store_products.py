"""
Store Manager's own product/stock management (see permissions.py's
Store Manager dashboard type) - a franchisor can also use every
endpoint here, but a Store Manager can't reach anything outside it.

Deliberately separate from item_access.py, which stays exactly what it
already was: the franchisor-only grid for granting individual coaches
invoicing access to an Item. A store product still needs the same
underlying Item Default (company/warehouse/price list) + Item Price
rows webshop_purchase.py's checkout already reads prices from, so
those two pieces are reused directly rather than re-implemented here.
"""

import contextlib
import itertools
import re

import frappe
from frappe import _

from dashboard.api.shared.permissions import ensure_logged_in, is_office_user, is_store_manager
from dashboard.api.shared.item_access import DEFAULT_PRICE_LIST, COACH_ONLY_PRICE_LIST, BRAND_FIELDS, _get_default_warehouse_for_company
from dashboard.dashboard.doctype.webshop_payment_settings.webshop_payment_settings import get_settings

BRAND_FIELDNAMES = list(BRAND_FIELDS.keys())


def _ensure_store_access():
    ensure_logged_in()

    if not (is_office_user() or is_store_manager()):
        frappe.throw(_("You are not allowed to manage the store."), frappe.PermissionError)


@contextlib.contextmanager
def _as_administrator():
    """
    _ensure_store_access() has already confirmed the caller is allowed
    to manage the store - this covers what ignore_permissions=True on
    this endpoint's own Item save doesn't reach: the stock Frappe
    Webshop app hooks Item's save to auto-sync a "Website Item" record,
    and that nested insert checks permissions itself rather than
    inheriting this call's ignore_permissions flag, so a Store Manager
    (a limited Website User, not an Item/Website Manager) otherwise gets
    a bare PermissionError from deep inside someone else's app.

    Deliberately uses frappe.flags.ignore_permissions rather than
    frappe.set_user("Administrator") - set_user() also reassigns
    frappe.session.sid to the given username, and restoring only
    session.user afterward (not session.sid) leaves that corrupted for
    the rest of the request, which was logging Rachel straight back out
    after every save. This flag never touches the session at all.
    """
    previous = frappe.flags.ignore_permissions
    frappe.flags.ignore_permissions = True
    try:
        yield
    finally:
        frappe.flags.ignore_permissions = previous


def _to_bool(value):
    return str(value).strip().lower() in ("1", "true", "yes", "on")


def _to_int(value, default=0):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _to_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _item_meta_has_field(fieldname):
    return frappe.get_meta("Item").has_field(fieldname)


def _parse_brands(brands):
    if not brands:
        return {}
    if isinstance(brands, dict):
        return brands
    try:
        return frappe.parse_json(brands) or {}
    except Exception:
        return {}


def _parse_json_list(value):
    if not value:
        return []
    if isinstance(value, list):
        return value
    try:
        return frappe.parse_json(value) or []
    except Exception:
        return []


def _slugify(value):
    return "".join(ch if ch.isalnum() else "-" for ch in str(value).strip().lower()).strip("-")


def _apply_gallery_images(item, gallery_images):
    """
    gallery_images: list of file URLs (already-uploaded, via
    uploadFile() same as the main image) - replaces the item's whole
    Additional Photos table with this set. None-vs-[] matters: None means
    "not sent, leave alone" (e.g. a variant save that never touches
    gallery at all), [] means "clear it".
    """
    if gallery_images is None or not _item_meta_has_field("custom_gallery"):
        return

    item.set("custom_gallery", [])
    for url in gallery_images:
        url = (url or "").strip()
        if url:
            item.append("custom_gallery", {"image": url})


def _sync_gallery_images_raw(item_code, gallery_images):
    """
    Same replace-the-whole-set behaviour as _apply_gallery_images(), but
    writes the child rows directly (delete then re-insert) instead of
    going through item.save() - see update_store_product()'s own
    docstring for why an already-existing Item is updated this way now.
    """
    if gallery_images is None or not _item_meta_has_field("custom_gallery"):
        return

    frappe.db.sql(
        "DELETE FROM `tabItem Gallery Image` WHERE parent=%s AND parenttype=%s",
        (item_code, "Item"),
    )

    idx = 0
    for url in gallery_images:
        url = (url or "").strip()
        if not url:
            continue

        idx += 1
        frappe.get_doc({
            "doctype": "Item Gallery Image",
            "parent": item_code,
            "parenttype": "Item",
            "parentfield": "custom_gallery",
            "idx": idx,
            "image": url,
        }).insert(ignore_permissions=True)


def _apply_personalization(item, enabled, label):
    """enabled/label are None when the caller never sent them (e.g. a
    variant row save that doesn't touch this) - left alone in that case."""
    if enabled is not None and _item_meta_has_field("custom_personalization_enabled"):
        item.custom_personalization_enabled = 1 if _to_bool(enabled) else 0

    if label is not None and _item_meta_has_field("custom_personalization_label"):
        item.custom_personalization_label = label.strip()


def _apply_logo_choice(item, enabled):
    if enabled is not None and _item_meta_has_field("custom_logo_choice_enabled"):
        item.custom_logo_choice_enabled = 1 if _to_bool(enabled) else 0


@frappe.whitelist()
def save_logo_choice_options(kid_logo=None, teen_logo=None, people_logo=None, school_logo=None):
    """Uploads/replaces the four brand logo images shown on any product
    with "Let Buyer Choose a Sleeve/Leg Logo" ticked - one place, reused
    by every such product (see get_logo_choice_options in
    webshop_purchase.py, which this Store dashboard panel also reads
    from to show what's currently uploaded)."""
    _ensure_store_access()

    # Local import - webshop_purchase.py imports store_coupons.py, which
    # imports this module, so a module-level import back the other way
    # here is a circular import (confirmed live: it broke every /buy
    # page with "cannot import name 'LOGO_CHOICE_DOCTYPE' from partially
    # initialized module"). By the time this function actually runs,
    # both modules are fully loaded, so the import is safe here.
    from dashboard.api.shared.webshop_purchase import LOGO_CHOICE_DOCTYPE, LOGO_CHOICES

    if not frappe.db.exists("DocType", LOGO_CHOICE_DOCTYPE):
        frappe.throw(_("Store Logo Choice isn't set up yet - run bench migrate."))

    updates = {}
    values = {"kid_logo": kid_logo, "teen_logo": teen_logo, "people_logo": people_logo, "school_logo": school_logo}

    for choice in LOGO_CHOICES:
        value = values.get(choice["fieldname"])
        if value is not None:
            updates[choice["fieldname"]] = value.strip()

    for fieldname, value in updates.items():
        frappe.db.set_single_value(LOGO_CHOICE_DOCTYPE, fieldname, value)

    frappe.db.commit()

    return {"ok": 1}


def _store_company():
    settings = get_settings()

    if not settings.company:
        frappe.throw(_("Set a Company on Webshop Payment Settings before managing store products."))

    return settings.company


def _ensure_item_default_row(item, company):
    """
    custom_show_on_site (on this row, not on Item) is the flag
    webshop_purchase.py's checkout actually gates a purchase on - a
    different, older flag than Item.custom_store_enabled (which only
    controls showing up in a store *listing*, see get_store_items() in
    resilient_domains). A store product needs both, or it lists fine
    but "isn't available for online purchase" the moment someone tries
    to actually buy it - also backfills it onto a row created before
    this was noticed.

    Same story for default_price_list: _set_item_price() always prices
    an item on DEFAULT_PRICE_LIST, but if this row already existed
    before the item became a store product (e.g. adopting a
    pre-existing, non-store Item - see create_store_product), it may
    point at a different price list or none at all. resilient_domains'
    get_store_items() looks the price up through *this row's*
    default_price_list, not the constant directly - a mismatch here
    means it finds no price, and the product silently never appears in
    the store listing at all, with no error anywhere to explain why.
    """
    has_show_on_site_field = frappe.get_meta("Item Default").has_field("custom_show_on_site")

    for row in item.get("item_defaults") or []:
        if row.get("company") == company:
            if has_show_on_site_field and not row.get("custom_show_on_site"):
                row.custom_show_on_site = 1
            if row.get("default_price_list") != DEFAULT_PRICE_LIST:
                row.default_price_list = DEFAULT_PRICE_LIST
            return row

    warehouse = _get_default_warehouse_for_company(company)

    if not warehouse:
        frappe.throw(_("No default warehouse found for {0} - please set one up first.").format(company))

    new_row = item.append("item_defaults", {
        "company": company,
        "default_warehouse": warehouse,
        "default_price_list": DEFAULT_PRICE_LIST,
    })

    if has_show_on_site_field:
        new_row.custom_show_on_site = 1

    return new_row


def _sync_item_default_row_raw(item_code, company):
    """Same job as _ensure_item_default_row(), but for an Item that
    already exists in the database - reads/writes the Item Default row
    directly rather than through the parent Item doc, see
    update_store_product()'s own docstring for why."""
    has_show_on_site_field = frappe.get_meta("Item Default").has_field("custom_show_on_site")

    existing_name = frappe.db.get_value(
        "Item Default", {"parent": item_code, "parenttype": "Item", "company": company}, "name"
    )

    if existing_name:
        updates = {"default_price_list": DEFAULT_PRICE_LIST}
        if has_show_on_site_field:
            updates["custom_show_on_site"] = 1
        frappe.db.set_value("Item Default", existing_name, updates)
        return

    warehouse = _get_default_warehouse_for_company(company)

    if not warehouse:
        frappe.throw(_("No default warehouse found for {0} - please set one up first.").format(company))

    next_idx = frappe.db.count("Item Default", {"parent": item_code, "parenttype": "Item"}) + 1

    row = frappe.get_doc({
        "doctype": "Item Default",
        "parent": item_code,
        "parenttype": "Item",
        "parentfield": "item_defaults",
        "idx": next_idx,
        "company": company,
        "default_warehouse": warehouse,
        "default_price_list": DEFAULT_PRICE_LIST,
    })

    if has_show_on_site_field:
        row.custom_show_on_site = 1

    row.insert(ignore_permissions=True)


def auto_setup_store_item_for_webshop(doc, method=None):
    """Item.on_update hook - mirrors what create_store_product/
    update_store_product/add_product_variant already do automatically
    through the guided Store dashboard forms (an Item Default row for
    the webshop's configured Company, priced on DEFAULT_PRICE_LIST,
    with custom_show_on_site ticked - see _ensure_item_default_row's
    own docstring on why a mismatch here means the product silently
    never appears in either store listing) for a store item touched
    directly in Desk instead, e.g. a variant or Item created/edited by
    hand rather than through the Store dashboard. Only ever adds/repairs
    that plumbing, never a price - Ashley still sets that herself,
    through the store form or a direct Item Price/custom_coach_price.
    """
    if not doc.get("custom_store_enabled"):
        return

    try:
        company = _store_company()
    except Exception:
        return

    try:
        _sync_item_default_row_raw(doc.name, company)
    except Exception:
        frappe.log_error(frappe.get_traceback(), f"Store Item Auto-Setup Failed - {doc.name}")


@frappe.whitelist()
def backfill_store_item_default_rows():
    """Franchisor/Store Manager-triggerable, safe to re-run any time -
    the same one-off fix dashboard.patches.backfill_store_item_default_rows
    runs once on deploy, for a store item that was missing its Item
    Default row entirely (not just an existing row with the wrong
    fields - see that patch's own docstring) at the time this deploy
    went out, e.g. one added directly in Desk before
    auto_setup_store_item_for_webshop existed to catch it.
    """
    _ensure_store_access()
    return _backfill_store_item_default_rows()


def _backfill_store_item_default_rows():
    if not frappe.get_meta("Item").has_field("custom_store_enabled"):
        return {"items_checked": 0}

    try:
        company = _store_company()
    except Exception:
        return {"items_checked": 0}

    store_item_codes = frappe.get_all("Item", filters={"custom_store_enabled": 1}, pluck="name")

    if not store_item_codes:
        return {"items_checked": 0}

    variant_codes = frappe.get_all(
        "Item", filters={"variant_of": ["in", store_item_codes]}, pluck="name"
    )

    all_item_codes = set(store_item_codes) | set(variant_codes)

    for item_code in all_item_codes:
        try:
            _sync_item_default_row_raw(item_code, company)
        except Exception:
            frappe.log_error(frappe.get_traceback(), f"Backfill Store Item Default Row Failed - {item_code}")

    frappe.db.commit()

    return {"items_checked": len(all_item_codes)}


def _get_item_price_row(item_code, price_list):
    return frappe.db.get_value(
        "Item Price",
        {"item_code": item_code, "price_list": price_list, "selling": 1},
        ["name", "price_list_rate"],
        as_dict=True,
    )


def _set_item_price(item_code, price_list, rate):
    existing = _get_item_price_row(item_code, price_list)

    if existing:
        frappe.db.set_value("Item Price", existing.name, "price_list_rate", rate)
        return existing.name

    price_doc = frappe.new_doc("Item Price")
    price_doc.item_code = item_code
    price_doc.price_list = price_list
    price_doc.selling = 1
    price_doc.price_list_rate = rate
    price_doc.currency = "GBP"
    price_doc.insert(ignore_permissions=True)

    return price_doc.name


def _clear_item_price(item_code, price_list):
    """Removes an Item Price row entirely (rather than leaving a stale
    0/blank rate behind) - used to un-set a coach price back to "no
    override, same as everyone else"."""
    existing = _get_item_price_row(item_code, price_list)
    if existing:
        frappe.delete_doc("Item Price", existing.name, ignore_permissions=True, force=True)


def _set_coach_price(item_code, coach_price):
    """coach_price is optional - blank/None clears any existing coach-
    only price for this item rather than setting a 0 rate, so it falls
    back to the normal price everyone else pays.

    A variant template (has_variants=1) can never have its own Item
    Price row at all - core Frappe validation rejects it outright
    ("Item Price cannot be created for the template item") - so a
    template's one flat Coach Price lives in its own custom_coach_price
    field on Item instead. A plain product (or an actual variant Item,
    which is never given its own coach price - see store_products.py's
    module notes on this) still uses the normal Item Price/price-list
    mechanism, since only a template is restricted this way."""
    if coach_price is None:
        return

    coach_price = (str(coach_price)).strip()
    is_template = bool(frappe.db.get_value("Item", item_code, "has_variants"))

    if not coach_price:
        if is_template:
            # custom_coach_price is a Currency field - like every
            # Frappe Currency/Float column, its DB column is NOT NULL
            # DEFAULT 0, so writing None here throws a raw MySQL
            # IntegrityError ("Column 'custom_coach_price' cannot be
            # null") rather than clearing it - this was the actual
            # cause of every "with variations" product silently ending
            # up with zero variants: create_variant_store_product()
            # calls this right after inserting the template, before the
            # variant-creation loop even starts, so an empty (the
            # default) Coach Price field crashed the save immediately
            # every single time. 0 means the same "no override" as None
            # does everywhere this field is read (_get_coach_price
            # already treats it as falsy via `or None`), so it's a safe,
            # equivalent value to write instead.
            frappe.db.set_value("Item", item_code, "custom_coach_price", 0)
        else:
            _clear_item_price(item_code, COACH_ONLY_PRICE_LIST)
        return

    if is_template:
        frappe.db.set_value("Item", item_code, "custom_coach_price", _to_float(coach_price))
    else:
        _set_item_price(item_code, COACH_ONLY_PRICE_LIST, _to_float(coach_price))


def _get_coach_price(item_code):
    if frappe.db.get_value("Item", item_code, "has_variants"):
        return frappe.db.get_value("Item", item_code, "custom_coach_price") or None

    row = _get_item_price_row(item_code, COACH_ONLY_PRICE_LIST)
    return row.price_list_rate if row else None


def _root_item_group():
    root = frappe.db.get_value(
        "Item Group", {"is_group": 1, "parent_item_group": ["in", ["", None]]}, "name"
    )
    return root or "All Item Groups"


def _ensure_item_group(item_group_name):
    """
    The product form's own Item Group field is free text (with existing
    groups only offered as suggestions, per get_item_groups() below) -
    typing a brand new one (or even relying on the "Products" fallback,
    if that group was never actually created) used to fail outright with
    a LinkValidationError, since Item Group is a real Link field. Creates
    it on the fly instead, same on-demand pattern as
    email_groups.ensure_email_group().
    """
    item_group_name = (item_group_name or "").strip()

    if not item_group_name or frappe.db.exists("Item Group", item_group_name):
        return item_group_name

    doc = frappe.new_doc("Item Group")
    doc.item_group_name = item_group_name
    doc.parent_item_group = _root_item_group()
    doc.is_group = 0
    doc.insert(ignore_permissions=True)

    return doc.name


@frappe.whitelist()
def get_item_groups():
    _ensure_store_access()

    return frappe.get_all(
        "Item Group",
        filters={"is_group": 0},
        pluck="name",
        order_by="name asc",
        limit_page_length=200,
    )


@frappe.whitelist()
def get_lms_courses():
    """
    Every course, not just published ones - a Restricted or unpublished
    course is exactly the kind of thing meant to be granted by a specific
    purchase rather than open self-signup, so it still needs to show up
    here to be picked as what a product unlocks.
    """
    _ensure_store_access()

    if not frappe.db.exists("DocType", "LMS Course"):
        return []

    return frappe.get_all(
        "LMS Course",
        fields=["name", "title"],
        order_by="title asc",
        limit_page_length=500,
    )


def _unique_abbr(value, used_abbrs):
    """A naive value[:5] truncation collides constantly for values that
    share a common prefix (e.g. "Size 6-7" / "Size 7-8" both truncate to
    "SIZE "), which Item Attribute Value rejects as a duplicate
    abbreviation within the same attribute - build a real one instead:
    strip to alphanumerics, and disambiguate with a counter suffix on
    collision rather than ever reusing one already taken."""
    base = re.sub(r"[^A-Za-z0-9]+", "", value).upper()[:8] or "VAL"
    abbr = base
    counter = 1

    while abbr in used_abbrs:
        counter += 1
        abbr = f"{base}{counter}"

    used_abbrs.add(abbr)
    return abbr


def _ensure_item_attribute(attribute_name, values):
    """Creates the Item Attribute if missing, and adds any new values to
    it - existing values are never removed, since other items/variants
    may already depend on them."""
    attribute_name = (attribute_name or "").strip()

    if not attribute_name:
        return

    if frappe.db.exists("Item Attribute", attribute_name):
        doc = frappe.get_doc("Item Attribute", attribute_name)
    else:
        doc = frappe.new_doc("Item Attribute")
        doc.attribute_name = attribute_name

    existing_values = {row.attribute_value for row in doc.get("item_attribute_values") or []}
    value_meta_has_abbr = frappe.get_meta("Item Attribute Value").has_field("abbr") if frappe.db.exists("DocType", "Item Attribute Value") else False
    used_abbrs = {row.abbr for row in doc.get("item_attribute_values") or [] if row.get("abbr")}

    for value in values:
        value = (value or "").strip()
        if not value or value in existing_values:
            continue

        new_row = {"attribute_value": value}
        if value_meta_has_abbr:
            new_row["abbr"] = _unique_abbr(value, used_abbrs)

        doc.append("item_attribute_values", new_row)
        existing_values.add(value)

    if doc.is_new():
        doc.insert(ignore_permissions=True)
    else:
        doc.save(ignore_permissions=True)


@frappe.whitelist()
def get_product_gallery(item_code=None):
    """
    A separate, lightweight lookup rather than bundling this into
    get_store_products()'s list - that list is fetched via frappe.get_all
    (no child tables) for every product at once, and gallery images are
    only ever needed when actually opening one product to edit it.
    """
    _ensure_store_access()

    item_code = (item_code or "").strip()

    if not item_code or not frappe.db.exists("Item", item_code) or not _item_meta_has_field("custom_gallery"):
        return []

    # ignore_permissions=True - "Item Gallery Image" is a plain child
    # table with no permission rows of its own (see its doctype json);
    # queried standalone like this (rather than read off an already-
    # loaded parent Item doc) it has no role to inherit from, so a Store
    # Manager (who has no direct role permission on Item either - see
    # _as_administrator() above) was getting a bare PermissionError just
    # from opening the edit-product modal, before ever trying to save.
    rows = frappe.get_all(
        "Item Gallery Image",
        filters={"parent": item_code, "parenttype": "Item"},
        fields=["image"],
        order_by="idx asc",
        limit_page_length=50,
        ignore_permissions=True,
    )

    return [row.image for row in rows if row.image]


@frappe.whitelist()
def find_empty_variant_templates():
    """A "with variations" product (has_variants=1) is only ever priced
    and listed via its actual variant Items underneath it (see
    resilient_domains' _variant_template_summary) - the template itself
    can never hold a price of its own (only custom_coach_price, a flat
    coach-only override). If a save throws partway through creating
    those variants (e.g. the IntegrityError seen live on "The Resilient
    Kid Personalised Coach Hoodie"), the template can be left behind
    with zero variants under it - custom_store_enabled=1, seemingly
    fully configured, "Enabled" in Desk, yet permanently invisible on
    every storefront (nothing to price it by), with nothing anywhere to
    explain why. Finds every such orphaned template so they can be
    fixed (re-save with variations from the Store dashboard) rather
    than hunted down one at a time.
    """
    _ensure_store_access()

    item_meta = frappe.get_meta("Item")
    if not item_meta.has_field("custom_store_enabled"):
        return []

    templates = frappe.get_all(
        "Item",
        filters={"custom_store_enabled": 1, "has_variants": 1, "disabled": 0},
        fields=["name", "item_name", "custom_item_visibility"],
        order_by="item_name asc",
    )

    if not templates:
        return []

    template_codes = [t.name for t in templates]

    variant_counts = {}
    for row in frappe.get_all(
        "Item", filters={"variant_of": ["in", template_codes]}, fields=["variant_of"], pluck="variant_of"
    ):
        variant_counts[row] = variant_counts.get(row, 0) + 1

    return [
        {
            "item_code": t.name,
            "item_name": t.item_name,
            "visibility": t.custom_item_visibility or "Everyone",
        }
        for t in templates
        if not variant_counts.get(t.name)
    ]


@frappe.whitelist()
def get_store_products(search=None):
    _ensure_store_access()

    item_meta = frappe.get_meta("Item")
    brand_fieldnames = [f for f in BRAND_FIELDNAMES if item_meta.has_field(f)]

    filters = {"custom_store_enabled": 1}
    search = (search or "").strip()
    if search:
        filters["item_name"] = ["like", f"%{search}%"]

    extra_fieldnames = [
        f for f in [
            "custom_digital_file", "custom_unlocks_lms_course", "custom_short_description", "custom_sku",
            "custom_personalization_enabled", "custom_personalization_label", "custom_logo_choice_enabled",
            "custom_item_visibility", "custom_coach_price",
        ]
        if item_meta.has_field(f)
    ]

    items = frappe.get_all(
        "Item",
        filters=filters,
        fields=(
            ["name", "item_name", "description", "item_group", "image", "disabled",
             "custom_stock_qty", "custom_unlimited_stock", "has_variants", "variant_of"]
            + brand_fieldnames + extra_fieldnames
        ),
        order_by="item_name asc",
        limit_page_length=0,
    )

    # A variant (e.g. one specific size) has custom_store_enabled set the
    # same as its template, so it'd otherwise show up here as its own
    # separate row - only the template belongs in this list, its variants
    # are managed through get_product_variants() instead.
    items = [item for item in items if not item.variant_of]

    prices = {}
    if items:
        price_rows = frappe.get_all(
            "Item Price",
            filters={
                "price_list": DEFAULT_PRICE_LIST,
                "selling": 1,
                "item_code": ["in", [i.name for i in items]],
            },
            fields=["item_code", "price_list_rate"],
        )
        prices = {row.item_code: row.price_list_rate for row in price_rows}

    # A plain product's Coach Price is an Item Price row (queried below,
    # same as the normal price); a variant template can never hold one at
    # all (Frappe rejects it outright) so its own flat Coach Price lives
    # in custom_coach_price on the Item itself instead - see
    # _set_coach_price/_get_coach_price.
    coach_prices = {
        item.name: item.get("custom_coach_price")
        for item in items
        if item.has_variants and item.get("custom_coach_price")
    }

    non_template_names = [i.name for i in items if not i.has_variants]
    if non_template_names:
        coach_price_rows = frappe.get_all(
            "Item Price",
            filters={
                "price_list": COACH_ONLY_PRICE_LIST,
                "selling": 1,
                "item_code": ["in", non_template_names],
            },
            fields=["item_code", "price_list_rate"],
        )
        coach_prices.update({row.item_code: row.price_list_rate for row in coach_price_rows})

    return [
        {
            "name": item.name,
            "item_name": item.item_name or item.name,
            "description": item.description or "",
            "short_description": item.get("custom_short_description") or "",
            "item_group": item.item_group or "",
            "image": item.image or "",
            "disabled": bool(item.disabled),
            "has_variants": bool(item.has_variants),
            "stock_qty": item.custom_stock_qty or 0,
            "unlimited_stock": bool(item.custom_unlimited_stock),
            "price": prices.get(item.name) or 0,
            "coach_price": coach_prices.get(item.name) or "",
            "visibility": item.get("custom_item_visibility") or "Everyone",
            "brands": {fieldname: bool(item.get(fieldname)) for fieldname in brand_fieldnames},
            "digital_file": item.get("custom_digital_file") or "",
            "unlocks_course": item.get("custom_unlocks_lms_course") or "",
            "sku": item.get("custom_sku") or "",
            "personalization_enabled": bool(item.get("custom_personalization_enabled")),
            "personalization_label": item.get("custom_personalization_label") or "",
            "logo_choice_enabled": bool(item.get("custom_logo_choice_enabled")),
        }
        for item in items
    ]


@frappe.whitelist()
def create_store_product(item_name=None, description=None, short_description=None, item_group=None, price=None,
                          stock_qty=None, unlimited_stock=None, brands=None, image=None,
                          digital_file=None, unlocks_course=None, sku=None, gallery_images=None,
                          personalization_enabled=None, personalization_label=None, logo_choice_enabled=None,
                          visibility=None, coach_price=None):
    """
    An Item with this exact name can already exist without being a store
    product yet - e.g. something tracked elsewhere in the system
    (coaching stock, an old catalog entry) that Rachel now also wants to
    sell online. Adopt it into the store rather than blocking with a
    dead-end "already exists" error; only a name already used by another
    *store* product is a genuine duplicate.

    Adopting an existing Item writes straight to the database rather
    than loading it as a Document and calling .save() - same reasoning
    as update_store_product()'s own docstring (a nested Webshop app hook
    on Item's on_update doesn't respect frappe.flags.ignore_permissions
    for a Store Manager). A genuinely brand-new Item still goes through
    item.insert() below, which hasn't shown this problem.
    """
    _ensure_store_access()

    item_name = (item_name or "").strip()

    if not item_name:
        frappe.throw(_("Product name is required."))

    company = _store_company()
    item_meta = frappe.get_meta("Item")

    existing_item_code = frappe.db.get_value("Item", {"item_name": item_name}, "name")

    if existing_item_code:
        if frappe.db.get_value("Item", existing_item_code, "custom_store_enabled"):
            frappe.throw(_("A product named {0} already exists.").format(item_name))

        existing = frappe.db.get_value("Item", existing_item_code, ["item_group", "description"], as_dict=True) or {}

        updates = {
            "item_group": _ensure_item_group((item_group or "").strip() or existing.get("item_group") or "Products"),
            "description": description or existing.get("description") or "",
            "disabled": 0,
            "custom_store_enabled": 1,
            "custom_unlimited_stock": 1 if _to_bool(unlimited_stock) else 0,
            "custom_stock_qty": _to_int(stock_qty),
        }

        if short_description is not None and item_meta.has_field("custom_short_description"):
            updates["custom_short_description"] = short_description.strip()[:200]

        if sku is not None and item_meta.has_field("custom_sku"):
            updates["custom_sku"] = sku.strip()

        if personalization_enabled is not None and item_meta.has_field("custom_personalization_enabled"):
            updates["custom_personalization_enabled"] = 1 if _to_bool(personalization_enabled) else 0

        if personalization_label is not None and item_meta.has_field("custom_personalization_label"):
            updates["custom_personalization_label"] = personalization_label.strip()

        if logo_choice_enabled is not None and item_meta.has_field("custom_logo_choice_enabled"):
            updates["custom_logo_choice_enabled"] = 1 if _to_bool(logo_choice_enabled) else 0

        if visibility is not None and item_meta.has_field("custom_item_visibility"):
            updates["custom_item_visibility"] = visibility

        if image:
            updates["image"] = image

        if digital_file and item_meta.has_field("custom_digital_file"):
            updates["custom_digital_file"] = digital_file

        if unlocks_course and item_meta.has_field("custom_unlocks_lms_course"):
            updates["custom_unlocks_lms_course"] = unlocks_course

        parsed_brands = _parse_brands(brands)
        for fieldname in BRAND_FIELDNAMES:
            if item_meta.has_field(fieldname):
                updates[fieldname] = 1 if parsed_brands.get(fieldname) else 0

        frappe.db.set_value("Item", existing_item_code, updates)
        _sync_gallery_images_raw(existing_item_code, _parse_json_list(gallery_images) if gallery_images is not None else None)
        _sync_item_default_row_raw(existing_item_code, company)

        if price is not None:
            _set_item_price(existing_item_code, DEFAULT_PRICE_LIST, _to_float(price))

        _set_coach_price(existing_item_code, coach_price)

        frappe.db.commit()

        return {"ok": 1, "item_code": existing_item_code}

    item = frappe.new_doc("Item")
    item.item_code = item_name
    item.item_name = item_name
    item.stock_uom = item.stock_uom or "Nos"
    item.is_stock_item = 0
    item.item_group = _ensure_item_group((item_group or "").strip() or "Products")
    item.description = description or ""

    if short_description is not None and _item_meta_has_field("custom_short_description"):
        item.custom_short_description = short_description.strip()[:200]

    if sku is not None and _item_meta_has_field("custom_sku"):
        item.custom_sku = sku.strip()

    _apply_personalization(item, personalization_enabled, personalization_label)
    _apply_logo_choice(item, logo_choice_enabled)

    item.disabled = 0
    item.custom_store_enabled = 1
    item.custom_unlimited_stock = 1 if _to_bool(unlimited_stock) else 0
    item.custom_stock_qty = _to_int(stock_qty)

    if image:
        item.image = image

    _apply_gallery_images(item, _parse_json_list(gallery_images) if gallery_images is not None else None)

    if digital_file and _item_meta_has_field("custom_digital_file"):
        item.custom_digital_file = digital_file

    if unlocks_course and _item_meta_has_field("custom_unlocks_lms_course"):
        item.custom_unlocks_lms_course = unlocks_course

    parsed_brands = _parse_brands(brands)
    for fieldname in BRAND_FIELDNAMES:
        if _item_meta_has_field(fieldname):
            item.set(fieldname, 1 if parsed_brands.get(fieldname) else 0)

    if visibility is not None and _item_meta_has_field("custom_item_visibility"):
        item.custom_item_visibility = visibility

    _ensure_item_default_row(item, company)

    with _as_administrator():
        item.insert(ignore_permissions=True)

        if price is not None:
            _set_item_price(item.name, DEFAULT_PRICE_LIST, _to_float(price))

        _set_coach_price(item.name, coach_price)

    frappe.db.commit()

    return {"ok": 1, "item_code": item.name}


@frappe.whitelist()
def update_store_product(item_code=None, item_name=None, description=None, short_description=None,
                          item_group=None, price=None, stock_qty=None, unlimited_stock=None, brands=None,
                          disabled=None, image=None, digital_file=None, unlocks_course=None, sku=None,
                          gallery_images=None, personalization_enabled=None, personalization_label=None,
                          logo_choice_enabled=None, visibility=None, coach_price=None):
    """
    Writes straight to the database (frappe.db.set_value + direct child-
    row management) rather than loading the Item as a Document and
    calling .save() - confirmed live that even with
    frappe.flags.ignore_permissions set (_as_administrator() above),
    saving an existing Item still hit "does not have doctype access...
    for document Item" for a Store Manager, coming from deep inside a
    nested hook (the stock Webshop app's own Website Item auto-sync on
    Item's on_update) that doesn't respect that flag. Bypassing
    Document.save() entirely for an UPDATE sidesteps that hook
    altogether - matches the same pattern already used successfully by
    update_variant()/update_store_stock()/stock_take_update() below.
    create_store_product()'s brand-new-Item path still uses insert()
    (there's no way to "raw write" a document that doesn't exist yet),
    which hasn't shown this problem.
    """
    _ensure_store_access()

    item_code = (item_code or "").strip()

    if not item_code or not frappe.db.exists("Item", item_code):
        frappe.throw(_("Product not found."))

    item_meta = frappe.get_meta("Item")
    updates = {}

    if item_name is not None and item_name.strip():
        updates["item_name"] = item_name.strip()

    if description is not None:
        updates["description"] = description

    if short_description is not None and item_meta.has_field("custom_short_description"):
        updates["custom_short_description"] = short_description.strip()[:200]

    if sku is not None and item_meta.has_field("custom_sku"):
        updates["custom_sku"] = sku.strip()

    if personalization_enabled is not None and item_meta.has_field("custom_personalization_enabled"):
        updates["custom_personalization_enabled"] = 1 if _to_bool(personalization_enabled) else 0

    if personalization_label is not None and item_meta.has_field("custom_personalization_label"):
        updates["custom_personalization_label"] = personalization_label.strip()

    if logo_choice_enabled is not None and item_meta.has_field("custom_logo_choice_enabled"):
        updates["custom_logo_choice_enabled"] = 1 if _to_bool(logo_choice_enabled) else 0

    if item_group is not None and item_group.strip():
        updates["item_group"] = _ensure_item_group(item_group.strip())

    if stock_qty is not None:
        updates["custom_stock_qty"] = _to_int(stock_qty)

    if unlimited_stock is not None:
        updates["custom_unlimited_stock"] = 1 if _to_bool(unlimited_stock) else 0

    if disabled is not None:
        updates["disabled"] = 1 if _to_bool(disabled) else 0

    if image is not None:
        updates["image"] = image

    if digital_file is not None and item_meta.has_field("custom_digital_file"):
        updates["custom_digital_file"] = digital_file

    if unlocks_course is not None and item_meta.has_field("custom_unlocks_lms_course"):
        updates["custom_unlocks_lms_course"] = unlocks_course

    parsed_brands = _parse_brands(brands)
    for fieldname in BRAND_FIELDNAMES:
        if fieldname in parsed_brands and item_meta.has_field(fieldname):
            updates[fieldname] = 1 if parsed_brands.get(fieldname) else 0

    if visibility is not None and item_meta.has_field("custom_item_visibility"):
        updates["custom_item_visibility"] = visibility

    if updates:
        frappe.db.set_value("Item", item_code, updates)

    # Archiving (or unarchiving) a variant template has to reach every
    # variant underneath it too - each one carries its own disabled flag,
    # separately checked at checkout, so archiving only the template
    # would leave every existing size/colour still individually buyable
    # via its own item_code.
    if disabled is not None:
        variant_codes = frappe.get_all("Item", filters={"variant_of": item_code}, pluck="name")
        if variant_codes:
            for variant_code in variant_codes:
                frappe.db.set_value("Item", variant_code, "disabled", updates["disabled"])

    _sync_gallery_images_raw(item_code, _parse_json_list(gallery_images) if gallery_images is not None else None)

    company = _store_company()
    _sync_item_default_row_raw(item_code, company)

    if price is not None:
        _set_item_price(item_code, DEFAULT_PRICE_LIST, _to_float(price))

    _set_coach_price(item_code, coach_price)

    frappe.db.commit()

    return {"ok": 1}


@frappe.whitelist()
def update_store_stock(item_code=None, stock_qty=None, unlimited_stock=None):
    """Fast path for just adjusting stock, without re-saving the whole Item."""
    _ensure_store_access()

    item_code = (item_code or "").strip()

    if not item_code or not frappe.db.exists("Item", item_code):
        frappe.throw(_("Product not found."))

    if unlimited_stock is not None:
        frappe.db.set_value("Item", item_code, "custom_unlimited_stock", 1 if _to_bool(unlimited_stock) else 0)

    if stock_qty is not None:
        frappe.db.set_value("Item", item_code, "custom_stock_qty", _to_int(stock_qty))

    frappe.db.commit()

    return {"ok": 1}


@frappe.whitelist()
def get_stock_take_rows(item_codes=None):
    """
    Expands a chosen set of store items (template or simple) into one row
    per variant/item - the Stock Take page's "build my count sheet" step.
    An item/variant currently set to unlimited_stock (Always Available) is
    included too, flagged via "unlimited_stock" - the frontend warns
    before counting one of these, since stock_take_update() always
    switches it to tracked stock (unlimited_stock=0) once it's actually
    been counted here.
    """
    _ensure_store_access()

    item_codes = _parse_json_list(item_codes)
    rows = []

    for item_code in item_codes:
        item_code = (item_code or "").strip()
        if not item_code or not frappe.db.exists("Item", item_code):
            continue

        item_fields = ["item_name", "has_variants", "custom_unlimited_stock", "custom_stock_qty"]
        if _item_meta_has_field("custom_sku"):
            item_fields.append("custom_sku")

        item = frappe.db.get_value("Item", item_code, item_fields, as_dict=True)

        if not item:
            continue

        if item.has_variants:
            for variant in get_product_variants(item_code):
                label = " / ".join((variant.get("attributes") or {}).values()) or variant.get("item_name")

                rows.append({
                    "item_code": variant.get("name"),
                    "item_name": item.item_name,
                    "variant_label": label,
                    "sku": variant.get("sku") or "",
                    "current_stock_qty": variant.get("stock_qty") or 0,
                    "unlimited_stock": bool(variant.get("unlimited_stock")),
                })
        else:
            rows.append({
                "item_code": item_code,
                "item_name": item.item_name,
                "variant_label": "",
                "sku": item.get("custom_sku") or "",
                "current_stock_qty": item.custom_stock_qty or 0,
                "unlimited_stock": bool(item.custom_unlimited_stock),
            })

    return rows


@frappe.whitelist()
def stock_take_update(updates=None):
    """
    updates: [{"item_code": "...", "stock_qty": 12}, ...] - one bulk save
    for every row on the Stock Take page's count sheet, rather than one
    round trip per item.

    Always also clears unlimited_stock - a counted item is, by
    definition, now being actively tracked (the frontend already warned
    before including a previously-"Always Available" item in the count
    sheet at all), so this is safe to do unconditionally rather than only
    for rows that were unlimited before.
    """
    _ensure_store_access()

    updates = _parse_json_list(updates)

    if not updates:
        frappe.throw(_("Nothing to save."))

    updated = 0

    for row in updates:
        item_code = (row.get("item_code") or "").strip()
        stock_qty = row.get("stock_qty")

        if not item_code or stock_qty in (None, "") or not frappe.db.exists("Item", item_code):
            continue

        frappe.db.set_value("Item", item_code, {
            "custom_stock_qty": _to_int(stock_qty),
            "custom_unlimited_stock": 0,
        })
        updated += 1

    frappe.db.commit()

    return {"ok": 1, "updated": updated}


# -------------------------------------------------------------------
# Variant products (e.g. a hoodie in several sizes/wordings, some sizes
# priced higher, each with its own stock count)
# -------------------------------------------------------------------

def _create_variant_item(template, attribute_values, price, stock_qty, unlimited_stock, company, image=None, sku=None):
    suffix = "-".join(_slugify(v) for v in attribute_values.values()) or "VAR"
    item_code = f"{template.name}-{suffix}"

    variant = frappe.new_doc("Item")
    variant.item_code = item_code
    variant.item_name = template.item_name + " - " + " / ".join(attribute_values.values())
    variant.item_group = template.item_group
    variant.description = template.description
    variant.stock_uom = "Nos"
    variant.is_stock_item = 0
    variant.variant_of = template.name
    variant.custom_store_enabled = 1
    variant.custom_unlimited_stock = 1 if _to_bool(unlimited_stock) else 0
    variant.custom_stock_qty = _to_int(stock_qty)

    if sku and _item_meta_has_field("custom_sku"):
        variant.custom_sku = sku.strip()

    if image:
        variant.image = image
    elif template.image:
        variant.image = template.image

    for fieldname in BRAND_FIELDNAMES:
        if _item_meta_has_field(fieldname):
            variant.set(fieldname, template.get(fieldname))

    # A variant always shares its template's Store Visibility - there's
    # no per-variant option for this, same as the brand fields above.
    if _item_meta_has_field("custom_item_visibility"):
        variant.custom_item_visibility = template.get("custom_item_visibility")

    for attribute_name, value in attribute_values.items():
        variant.append("attributes", {"attribute": attribute_name, "attribute_value": value})

    _ensure_item_default_row(variant, company)

    variant.insert(ignore_permissions=True)

    price = _to_float(price)
    if price:
        _set_item_price(variant.name, DEFAULT_PRICE_LIST, price)

    return variant.name


@frappe.whitelist()
def create_variant_store_product(item_name=None, description=None, short_description=None, item_group=None,
                                  brands=None, image=None, attributes=None, variants=None, sku=None,
                                  gallery_images=None, personalization_enabled=None, personalization_label=None,
                                  logo_choice_enabled=None, visibility=None, coach_price=None):
    """
    attributes: [{"attribute": "Size", "values": ["Small", "Large"]}, ...]
    variants: [{"attribute_values": {"Size": "Small"}, "price": 10,
                "stock_qty": 5, "unlimited_stock": false}, ...]

    Creates the template Item (has_variants=1, never itself purchasable)
    plus one real Item per entry in `variants`, each with its own Item
    Default/Item Price/stock - exactly what webshop_purchase.py's
    get_item_or_variants() already knows how to read for checkout.

    coach_price is a single flat rate stored on the template only, never
    per-variant - a coach pays the same price no matter which size/colour
    they buy, unlike the regular price which does vary by variant. See
    webshop_purchase.py's _get_purchasable_item(), which looks this up via
    the variant's own variant_of rather than its own item_code.
    """
    _ensure_store_access()

    item_name = (item_name or "").strip()

    if not item_name:
        frappe.throw(_("Product name is required."))

    existing_item_code = frappe.db.get_value("Item", {"item_name": item_name}, "name")
    existing_variant_codes = []

    if existing_item_code:
        existing_has_variants = frappe.db.get_value("Item", existing_item_code, "has_variants")

        if existing_has_variants:
            existing_variant_codes = frappe.get_all(
                "Item", filters={"variant_of": existing_item_code}, pluck="name"
            )

            # A same-named variant template already existing is far more
            # often a leftover from an earlier save that didn't fully
            # complete (e.g. threw partway through creating its variants,
            # leaving the template itself behind - confirmed live with a
            # single-combination product, which insert()s the template
            # before ever reaching the loop that can fail) than an actual
            # second, different product - safe to replace automatically
            # the same as the simple-item conversion case below, as long
            # as nothing under it has actually been sold yet.
            if existing_variant_codes and frappe.db.exists(
                "Sales Invoice Item", {"item_code": ["in", existing_variant_codes]}
            ):
                frappe.throw(_(
                    "A product with variations named {0} already exists and has already been sold, "
                    "so it can't be replaced. Choose a different name."
                ).format(item_name))
        else:
            # A common real workflow: a product is created simple first, then
            # later needs variations added - safe to convert automatically as
            # long as it's never actually been sold on anything yet (once it
            # has, Frappe won't let has_variants be switched on, and rewriting
            # sold history out from under it would be wrong anyway).
            if frappe.db.exists("Sales Invoice Item", {"item_code": existing_item_code}):
                frappe.throw(_(
                    "An item named {0} already exists and has already been sold, so it can't be "
                    "safely converted into a product with variations. Choose a different name."
                ).format(item_name))

    attributes = _parse_json_list(attributes)
    variants = _parse_json_list(variants)

    if not attributes:
        frappe.throw(_("Add at least one attribute (e.g. Size) for a product with variations."))

    if not variants:
        frappe.throw(_("No variant combinations to create."))

    company = _store_company()

    with _as_administrator():
        if existing_item_code:
            # A template can't be deleted while its variants still point
            # at it via variant_of - clear those first, unsold-only
            # already confirmed above.
            for variant_code in existing_variant_codes:
                frappe.delete_doc("Item", variant_code, ignore_permissions=True, force=True)

            frappe.delete_doc("Item", existing_item_code, ignore_permissions=True, force=True)

        for attr in attributes:
            _ensure_item_attribute(attr.get("attribute"), attr.get("values") or [])

        template = frappe.new_doc("Item")
        template.item_code = item_name
        template.item_name = item_name
        template.item_group = _ensure_item_group((item_group or "").strip() or "Products")
        template.description = description or ""

        if short_description and _item_meta_has_field("custom_short_description"):
            template.custom_short_description = short_description.strip()[:200]

        if sku and _item_meta_has_field("custom_sku"):
            template.custom_sku = sku.strip()

        _apply_personalization(template, personalization_enabled, personalization_label)
        _apply_logo_choice(template, logo_choice_enabled)

        template.stock_uom = "Nos"
        template.is_stock_item = 0
        template.has_variants = 1
        template.custom_store_enabled = 1

        if image:
            template.image = image

        _apply_gallery_images(template, _parse_json_list(gallery_images) if gallery_images is not None else None)

        parsed_brands = _parse_brands(brands)
        for fieldname in BRAND_FIELDNAMES:
            if _item_meta_has_field(fieldname):
                template.set(fieldname, 1 if parsed_brands.get(fieldname) else 0)

        if visibility is not None and _item_meta_has_field("custom_item_visibility"):
            template.custom_item_visibility = visibility

        for attr in attributes:
            template.append("attributes", {"attribute": attr.get("attribute")})

        template.insert(ignore_permissions=True)

        _set_coach_price(template.name, coach_price)

        created = []
        first_variant_image = ""

        for variant_spec in variants:
            variant_image = (variant_spec.get("image") or "").strip()

            variant_name = _create_variant_item(
                template,
                variant_spec.get("attribute_values") or {},
                variant_spec.get("price"),
                variant_spec.get("stock_qty"),
                variant_spec.get("unlimited_stock"),
                company,
                image=variant_image,
                sku=variant_spec.get("sku"),
            )
            created.append(variant_name)

            if variant_image and not first_variant_image:
                first_variant_image = variant_image

        # A variant template has no image of its own to show in a store
        # listing (get_store_items() only ever reads the template's
        # image) - fall back to whichever variant got one first, so the
        # product still has a thumbnail instead of the blank placeholder.
        if not template.image and first_variant_image:
            frappe.db.set_value("Item", template.name, "image", first_variant_image)

    frappe.db.commit()

    return {"ok": 1, "item_code": template.name, "variants": created}


@frappe.whitelist()
def get_product_variants(template_item_code=None):
    _ensure_store_access()

    template_item_code = (template_item_code or "").strip()

    variant_fields = ["name", "item_name", "image", "disabled", "custom_stock_qty", "custom_unlimited_stock"]
    if _item_meta_has_field("custom_sku"):
        variant_fields.append("custom_sku")

    variants = frappe.get_all(
        "Item",
        filters={"variant_of": template_item_code},
        fields=variant_fields,
        order_by="item_name asc",
        limit_page_length=500,
    )

    result = []

    for variant in variants:
        attr_rows = frappe.get_all(
            "Item Variant Attribute",
            filters={"parent": variant.name, "parenttype": "Item"},
            fields=["attribute", "attribute_value"],
            order_by="idx asc",
        )
        price_row = _get_item_price_row(variant.name, DEFAULT_PRICE_LIST)

        result.append({
            "name": variant.name,
            "item_name": variant.item_name,
            "image": variant.image or "",
            "disabled": bool(variant.disabled),
            "stock_qty": variant.custom_stock_qty or 0,
            "unlimited_stock": bool(variant.custom_unlimited_stock),
            "price": price_row.price_list_rate if price_row else 0,
            "attributes": {row.attribute: row.attribute_value for row in attr_rows},
            "sku": variant.get("custom_sku") or "",
        })

    return result


@frappe.whitelist()
def update_variant(item_code=None, price=None, stock_qty=None, unlimited_stock=None, disabled=None, image=None, sku=None):
    _ensure_store_access()

    item_code = (item_code or "").strip()

    if not item_code or not frappe.db.exists("Item", item_code):
        frappe.throw(_("Variant not found."))

    if sku is not None and _item_meta_has_field("custom_sku"):
        frappe.db.set_value("Item", item_code, "custom_sku", sku.strip())

    if stock_qty is not None:
        frappe.db.set_value("Item", item_code, "custom_stock_qty", _to_int(stock_qty))

    if unlimited_stock is not None:
        frappe.db.set_value("Item", item_code, "custom_unlimited_stock", 1 if _to_bool(unlimited_stock) else 0)

    if disabled is not None:
        frappe.db.set_value("Item", item_code, "disabled", 1 if _to_bool(disabled) else 0)

    if image:
        frappe.db.set_value("Item", item_code, "image", image)

        template_item_code = frappe.db.get_value("Item", item_code, "variant_of")
        if template_item_code and not frappe.db.get_value("Item", template_item_code, "image"):
            frappe.db.set_value("Item", template_item_code, "image", image)

    if price is not None:
        with _as_administrator():
            _set_item_price(item_code, DEFAULT_PRICE_LIST, _to_float(price))

    frappe.db.commit()

    return {"ok": 1}


@frappe.whitelist()
def delete_variant(item_code=None):
    """Permanently removes a variant that's no longer stocked - Disabled
    only hides it from the store, it doesn't get it off this list, which
    isn't what's wanted once a size/colour is genuinely discontinued.
    Refuses (with a clear reason) rather than deleting when the variant
    has real order history against it, since that would silently orphan
    those past Sales Invoice/Order line items - Disable is still the
    right call for a variant like that."""
    _ensure_store_access()

    item_code = (item_code or "").strip()

    if not item_code or not frappe.db.exists("Item", item_code):
        frappe.throw(_("Variant not found."))
    if not frappe.db.get_value("Item", item_code, "variant_of"):
        frappe.throw(_("This isn't a variant."))

    try:
        frappe.delete_doc("Item", item_code, ignore_permissions=True)
        frappe.db.commit()
    except frappe.LinkExistsError:
        frappe.throw(_("This variant can't be deleted - it's on an existing order or invoice. Mark it as inactive instead so it stays out of the store but keeps its order history."))

    return {"ok": 1}


@frappe.whitelist()
def add_product_variant(template_item_code=None, attribute_values=None, price=None, stock_qty=None,
                         unlimited_stock=None, sku=None, image=None):
    """Adds one new variant (e.g. a size that wasn't offered when the
    product was first set up) onto an existing variant template, without
    touching anything already there - unlike create_variant_store_product,
    which rebuilds the whole product from scratch, this only ever inserts
    the one new Item. New attribute values (e.g. "XS" not used by any
    variant yet) are created automatically, same as at product creation."""
    _ensure_store_access()

    template_item_code = (template_item_code or "").strip()

    if not template_item_code or not frappe.db.exists("Item", template_item_code):
        frappe.throw(_("Product not found."))

    template = frappe.get_doc("Item", template_item_code)

    if not template.has_variants:
        frappe.throw(_("This product doesn't have variations."))

    if isinstance(attribute_values, dict):
        parsed_values = attribute_values
    else:
        try:
            parsed_values = frappe.parse_json(attribute_values) or {}
        except Exception:
            parsed_values = {}

    parsed_values = {k: (v or "").strip() for k, v in parsed_values.items() if (v or "").strip()}

    template_attributes = [row.attribute for row in (template.get("attributes") or [])]
    missing = [a for a in template_attributes if a not in parsed_values]

    if missing:
        frappe.throw(_("Choose a value for: {0}").format(", ".join(missing)))

    existing_variant_codes = frappe.get_all("Item", filters={"variant_of": template_item_code}, pluck="name")

    for existing_code in existing_variant_codes:
        rows = frappe.get_all(
            "Item Variant Attribute",
            filters={"parent": existing_code, "parenttype": "Item"},
            fields=["attribute", "attribute_value"],
        )
        if {row.attribute: row.attribute_value for row in rows} == parsed_values:
            frappe.throw(_("A variant with this exact combination already exists."))

    company = _store_company()

    with _as_administrator():
        for attribute_name in template_attributes:
            _ensure_item_attribute(attribute_name, [parsed_values[attribute_name]])

        variant_name = _create_variant_item(
            template,
            parsed_values,
            price,
            stock_qty,
            unlimited_stock,
            company,
            image=(image or "").strip(),
            sku=sku,
        )

    frappe.db.commit()

    return {"ok": 1, "item_code": variant_name}


@frappe.whitelist()
def add_product_variants_bulk(template_item_code=None, attribute_value_lists=None, price=None, stock_qty=None,
                               unlimited_stock=None):
    """
    Generates every combination across several values per attribute in
    one go (e.g. 20 Colours x 6 Sizes = up to 120 variants) instead of
    add_product_variant's one-at-a-time form - built for exactly that
    "adding 120 variations by hand is taking forever" case. All new
    variants share the one price/stock/unlimited_stock given here; SKUs
    and images stay editable per-row afterwards (image can also be
    applied in bulk per attribute-value combination further down this
    same modal). Combinations that already exist are silently skipped
    rather than erroring, so this is safe to run again after adding more
    values to top up a range.

    Coach pricing isn't set here - it's a single flat rate on the
    template itself (see create_variant_store_product/update_store_product),
    the same for every variant regardless of size/colour.

    attribute_value_lists: {"Colour": ["Red", "Blue", ...], "Size": ["S", "M", "L"]}
    - one entry per attribute on the product template, each a list of
    the values to generate every combination across.
    """
    _ensure_store_access()

    template_item_code = (template_item_code or "").strip()

    if not template_item_code or not frappe.db.exists("Item", template_item_code):
        frappe.throw(_("Product not found."))

    template = frappe.get_doc("Item", template_item_code)

    if not template.has_variants:
        frappe.throw(_("This product doesn't have variations."))

    if isinstance(attribute_value_lists, dict):
        parsed_lists = attribute_value_lists
    else:
        try:
            parsed_lists = frappe.parse_json(attribute_value_lists) or {}
        except Exception:
            parsed_lists = {}

    template_attributes = [row.attribute for row in (template.get("attributes") or [])]

    value_lists = []
    missing = []

    for attribute_name in template_attributes:
        values = [
            v.strip() for v in (parsed_lists.get(attribute_name) or [])
            if (v or "").strip()
        ]
        # De-duplicate while keeping the order the user typed them in, so
        # a repeated value in a pasted/comma-separated list doesn't
        # double up in the combination count below.
        seen = set()
        deduped = []
        for v in values:
            if v not in seen:
                seen.add(v)
                deduped.append(v)

        if not deduped:
            missing.append(attribute_name)
        else:
            value_lists.append(deduped)

    if missing:
        frappe.throw(_("Add at least one value for: {0}").format(", ".join(missing)))

    combinations = list(itertools.product(*value_lists))

    if len(combinations) > 1000:
        frappe.throw(_(
            "That would create {0} combinations in one go, which is more than this can safely "
            "handle at once - narrow down the values and add them in smaller batches."
        ).format(len(combinations)))

    existing_combos = set()
    for existing_code in frappe.get_all("Item", filters={"variant_of": template_item_code}, pluck="name"):
        rows = frappe.get_all(
            "Item Variant Attribute",
            filters={"parent": existing_code, "parenttype": "Item"},
            fields=["attribute", "attribute_value"],
        )
        existing_combos.add(tuple((row.attribute, row.attribute_value) for row in sorted(rows, key=lambda r: r.attribute)))

    company = _store_company()
    created = []
    skipped = 0

    with _as_administrator():
        for attribute_name, values in zip(template_attributes, value_lists):
            _ensure_item_attribute(attribute_name, values)

        for combo in combinations:
            attribute_values = dict(zip(template_attributes, combo))
            combo_key = tuple(sorted(attribute_values.items()))

            if combo_key in existing_combos:
                skipped += 1
                continue

            variant_name = _create_variant_item(
                template,
                attribute_values,
                price,
                stock_qty,
                unlimited_stock,
                company,
            )
            created.append(variant_name)
            existing_combos.add(combo_key)

    frappe.db.commit()

    return {"ok": 1, "created": created, "created_count": len(created), "skipped_count": skipped}
