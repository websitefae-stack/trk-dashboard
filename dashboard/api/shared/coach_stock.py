"""
Per-coach Kid/Teen Pack stock tracking and pack-handover compliance -
scoped and fully specified by the business owner (Ashley suspects some
coaches aren't actually handing out the physical Kid/Teen Pack included
in a new client's first invoice, or are photocopying instead of
ordering real stock). This module gives her:

- a per-coach stock ledger (Coach Stock Movement - see
  create_coach_stock_movement_doctype.py's own docstring for why it's
  add-only with the balance always computed via SUM, never cached),
- a coach-facing worklist of Kid/Teen clients who haven't had a pack
  handover recorded yet (get_pending_pack_handovers), with a simple
  Given / Could Not Give - Out of Stock / Not Given - Other Reason
  outcome (record_pack_handover),
- a franchisor-facing compliance report across every coach
  (get_pack_compliance_report) and a manual stock adjustment tool
  (set_coach_stock_adjustment).

Deliberately NOT the same thing as Item.custom_stock_qty/custom_
unlimited_stock (see store_stock.py) - those track the franchisor's own
single company-warehouse stock number, decremented on ANY Sales Invoice
sale. This tracks how many packs a specific COACH is personally
holding, which only ever changes via an order from the Coach Store
(webshop_purchase.create_coach_store_order - see
record_coach_stock_received_on_submit() below, wired as a second
Sales Invoice on_submit hook in hooks.py alongside store_stock.py's own
one) or a handover/adjustment recorded here.

Schema is intentionally not Kid/Teen-specific - Coach Stock Movement.item
is a plain Link to Item, not a two-value enum, so a future "additional
workbook" SKU (out of scope for this build - those are bought on an
ongoing basis as a client progresses, not part of the pack included in
a client's first invoice) needs zero schema change, just an Item that
qualifies for whichever lookup is in play.
"""

import frappe
from frappe import _

from dashboard.api.shared.permissions import is_franchisor_user, get_current_coach_name
from dashboard.api.shared.invoices import _coach_label_from_name, _get_coach_options
from dashboard.api.shared.store_products import _parse_json_list
from dashboard.api.shared.utils import coalesce_str, coalesce_raw

MOVEMENT_DOCTYPE = "Coach Stock Movement"

# A client is always exactly one of Kid or Teen when a physical pack
# applies at all - see client_details.py's own identical note on
# custom_resilient_pack_sent.
PACK_CLIENT_TYPES = ("Kid", "Teen")

HANDOVER_STATUS_OPTIONS = (
    "Given",
    "Could Not Give - Out of Stock",
    "Not Given - Other Reason",
)

# "Received (Order)" and "Given to Client" are only ever written by the
# two code paths below (the Coach Store order hook and
# record_pack_handover()) - set_coach_stock_adjustment() rejects both,
# so a franchisor can never hand-fabricate either audit trail.
ADJUSTMENT_MOVEMENT_TYPES = ("Opening Count", "Manual Adjustment")

# Looked up by item_name (not a fixed item_code) - these two Items must
# already exist on the site; neither is ever auto-created here (see
# _pack_item_for_client_type()'s own note). Confirmed live against the
# real Store product names - not the generic "Kid Pack"/"Teen Pack"
# this module shipped with, which matched nothing on the real site.
PACK_ITEM_NAMES = ("The Resilient Kid Client Pack", "The Resilient Teen Client Pack")


def _pack_item_for_client_type(client_type):
    """Teen -> the Teen pack, anything else Kid-eligible (only ever
    called for client_type in PACK_CLIENT_TYPES - see record_pack_
    handover()'s own guard) -> the Kid pack. Doesn't auto-create either
    Item if it's missing from this site - callers look it up by
    item_name themselves and decide what to do when it's not found."""
    return PACK_ITEM_NAMES[1] if client_type == "Teen" else PACK_ITEM_NAMES[0]


def _resolve_coach_for_call(coach=None):
    """Shared coach-resolution/permission rule used by every whitelisted
    function below that takes an optional `coach` arg: no coach given
    resolves the CURRENT logged-in coach (PermissionError if the caller
    isn't one, same as get_current_coach_name's own default behaviour);
    an explicit coach is only allowed when it's the caller's own coach
    identity, or the caller is the franchisor looking at someone else's."""
    coach = coalesce_str("coach", coach)
    own_coach = get_current_coach_name(optional=True)

    if not coach:
        if not own_coach:
            frappe.throw(_("Only a coach can access this."), frappe.PermissionError)
        return own_coach

    if coach != own_coach and not is_franchisor_user():
        frappe.throw(_("Only the franchisor can view another coach's stock."), frappe.PermissionError)

    if not frappe.db.exists("Coach", coach):
        frappe.throw(_("Coach not found."))

    return coach


def _coach_stock_balances(coach):
    """The one source of truth for "current balance" - SQL SUM/GROUP BY,
    not Python-side iteration over every row, for correctness at scale.
    get_coach_stock_balances() and record_pack_handover()'s own
    negative-balance check both read through this (via _balance_for_item
    below) rather than duplicating the aggregation."""
    rows = frappe.db.sql(
        """
        select item, sum(quantity_change) as balance
        from `tabCoach Stock Movement`
        where coach = %s
        group by item
        """,
        (coach,),
        as_dict=True,
    )
    return {row.item: int(row.balance or 0) for row in rows}


def _balance_for_item(coach, item):
    return _coach_stock_balances(coach).get(item, 0)


@frappe.whitelist()
def get_pack_item_options():
    """Franchisor-only - the Item choices for a manual stock adjustment.
    Kid Pack/Teen Pack by item_name, OR (for future extensibility -
    additional workbook SKUs this build deliberately doesn't wire up
    anywhere else, but shouldn't need a code change just to appear
    here) any Item flagged custom_store_enabled. Doesn't auto-create Kid
    Pack/Teen Pack if either is missing from this site - this just
    comes back without them, and the franchisor-facing page says so
    rather than erroring."""
    if not is_franchisor_user():
        frappe.throw(_("Only the franchisor can manage stock."), frappe.PermissionError)

    rows = frappe.get_all(
        "Item",
        or_filters=[
            ["item_name", "in", list(PACK_ITEM_NAMES)],
            ["custom_store_enabled", "=", 1],
        ],
        fields=["name", "item_name"],
        order_by="item_name asc",
        limit_page_length=0,
    )
    return [{"item_code": row.name, "item_name": row.item_name or row.name} for row in rows]


@frappe.whitelist()
def get_coach_stock_balances(coach=None):
    """One row per Item that has ANY Coach Stock Movement for this coach
    at all - an Item nobody's ever ordered or adjusted for this coach
    just doesn't appear, rather than showing every store Item at 0."""
    coach = _resolve_coach_for_call(coach)
    balances = _coach_stock_balances(coach)
    if not balances:
        return []

    items = frappe.get_all(
        "Item",
        filters={"name": ["in", list(balances.keys())]},
        fields=["name", "item_name"],
    )
    item_names = {row.name: row.item_name or row.name for row in items}

    return [
        {"item": item, "item_name": item_names.get(item, item), "balance": balance}
        for item, balance in balances.items()
    ]


def _client_names_for_coach(coach):
    return frappe.get_all(
        "Client",
        or_filters=[
            ["primary_coach", "=", coach],
            ["attending_coach", "=", coach],
        ],
        pluck="name",
        limit_page_length=0,
    )


@frappe.whitelist()
def get_pending_pack_handovers(coach=None):
    """Every Active (non-Archived - see clients.py's own identical
    "no status picked" default) Kid/Teen client of this coach with no
    custom_pack_handover_status recorded yet.

    Deliberately NOT gated on an actual session-count/Event record -
    confirmed scope for this build: "first session" is treated here as
    simply "every Kid/Teen client who hasn't had a handover recorded
    yet", which the coach is expected to action around their first
    session with each client. Inferring the real first-session moment
    from calendar.py's Event records would need deeper research into
    that module than this build covers, and would be far more fragile
    than this plain "not yet recorded" worklist."""
    coach = _resolve_coach_for_call(coach)

    client_names = _client_names_for_coach(coach)
    if not client_names:
        return []

    return frappe.get_all(
        "Client",
        filters=[
            ["name", "in", client_names],
            ["status", "!=", "Archived"],
            ["client_type", "in", list(PACK_CLIENT_TYPES)],
            ["custom_pack_handover_status", "is", "not set"],
        ],
        fields=["name", "full_name", "client_type"],
        order_by="full_name asc",
        limit_page_length=0,
    )


def _ensure_can_record_handover(client_doc):
    """Caller must be the client's own assigned coach (primary or
    attending - same either-or this app already treats as equivalent
    "belongs to this coach" everywhere else, e.g. session_workers/
    index.py's own client lookup) or the franchisor."""
    if is_franchisor_user():
        return

    own_coach = get_current_coach_name(optional=True)
    if own_coach and own_coach in (client_doc.get("primary_coach"), client_doc.get("attending_coach")):
        return

    frappe.throw(_("You don't have access to this client."), frappe.PermissionError)


def _acting_coach_for_handover(client_doc):
    """Whose stock to deduct from when a pack is actually given: the
    logged-in coach themselves when they're one of this client's own
    coaches (the normal case - they're the one who physically handed it
    over), otherwise this client's primary/attending coach - covers the
    franchisor recording a handover on a coach's behalf without
    deducting from nobody's stock."""
    own_coach = get_current_coach_name(optional=True)
    if own_coach and own_coach in (client_doc.get("primary_coach"), client_doc.get("attending_coach")):
        return own_coach

    return client_doc.get("primary_coach") or client_doc.get("attending_coach")


@frappe.whitelist()
def record_pack_handover(client, status, reason=None):
    client = coalesce_str("client", client)
    status = coalesce_str("status", status)
    reason = coalesce_str("reason", reason)

    if not client or not frappe.db.exists("Client", client):
        frappe.throw(_("Client not found."))

    if status not in HANDOVER_STATUS_OPTIONS:
        frappe.throw(_("Invalid handover status."))

    doc = frappe.get_doc("Client", client)
    _ensure_can_record_handover(doc)

    if status == "Given":
        if doc.client_type not in PACK_CLIENT_TYPES:
            frappe.throw(_("This client isn't a Kid or Teen client."))

        coach = _acting_coach_for_handover(doc)
        if not coach:
            frappe.throw(_("This client has no coach assigned - there's no coach's stock to deduct from."))

        item_name = _pack_item_for_client_type(doc.client_type)
        item_code = frappe.db.get_value("Item", {"item_name": item_name}, "name")
        if not item_code:
            frappe.throw(_("No '{0}' Item exists yet - ask the franchisor to set one up first.").format(item_name))

        # Confirmed decision (reversed from this feature's first build,
        # which allowed a negative balance and just logged it): a coach
        # can never record "Given" without the stock to back it up - no
        # negative balances allowed at all. Steers them towards "Could
        # Not Give - Out of Stock" instead, which is itself the accurate
        # record of what actually happened.
        balance = _balance_for_item(coach, item_code)
        if balance <= 0:
            frappe.throw(_(
                "{0} has no {1} left in stock to give out - record this as "
                "\"Could Not Give - Out of Stock\" instead."
            ).format(_coach_label_from_name(coach), item_name))

        frappe.get_doc({
            "doctype": MOVEMENT_DOCTYPE,
            "coach": coach,
            "item": item_code,
            "quantity_change": -1,
            "movement_type": "Given to Client",
            "reference_client": client,
            "created_by_user": frappe.session.user,
        }).insert(ignore_permissions=True)

        doc.custom_resilient_pack_sent = 1
        doc.custom_pack_handover_reason = ""
    else:
        if status == "Not Given - Other Reason" and not reason:
            frappe.throw(_("Please enter a reason."))

        # "Could Not Give - Out of Stock" needs no free-text reason - the
        # status itself already says why.
        doc.custom_pack_handover_reason = reason if status == "Not Given - Other Reason" else ""

    doc.custom_pack_handover_status = status
    doc.custom_pack_handover_date = frappe.utils.today()
    doc.custom_pack_handover_recorded_by = frappe.session.user
    doc.save(ignore_permissions=True)
    frappe.db.commit()

    return {"ok": True}


@frappe.whitelist()
def set_coach_stock_adjustment(coach, item, quantity_change, movement_type, notes=None):
    if not is_franchisor_user():
        frappe.throw(_("Only the franchisor can adjust coach stock."), frappe.PermissionError)

    coach = coalesce_str("coach", coach)
    item = coalesce_str("item", item)
    movement_type = coalesce_str("movement_type", movement_type)
    notes = coalesce_str("notes", notes)

    try:
        quantity_change = int(coalesce_raw("quantity_change", quantity_change) or 0)
    except (TypeError, ValueError):
        frappe.throw(_("Quantity must be a whole number."))

    if movement_type not in ADJUSTMENT_MOVEMENT_TYPES:
        frappe.throw(_("Invalid movement type for a manual adjustment."))

    if movement_type == "Manual Adjustment" and not notes:
        frappe.throw(_("Please enter a note explaining this adjustment."))

    if not quantity_change:
        frappe.throw(_("Enter a non-zero quantity."))

    if not frappe.db.exists("Coach", coach):
        frappe.throw(_("Coach not found."))

    if not frappe.db.exists("Item", item):
        frappe.throw(_("Item not found."))

    # No negative balances allowed anywhere in this ledger - same rule
    # as record_pack_handover()'s own guard.
    if _balance_for_item(coach, item) + quantity_change < 0:
        frappe.throw(_("That would take {0}'s stock below zero.").format(_coach_label_from_name(coach)))

    frappe.get_doc({
        "doctype": MOVEMENT_DOCTYPE,
        "coach": coach,
        "item": item,
        "quantity_change": quantity_change,
        "movement_type": movement_type,
        "notes": notes,
        "created_by_user": frappe.session.user,
    }).insert(ignore_permissions=True)
    frappe.db.commit()

    return {"ok": True, "balance": _balance_for_item(coach, item)}


@frappe.whitelist()
def get_coach_stock_take_rows():
    """Franchisor-only - the whole count sheet in one call: every coach,
    crossed with every pack Item, with their current balance already
    filled in. Confirmed live request: entering stock one coach/one item
    at a time (the existing Adjust Stock modal) was too slow for an
    actual stock take across the whole coach roster - this is the "see
    the full list and just type the numbers in" view, paired with
    coach_stock_take_update() below for the one bulk save."""
    if not is_franchisor_user():
        frappe.throw(_("Only the franchisor can view this."), frappe.PermissionError)

    items = get_pack_item_options()
    coaches = _get_coach_options()

    rows = []
    for coach in coaches:
        balances = _coach_stock_balances(coach["value"])
        rows.append({
            "coach": coach["value"],
            "coach_name": coach["label"],
            "balances": {item["item_code"]: balances.get(item["item_code"], 0) for item in items},
        })

    return {"items": items, "coaches": rows}


@frappe.whitelist()
def coach_stock_take_update(updates=None):
    """Franchisor-only bulk save for the Stock Take grid - one round trip
    for the whole count sheet rather than one per coach/item (see get_
    coach_stock_take_rows()'s own docstring for why). `updates` is
    [{"coach":, "item":, "stock_qty":}, ...] - an ABSOLUTE count per
    cell, same shape as store_products.stock_take_update()'s own updates
    list, not a relative quantity_change like set_coach_stock_adjustment
    takes. A row whose stock_qty hasn't actually changed from the
    current balance is skipped - no empty movement rows. First-ever
    count for a coach/item records as "Opening Count", any later
    recount as "Manual Adjustment", decided automatically rather than
    asking the franchisor to pick for every cell. stock_qty is always
    treated as >= 0 - a physical count can't be negative, so there's no
    separate negative-balance guard to apply here (unlike set_coach_
    stock_adjustment's free-form relative quantity_change)."""
    if not is_franchisor_user():
        frappe.throw(_("Only the franchisor can update stock."), frappe.PermissionError)

    updates = _parse_json_list(updates)
    if not updates:
        frappe.throw(_("Nothing to save."))

    updated = 0
    for row in updates:
        coach = (row.get("coach") or "").strip()
        item = (row.get("item") or "").strip()
        stock_qty = row.get("stock_qty")

        if not coach or not item or stock_qty in (None, ""):
            continue
        if not frappe.db.exists("Coach", coach) or not frappe.db.exists("Item", item):
            continue

        try:
            stock_qty = max(0, int(stock_qty))
        except (TypeError, ValueError):
            continue

        current = _balance_for_item(coach, item)
        delta = stock_qty - current
        if delta == 0:
            continue

        has_prior_movement = bool(frappe.db.exists(MOVEMENT_DOCTYPE, {"coach": coach, "item": item}))

        frappe.get_doc({
            "doctype": MOVEMENT_DOCTYPE,
            "coach": coach,
            "item": item,
            "quantity_change": delta,
            "movement_type": "Manual Adjustment" if has_prior_movement else "Opening Count",
            "notes": "Stock take" if has_prior_movement else None,
            "created_by_user": frappe.session.user,
        }).insert(ignore_permissions=True)
        updated += 1

    frappe.db.commit()
    return {"ok": True, "updated": updated}


@frappe.whitelist()
def get_pack_compliance_report():
    """Ashley's "is pack compliance actually happening" view - one row
    per coach who has at least one Active Kid/Teen client, with that
    client base split by handover outcome (including "Not Recorded",
    the get_pending_pack_handovers() cohort) alongside the same coach's
    current stock balances. Structured as a flat list of per-coach dicts
    so a table/report UI can render it with no further reshaping."""
    if not is_franchisor_user():
        frappe.throw(_("Only the franchisor can view this report."), frappe.PermissionError)

    rows = frappe.get_all(
        "Client",
        filters=[
            ["status", "!=", "Archived"],
            ["client_type", "in", list(PACK_CLIENT_TYPES)],
        ],
        fields=["name", "primary_coach", "attending_coach", "custom_pack_handover_status"],
        limit_page_length=0,
    )

    by_coach = {}
    for row in rows:
        coach = row.primary_coach or row.attending_coach
        if not coach:
            continue
        by_coach.setdefault(coach, []).append(row)

    results = []
    for coach in sorted(by_coach.keys(), key=lambda name: _coach_label_from_name(name)):
        clients = by_coach[coach]

        counts = {
            "Given": 0,
            "Could Not Give - Out of Stock": 0,
            "Not Given - Other Reason": 0,
            "Not Recorded": 0,
        }
        for client in clients:
            status = client.custom_pack_handover_status or "Not Recorded"
            counts[status] = counts.get(status, 0) + 1

        results.append({
            "coach": coach,
            "coach_name": _coach_label_from_name(coach),
            "client_count": len(clients),
            "status_counts": counts,
            "stock_balances": get_coach_stock_balances(coach=coach),
        })

    return results


def record_coach_stock_received_on_submit(doc, method=None):
    """Second Sales Invoice on_submit hook (wired in hooks.py alongside
    store_stock.decrement_stock_on_submit, which is a different concern
    entirely - see this module's own docstring). custom_coach is set
    only by webshop_purchase.create_coach_store_order(), so its presence
    is this feature's whole signal that an invoice is a coach's own
    stock order, not a guest/online sale or a manual HQ invoice to a
    coach for something unrelated.

    Scoped to Kid Pack/Teen Pack by item_name specifically, rather than
    every item on the invoice - an order that also includes branded
    merch must never create a stock movement for that merch; this
    ledger is only ever about the physical client pack.

    Defensive by design, same as store_stock.py's own hooks - a
    stock-tracking hiccup here must never block a real invoice
    submission, so any failure is logged and swallowed rather than
    raised."""
    try:
        coach = doc.get("custom_coach")
        if not coach:
            return

        tracked_item_codes = set(frappe.get_all(
            "Item",
            filters={"item_name": ["in", list(PACK_ITEM_NAMES)]},
            pluck="name",
        ))
        if not tracked_item_codes:
            return

        for row in doc.items or []:
            if row.item_code not in tracked_item_codes:
                continue

            qty = int(row.qty or 0)
            if not qty:
                continue

            frappe.get_doc({
                "doctype": MOVEMENT_DOCTYPE,
                "coach": coach,
                "item": row.item_code,
                "quantity_change": qty,
                "movement_type": "Received (Order)",
                "reference_sales_invoice": doc.name,
                "created_by_user": doc.owner,
            }).insert(ignore_permissions=True)
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Coach Stock Received Hook Failed")
