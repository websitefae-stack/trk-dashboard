import frappe
from frappe import _
from frappe.utils import now_datetime, get_url, get_fullname, flt

from dashboard.api.shared.permissions import ensure_logged_in, is_franchisor_user, ensure_office_user, get_current_coach_name
from dashboard.api.shared.utils import coalesce_str, coalesce_raw
from dashboard.api.shared.notifications import create_trk_notification, FRANCHISOR_USERS, ASHLEY_USER
from dashboard.api.shared.item_access import _get_coach_login, DEFAULT_PRICE_LIST, SERVICE_ITEM_GROUP
from dashboard.api.shared import payment_utils


LEAD_DOCTYPE = "Client Lead"
TRANSFER_DOCTYPE = "Client Transfer Agreement"
TRANSFER_FEE_ITEM_CODE = "Client Transfer Fee"
DEFAULT_TRANSFER_FEE = 100

STATUS_AWAITING_RECEIVING = "Awaiting Receiving Coach"
STATUS_AWAITING_FRANCHISOR = "Awaiting Franchisor"
STATUS_AWAITING_TRANSFERRING = "Awaiting Transferring Coach"
STATUS_COMPLETED = "Completed"
STATUS_DECLINED = "Declined"

OPEN_STATUSES = (STATUS_AWAITING_RECEIVING, STATUS_AWAITING_FRANCHISOR, STATUS_AWAITING_TRANSFERRING)

# Which of the three signature roles is currently "on the clock" for a
# given status - drives both who's allowed to sign/decline right now
# (_current_signer_role must match this) and, on sign_transfer, what the
# next status becomes.
_ROLE_FOR_STATUS = {
    STATUS_AWAITING_RECEIVING: "receiving",
    STATUS_AWAITING_FRANCHISOR: "franchisor",
    STATUS_AWAITING_TRANSFERRING: "transferring",
}


# =====================================================
# BASIC HELPERS
# =====================================================

def _current_coach_name():
    return get_current_coach_name(optional=True)


def _coach_label(coach_name):
    if not coach_name:
        return ""

    label = frappe.db.get_value("Coach", coach_name, "coach_name")
    return label or coach_name


def _coach_territory(coach_name):
    if not coach_name:
        return ""

    return frappe.db.get_value("Coach", coach_name, "territory_postcodes") or ""


def _lead_document_fields(lead_name):
    """
    The handful of Client Territory Transfer Agreement fields sourced from
    the lead itself rather than the transfer doc - see get_transfer_for_signing().
    """
    if not lead_name or not frappe.db.exists(LEAD_DOCTYPE, lead_name):
        return {"parent_guardian_name": "", "date_first_registered": "", "client_reference": ""}

    lead = frappe.db.get_value(LEAD_DOCTYPE, lead_name, ["contact_name", "creation"], as_dict=True) or {}

    return {
        "parent_guardian_name": lead.get("contact_name") or "",
        "date_first_registered": str(lead.get("creation") or "")[:10],
        "client_reference": lead_name,
    }


def _resolve_coach(value):
    """
    Accepts a Coach record's own name, their login email (user/coach_email),
    or their plain display name (coach_name, e.g. "Liz") - so a franchisor
    calling backfill_client_transfer() directly by URL can just type a name
    rather than looking up the internal Coach doc id first. Returns the
    Coach doc name, or "" if nothing matches (ambiguous display-name
    matches are treated as no match - caller must be more specific).
    """
    if not value:
        return ""

    if frappe.db.exists("Coach", value):
        return value

    for fieldname in ("user", "coach_email"):
        found = frappe.db.get_value("Coach", {fieldname: value}, "name")
        if found:
            return found

    matches = frappe.get_all("Coach", filters={"coach_name": ["like", f"%{value}%"]}, pluck="name")
    if len(matches) == 1:
        return matches[0]

    return ""


def _is_franchisor_coach(coach_name):
    login = _get_coach_login(coach_name)
    return bool(login) and login in FRANCHISOR_USERS


def _expected_role_for_status(status):
    return _ROLE_FOR_STATUS.get(status)


def _current_signer_role(transfer):
    """
    Which of the three signature roles (if any) the logged-in user actually
    is on this specific agreement. A coach who is one of the two parties
    always resolves to their own role first - only a franchisor who ISN'T
    also one of the two coaches on this transfer ever resolves to
    "franchisor" (matches the 2-vs-3-signature rule: when Ashley herself is
    transferring or receiving, there's no separate franchisor step at all).
    """
    current_coach = _current_coach_name()

    if current_coach and current_coach == transfer.receiving_coach:
        return "receiving"

    if current_coach and current_coach == transfer.transferring_coach:
        return "transferring"

    if transfer.requires_franchisor_signature and is_franchisor_user():
        return "franchisor"

    return None


def _log_row(event):
    return {
        "timestamp": now_datetime(),
        "event": event,
        "user": frappe.session.user,
        "ip_address": getattr(frappe.local, "request_ip", "") or "",
    }


def _sign_url(transfer_name):
    return get_url(f"/transfer_sign?name={transfer_name}")


# =====================================================
# NOTIFICATIONS
# =====================================================

def _notify_next_signer(transfer):
    status = transfer.status

    if status == STATUS_AWAITING_FRANCHISOR:
        # Ashley's own signing step - only her, not the whole franchisor-
        # level group, and only when it's actually her turn (this branch
        # only runs while status is STATUS_AWAITING_FRANCHISOR, never on
        # the receiving/transferring coach's own steps).
        try:
            create_trk_notification(
                recipient_user=ASHLEY_USER,
                notification_type="Task",
                message="A Client Transfer Agreement for {0} needs your signature.".format(transfer.client_name),
                reference_doctype=TRANSFER_DOCTYPE,
                reference_name=transfer.name,
            )
        except Exception:
            frappe.log_error(frappe.get_traceback(), f"Transfer Notification Failed - {transfer.name}")
        return

    target_coach = transfer.receiving_coach if status == STATUS_AWAITING_RECEIVING else (
        transfer.transferring_coach if status == STATUS_AWAITING_TRANSFERRING else None
    )

    if not target_coach:
        return

    coach_user = _get_coach_login(target_coach)
    if not coach_user:
        return

    try:
        create_trk_notification(
            recipient_user=coach_user,
            notification_type="Task",
            message="A Client Transfer Agreement for {0} needs your signature.".format(transfer.client_name),
            reference_doctype=TRANSFER_DOCTYPE,
            reference_name=transfer.name,
            coach=target_coach,
        )
    except Exception:
        frappe.log_error(frappe.get_traceback(), f"Transfer Notification Failed - {transfer.name}")


def _notify_transfer_completed(transfer):
    message = "The transfer of {0} to {1} is complete.".format(
        transfer.client_name, _coach_label(transfer.receiving_coach)
    )

    for coach_name in (transfer.transferring_coach, transfer.receiving_coach):
        coach_user = _get_coach_login(coach_name)
        if not coach_user:
            continue

        try:
            create_trk_notification(
                recipient_user=coach_user,
                notification_type="Task",
                message=message,
                reference_doctype=TRANSFER_DOCTYPE,
                reference_name=transfer.name,
                coach=coach_name,
            )
        except Exception:
            frappe.log_error(frappe.get_traceback(), f"Transfer Notification Failed - {transfer.name}")


def _notify_transfer_fee_invoiced(transfer):
    """
    Fired whenever _maybe_invoice_transfer_fee actually raises the fee
    invoice (live payment, backfill, or a manual link_transfer_to_client)
    - previously nothing told either coach this had happened at all,
    which Ashley flagged: the transferring coach (who the fee is owed
    to) needs to know to expect payment, and the receiving coach (who
    the invoice is billed to) needs to know they now owe it.
    """
    amount = transfer.transfer_fee_amount or DEFAULT_TRANSFER_FEE
    transferring_label = _coach_label(transfer.transferring_coach)
    receiving_label = _coach_label(transfer.receiving_coach)

    recipients = (
        (transfer.transferring_coach, "You're owed a £{0} client transfer fee from {1} for {2} ({3}) - keep an eye out for payment.".format(
            amount, receiving_label, transfer.client_name, transfer.invoice,
        )),
        (transfer.receiving_coach, "You've been invoiced £{0} for the client transfer fee for {1} - please pay {2} to {3}.".format(
            amount, transfer.client_name, transfer.invoice, transferring_label,
        )),
    )

    for coach_name, message in recipients:
        coach_user = _get_coach_login(coach_name)
        if not coach_user:
            continue

        try:
            create_trk_notification(
                recipient_user=coach_user,
                notification_type="Task",
                message=message,
                reference_doctype="Sales Invoice",
                reference_name=transfer.invoice,
                coach=coach_name,
            )
        except Exception:
            frappe.log_error(frappe.get_traceback(), f"Transfer Notification Failed - {transfer.name}")


def _notify_transfer_fee_invoice_failed(transfer):
    """Invoicing on the client's payment is best-effort (see
    _process_invoice_transfer_fee / _maybe_invoice_transfer_fee) - this is
    the safety net that replaces the old "block signing until it works"
    behaviour, since a billing problem now surfaces long after signing,
    on a payment the transferring coach isn't necessarily even part of."""
    message = (
        "The £{0} client transfer fee for {1} ({2} to {3}) couldn't be "
        "invoiced automatically now the client has paid {3} - check {2}'s "
        "Coach record (company/bank account) and invoice it manually."
    ).format(
        transfer.transfer_fee_amount or DEFAULT_TRANSFER_FEE,
        transfer.client_name,
        _coach_label(transfer.transferring_coach),
        _coach_label(transfer.receiving_coach),
    )

    try:
        create_trk_notification(
            recipient_user=ASHLEY_USER,
            notification_type="Task",
            message=message,
            reference_doctype=TRANSFER_DOCTYPE,
            reference_name=transfer.name,
        )
    except Exception:
        frappe.log_error(frappe.get_traceback(), f"Transfer Notification Failed - {transfer.name}")


def _notify_transfer_declined(transfer):
    coach_user = _get_coach_login(transfer.transferring_coach)
    if not coach_user:
        return

    try:
        create_trk_notification(
            recipient_user=coach_user,
            notification_type="Task",
            message="The transfer of {0} to {1} was declined.".format(
                transfer.client_name, _coach_label(transfer.receiving_coach)
            ),
            reference_doctype=TRANSFER_DOCTYPE,
            reference_name=transfer.name,
            coach=transfer.transferring_coach,
        )
    except Exception:
        frappe.log_error(frappe.get_traceback(), f"Transfer Notification Failed - {transfer.name}")


# =====================================================
# INVOICE / CUSTOMER / ITEM HELPERS
# =====================================================

def _ensure_transfer_fee_item():
    if frappe.db.exists("Item", TRANSFER_FEE_ITEM_CODE):
        return TRANSFER_FEE_ITEM_CODE

    # Local import - store_products.py imports from item_access.py at load
    # time, which this module also imports from, so importing _ensure_
    # item_group back at module level here would risk a circular import.
    from dashboard.api.shared.store_products import _ensure_item_group

    item = frappe.new_doc("Item")
    item.item_code = TRANSFER_FEE_ITEM_CODE
    item.item_name = TRANSFER_FEE_ITEM_CODE
    item.item_group = _ensure_item_group(SERVICE_ITEM_GROUP)
    item.stock_uom = "Nos"
    item.is_stock_item = 0
    item.include_item_in_manufacturing = 0
    item.insert(ignore_permissions=True)

    return item.name


def _get_or_create_coach_linked_client(coach_name):
    """
    Coach.linked_client is this app's existing "internal billing record" for
    a coach (a Client with client_type Franchise) - already used to invoice
    coaches for their Franchise Fee, and already given a blanket "any coach
    may invoice/access this" carve-out (see permissions.py). Reusing it here
    means the £100 transfer fee shows up through exactly the same
    inter-franchisee invoicing machinery, instead of a parallel one.
    """
    existing = frappe.db.get_value("Coach", coach_name, "linked_client")
    if existing and frappe.db.exists("Client", existing):
        return existing

    from dashboard.api.shared.client_details import set_full_name_from_parts, get_coach_defaults_from_coach

    coach_defaults = get_coach_defaults_from_coach(coach_name)
    label = _coach_label(coach_name) or coach_name

    client = frappe.new_doc("Client")
    set_full_name_from_parts(client, {"name1": label, "last_name": ""})

    client_meta = frappe.get_meta("Client")

    if client_meta.has_field("client_type"):
        client.client_type = "Franchise"
    if client_meta.has_field("primary_coach"):
        client.primary_coach = coach_name
    if client_meta.has_field("company") and coach_defaults.get("company"):
        client.company = coach_defaults.get("company")
    if client_meta.has_field("pricelist"):
        client.pricelist = coach_defaults.get("pricelist") or DEFAULT_PRICE_LIST

    client.insert(ignore_permissions=True)

    frappe.db.set_value("Coach", coach_name, "linked_client", client.name)

    return client.name


def _get_or_create_billing_customer(client_name, coach_name):
    """
    _set_invoice_header_fields() (invoices.py) never derives doc.customer
    from doc.custom_client on its own - it has to be passed in directly, the
    same as the app's own "link a Contact as billing contact" flow
    (contact_details.py) sets Client.billing_contact by creating a Customer
    the same way. A freshly auto-created linked_client has neither, so one
    is created here, matching that same convention exactly.
    """
    existing = frappe.db.get_value("Client", client_name, "billing_contact")
    if existing and frappe.db.exists("Customer", existing):
        return existing

    customer_doc = frappe.new_doc("Customer")
    customer_doc.customer_type = "Individual"
    customer_doc.customer_name = _coach_label(coach_name) or coach_name
    customer_doc.insert(ignore_permissions=True)

    if frappe.get_meta("Client").has_field("billing_contact"):
        frappe.db.set_value("Client", client_name, "billing_contact", customer_doc.name)

    return customer_doc.name


def _create_transfer_fee_invoice(transfer):
    """
    Built directly rather than through invoices.submit_invoice() -
    confirmed live that its company/bank-account inference (built around
    "one Client, resolve everything else from it") landed on the wrong
    company and the wrong coach's identity for a pure coach-to-coach fee
    with no real Client behind it. Every field that actually matters here
    (company, bank account, price list, who the income belongs to) is set
    explicitly from the transferring coach's own Coach record instead of
    being inferred from anything.
    """
    transferring_coach = frappe.db.get_value(
        "Coach", transfer.transferring_coach, ["company", "bank_account", "pricelist"], as_dict=True
    ) or {}

    company = transferring_coach.get("company")
    bank_account = transferring_coach.get("bank_account")

    if not company:
        frappe.throw(_(
            "{0} doesn't have a company set on their Coach record - add one before this transfer can be completed."
        ).format(_coach_label(transfer.transferring_coach)))

    if not bank_account:
        frappe.throw(_(
            "{0} doesn't have a bank account set on their Coach record - add one before this transfer can be completed."
        ).format(_coach_label(transfer.transferring_coach)))

    # Still uses the receiving coach's own linked_client/Customer, purely
    # so "Bill To" shows their name and existing permission checks (e.g.
    # Franchise-type clients being invoiceable by any coach) keep working -
    # it plays no part in deciding company/bank account/income owner below.
    receiving_client = _get_or_create_coach_linked_client(transfer.receiving_coach)
    receiving_customer = _get_or_create_billing_customer(receiving_client, transfer.receiving_coach)
    item_code = _ensure_transfer_fee_item()

    invoice = frappe.new_doc("Sales Invoice")
    invoice.customer = receiving_customer
    invoice.company = company
    invoice.posting_date = frappe.utils.nowdate()
    invoice.due_date = frappe.utils.add_days(frappe.utils.nowdate(), 30)
    invoice.selling_price_list = transferring_coach.get("pricelist") or DEFAULT_PRICE_LIST

    meta = invoice.meta

    if meta.has_field("custom_client"):
        invoice.custom_client = receiving_client
    if meta.has_field("set_posting_time"):
        invoice.set_posting_time = 1
    if meta.has_field("custom_bank_account"):
        invoice.custom_bank_account = bank_account
    if meta.has_field("custom_income_owner_coach"):
        invoice.custom_income_owner_coach = transfer.transferring_coach
    if meta.has_field("custom_created_by_coach"):
        invoice.custom_created_by_coach = transfer.transferring_coach
    if meta.has_field("disable_rounded_total"):
        invoice.disable_rounded_total = 1
        invoice.rounding_adjustment = 0
        invoice.base_rounding_adjustment = 0

    naming_series_field = meta.get_field("naming_series")
    if naming_series_field and naming_series_field.options:
        invoice.naming_series = naming_series_field.options.split("\n")[0].strip()

    row = invoice.append("items", {})
    row.item_code = item_code
    row.item_name = TRANSFER_FEE_ITEM_CODE
    row.description = "Client transfer fee - {0} transferred from {1} to {2}".format(
        transfer.client_name,
        _coach_label(transfer.transferring_coach),
        _coach_label(transfer.receiving_coach),
    )
    row.qty = 1
    row.uom = "Nos"
    row.stock_uom = "Nos"
    row.conversion_factor = 1
    row.rate = flt(transfer.transfer_fee_amount) or DEFAULT_TRANSFER_FEE
    row.amount = row.qty * row.rate

    if hasattr(invoice, "set_missing_values"):
        invoice.set_missing_values()
    if hasattr(invoice, "calculate_taxes_and_totals"):
        invoice.calculate_taxes_and_totals()

    invoice.insert(ignore_permissions=True)
    invoice.submit()
    frappe.db.commit()

    return invoice.name


def _transferred_client_for(transfer):
    """
    The real Client record this transfer is about. resolved_client (set
    by link_transfer_to_client below) always wins when present - it
    exists specifically for a transfer whose Client Lead never went
    through the normal conversion flow (a pre-existing client, or
    paperwork backfilled after the fact - confirmed live: Client Lead
    bvm9nd1qnq, a transfer for an existing client, has no converted_client
    at all despite the transfer itself being genuinely Completed and the
    receiving coach already invoicing them). Falls back to the Client
    Lead's own conversion otherwise. None means there's nothing to
    invoice against yet - see _process_invoice_transfer_fee /
    _maybe_invoice_transfer_fee below, both of which treat that as "not
    qualifying yet", not an error.
    """
    if transfer.get("resolved_client"):
        return transfer.get("resolved_client")
    if not transfer.client_lead:
        return None
    return frappe.db.get_value(LEAD_DOCTYPE, transfer.client_lead, "converted_client")


def _maybe_invoice_transfer_fee(transfer, paid_invoice_name, reason):
    """
    Shared by both trigger paths below - actually raises the fee invoice
    once a qualifying paid invoice has been found, best-effort (a billing
    problem, e.g. the transferring coach's Coach record missing a bank
    account, must never block the payment that triggered this - the
    franchisor is notified instead so it doesn't go unnoticed)."""
    try:
        transfer.invoice = _create_transfer_fee_invoice(transfer)
        transfer.append("activity", _log_row(
            f"Transfer fee invoice {transfer.invoice} created ({paid_invoice_name} paid in full by the client at "
            f"{_coach_label(transfer.receiving_coach)}{' - ' + reason if reason else ''})"
        ))
        transfer.save(ignore_permissions=True)
        frappe.db.commit()
        _notify_transfer_fee_invoiced(transfer)
        return True
    except Exception:
        frappe.log_error(frappe.get_traceback(), f"Transfer Fee Invoice Failed On Payment - {transfer.name}")
        _notify_transfer_fee_invoice_failed(transfer)
        return False


def _process_invoice_transfer_fee(invoice_name):
    """
    Payment Entry.on_submit hook target (see hooks.py) - mirrors course_
    unlock_on_payment.py's own pattern exactly: fires for every route an
    invoice can be marked paid (the dashboard's own "mark paid" button or
    a Payment Entry made directly in Desk), deferred into a background
    job so a billing problem here can never block the payment itself
    from recording.

    The SJ-to-Emily transfer fee is deliberately tied to THIS - Emily's
    own invoice to the transferred client actually being paid in full -
    never to the lead converting or the transfer agreement completing on
    their own (see sign_transfer()'s own comment). Per Ashley: Emily
    shouldn't owe SJ anything until the client has actually paid Emily.
    """
    if not frappe.db.exists("Sales Invoice", invoice_name):
        return

    invoice = frappe.db.get_value(
        "Sales Invoice", invoice_name,
        ["custom_client", "custom_created_by_coach", "docstatus", "outstanding_amount", "grand_total"],
        as_dict=True,
    )
    if not invoice or invoice.docstatus != 1:
        return
    if not invoice.custom_client or not invoice.custom_created_by_coach:
        return

    outstanding = payment_utils.get_outstanding_amount_for_payment(
        invoice.outstanding_amount, invoice.grand_total, invoice_name
    )
    if outstanding > 0.01:
        return

    pending_transfers = frappe.get_all(
        TRANSFER_DOCTYPE,
        filters={
            "status": STATUS_COMPLETED,
            "receiving_coach": invoice.custom_created_by_coach,
            "invoice": ["in", ["", None]],
        },
        fields=["name"],
    )

    for row in pending_transfers:
        transfer = frappe.get_doc(TRANSFER_DOCTYPE, row.name)
        if _transferred_client_for(transfer) != invoice.custom_client:
            continue

        # Only one transfer should ever match a given (client, receiving
        # coach) pair - a second, later transfer of the same client back
        # to the same coach is vanishingly unlikely, but stop at the
        # first match regardless rather than invoicing twice for one
        # payment.
        _maybe_invoice_transfer_fee(transfer, invoice_name, reason=None)
        break


def invoice_transfer_fee_on_client_payment(doc, method=None):
    try:
        _invoice_transfer_fee_on_client_payment(doc)
    except Exception:
        frappe.log_error(frappe.get_traceback(), f"Transfer Fee On Payment Failed - {doc.name}")


def _invoice_transfer_fee_on_client_payment(doc):
    if doc.payment_type != "Receive":
        return

    for reference in doc.references or []:
        if reference.reference_doctype != "Sales Invoice" or not reference.reference_name:
            continue

        frappe.enqueue(
            "dashboard.api.shared.client_transfers.process_invoice_transfer_fee",
            queue="short",
            enqueue_after_commit=True,
            invoice_name=reference.reference_name,
        )


def process_invoice_transfer_fee(invoice_name):
    try:
        _process_invoice_transfer_fee(invoice_name)
    except Exception:
        frappe.log_error(frappe.get_traceback(), f"Transfer Fee On Payment Failed - {invoice_name}")


@frappe.whitelist()
def backfill_transfer_fees_for_paid_invoices():
    """
    Franchisor-triggerable, safe to re-run any time - for every Completed
    transfer with no fee invoice yet, checks whether the receiving coach
    already has an invoice to the transferred client that's fully paid
    (e.g. paid before this payment-triggered automation existed, or
    missed because the hook failed for some other reason) and raises the
    fee invoice for any that qualify. Already-invoiced transfers are
    skipped, so this is safe to run as often as needed.
    """
    ensure_office_user()
    return _backfill_transfer_fees_for_paid_invoices()


def _find_qualifying_paid_invoice(client_name, coach_name):
    """The earliest submitted invoice from coach_name to client_name
    that's fully paid - shared by the backfill and link_transfer_to_client
    below, both of which need to answer "has this already happened"."""
    candidate_invoices = frappe.get_all(
        "Sales Invoice",
        filters={"custom_client": client_name, "custom_created_by_coach": coach_name, "docstatus": 1},
        fields=["name", "outstanding_amount", "grand_total"],
        order_by="posting_date asc, creation asc",
    )

    for candidate in candidate_invoices:
        outstanding = payment_utils.get_outstanding_amount_for_payment(
            candidate.outstanding_amount, candidate.grand_total, candidate.name
        )
        if outstanding <= 0.01:
            return candidate.name

    return None


def _clear_stale_transfer_invoice_references():
    """
    A transfer's own invoice field can go stale if the Sales Invoice it
    pointed to was later deleted (e.g. manual cleanup in Desk) - confirmed
    live: 2 of 3 "Leo" transfer fee invoices no longer existed, even
    though their Client Transfer Agreement still listed them, which
    permanently blocked those transfers from ever being reconsidered -
    both the backfill below and the payment hook treat invoice != ""
    as "already done" and never re-check it. Clears invoice back to
    blank on any transfer whose referenced Sales Invoice is gone, so the
    backfill picks it up as pending again right after.
    """
    rows = frappe.get_all(
        TRANSFER_DOCTYPE,
        filters={"invoice": ["is", "set"]},
        fields=["name", "invoice"],
    )

    cleared = []
    for row in rows:
        if row.invoice and not frappe.db.exists("Sales Invoice", row.invoice):
            frappe.db.set_value(TRANSFER_DOCTYPE, row.name, "invoice", None, update_modified=False)
            cleared.append({"transfer": row.name, "stale_invoice": row.invoice})

    if cleared:
        frappe.db.commit()

    return cleared


def _backfill_transfer_fees_for_paid_invoices():
    cleared_stale = _clear_stale_transfer_invoice_references()

    pending_transfers = frappe.get_all(
        TRANSFER_DOCTYPE,
        filters={"status": STATUS_COMPLETED, "invoice": ["in", ["", None]]},
        fields=["name"],
    )

    invoiced = []
    for row in pending_transfers:
        transfer = frappe.get_doc(TRANSFER_DOCTYPE, row.name)

        client_name = _transferred_client_for(transfer)
        if not client_name:
            continue

        paid_invoice_name = _find_qualifying_paid_invoice(client_name, transfer.receiving_coach)
        if not paid_invoice_name:
            continue

        if _maybe_invoice_transfer_fee(transfer, paid_invoice_name, reason="backfill"):
            invoiced.append(transfer.name)

    return {"checked": len(pending_transfers), "invoiced": invoiced, "cleared_stale_invoice_references": cleared_stale}


@frappe.whitelist()
def link_transfer_to_client(transfer=None, client=None):
    """
    Franchisor-only: sets resolved_client on a Completed transfer whose
    Client Lead never converted normally (see _transferred_client_for's
    own docstring) - confirmed live via explain_transfer_fee_status as
    the actual blocker for at least one real transfer (a transfer for an
    existing client, not one that came through the Lead pipeline).
    Immediately checks for an already-qualifying paid invoice and raises
    the fee invoice right away if one exists, same as the backfill does,
    rather than waiting for the next payment.
    """
    ensure_office_user()

    transfer = coalesce_str("transfer", transfer)
    client = coalesce_str("client", client)

    if not transfer or not frappe.db.exists(TRANSFER_DOCTYPE, transfer):
        frappe.throw(_("Transfer agreement not found."))
    if not client or not frappe.db.exists("Client", client):
        frappe.throw(_("Client not found."))

    doc = frappe.get_doc(TRANSFER_DOCTYPE, transfer)

    if doc.invoice and not frappe.db.exists("Sales Invoice", doc.invoice):
        doc.invoice = None

    doc.resolved_client = client
    doc.append("activity", _log_row(f"Linked to Client {client} by {get_fullname(frappe.session.user) or frappe.session.user} (its Client Lead never converted normally)"))
    doc.save(ignore_permissions=True)
    frappe.db.commit()

    if doc.invoice:
        return {"ok": True, "resolved_client": client, "invoiced": False, "note": "Fee invoice already existed."}

    if doc.status != STATUS_COMPLETED:
        return {"ok": True, "resolved_client": client, "invoiced": False, "note": "Transfer isn't Completed yet - nothing to invoice until it is."}

    paid_invoice_name = _find_qualifying_paid_invoice(client, doc.receiving_coach)
    if not paid_invoice_name:
        return {"ok": True, "resolved_client": client, "invoiced": False, "note": "No fully-paid invoice from the receiving coach to this client yet."}

    invoiced = _maybe_invoice_transfer_fee(doc, paid_invoice_name, reason="linked to client by hand")
    return {"ok": True, "resolved_client": client, "invoiced": invoiced, "invoice": doc.invoice or None}


@frappe.whitelist()
def explain_transfer_fee_status(transfer=None, client_name=None):
    """
    Franchisor-only diagnostic, read-only - says exactly why a given
    Client Transfer Agreement's fee invoice hasn't been raised yet (or
    confirms it has), rather than leaving "nothing happened" to guess at.
    Pass either `transfer` (the agreement's own record name) directly, or
    `client_name` to search for it first, same substring match as
    find_client_leads - if that matches more than one transfer, returns
    the list so the right one can be re-run via `transfer` instead.
    """
    ensure_office_user()

    transfer = coalesce_str("transfer", transfer)
    client_name = coalesce_str("client_name", client_name)

    if not transfer:
        if not client_name:
            frappe.throw(_("Provide either transfer or client_name."))

        matches = frappe.get_all(
            TRANSFER_DOCTYPE,
            filters={"client_name": ["like", f"%{client_name}%"]},
            fields=["name", "client_name", "transferring_coach", "receiving_coach", "status", "invoice"],
        )
        if not matches:
            frappe.throw(_("No Client Transfer Agreement found matching \"{0}\".").format(client_name))
        if len(matches) > 1:
            return {"matches": matches}
        transfer = matches[0]["name"]

    if not frappe.db.exists(TRANSFER_DOCTYPE, transfer):
        frappe.throw(_("Transfer agreement not found."))

    doc = frappe.get_doc(TRANSFER_DOCTYPE, transfer)

    invoice_is_stale = bool(doc.invoice) and not frappe.db.exists("Sales Invoice", doc.invoice)

    result = {
        "transfer": doc.name,
        "client_name": doc.client_name,
        "transferring_coach": _coach_label(doc.transferring_coach),
        "receiving_coach": _coach_label(doc.receiving_coach),
        "status": doc.status,
        "invoice": None if invoice_is_stale else (doc.invoice or None),
    }

    if invoice_is_stale:
        result["explanation"] = (
            "This transfer's own invoice field points at {0}, but that Sales Invoice no longer exists (likely "
            "deleted) - call backfill_transfer_fees_for_paid_invoices to clear the stale reference and "
            "reconsider this transfer."
        ).format(doc.invoice)
        return result

    if doc.invoice:
        result["explanation"] = "Fee invoice already raised - {0}.".format(doc.invoice)
        return result

    if doc.status != STATUS_COMPLETED:
        result["explanation"] = (
            "Transfer agreement is not yet Completed (currently {0}) - every signature is needed before any "
            "fee can be invoiced."
        ).format(doc.status)
        return result

    converted_client = _transferred_client_for(doc)
    if not converted_client:
        result["explanation"] = (
            "The linked Client Lead ({0}) hasn't converted to a Client yet (or has no converted_client "
            "recorded on it) - there's no actual Client record yet for {1}'s invoices to this person to match "
            "against. If this is actually an existing client (the Lead never went through the normal "
            "conversion flow), call link_transfer_to_client with this transfer's name and the real Client "
            "record to fix it."
        ).format(doc.client_lead, result["receiving_coach"])
        return result

    result["converted_client"] = converted_client

    candidate_invoices = frappe.get_all(
        "Sales Invoice",
        filters={"custom_client": converted_client, "custom_created_by_coach": doc.receiving_coach, "docstatus": 1},
        fields=["name", "outstanding_amount", "grand_total", "status"],
        order_by="posting_date asc, creation asc",
    )

    if not candidate_invoices:
        result["explanation"] = (
            "No submitted invoice from {0} to this client ({1}) yet - either {0} hasn't invoiced them, or the "
            "invoice exists but isn't tagged as created by {0} (custom_created_by_coach), which this match "
            "depends on."
        ).format(result["receiving_coach"], converted_client)
        return result

    result["candidate_invoices"] = [
        {"name": row.name, "outstanding_amount": row.outstanding_amount, "grand_total": row.grand_total, "status": row.status}
        for row in candidate_invoices
    ]

    paid = [
        row for row in candidate_invoices
        if payment_utils.get_outstanding_amount_for_payment(row.outstanding_amount, row.grand_total, row.name) <= 0.01
    ]

    if not paid:
        result["explanation"] = (
            "{0} has {1} submitted invoice(s) to this client, but none are fully paid yet - the fee will be "
            "invoiced automatically the moment one is."
        ).format(result["receiving_coach"], len(candidate_invoices))
        return result

    result["explanation"] = (
        "{0} is fully paid - this should already have raised the fee invoice automatically. Call "
        "backfill_transfer_fees_for_paid_invoices to retry it now, or check the Error Log for "
        "'Transfer Fee Invoice Failed On Payment - {1}' to see why it failed."
    ).format(paid[0].name, doc.name)
    return result


# =====================================================
# API
# =====================================================

@frappe.whitelist()
def create_transfer(lead=None, receiving_coach=None, effective_transfer_date=None, reason_for_transfer=None, transfer_fee_amount=None):
    ensure_logged_in()

    lead = coalesce_str("lead", lead)
    receiving_coach = coalesce_str("receiving_coach", receiving_coach)

    if not lead or not frappe.db.exists(LEAD_DOCTYPE, lead):
        frappe.throw(_("Lead not found."))

    if not receiving_coach or not frappe.db.exists("Coach", receiving_coach):
        frappe.throw(_("Please choose a coach to transfer this lead to."))

    lead_doc = frappe.get_doc(LEAD_DOCTYPE, lead)
    transferring_coach = lead_doc.coach

    if not transferring_coach:
        frappe.throw(_("This lead has no coach to transfer from."))

    if receiving_coach == transferring_coach:
        frappe.throw(_("Choose a different coach to transfer this lead to."))

    current_coach = _current_coach_name()
    if not is_franchisor_user() and current_coach != transferring_coach:
        frappe.throw(_("You can only transfer your own leads."), frappe.PermissionError)

    if lead_doc.get("active_transfer") and frappe.db.exists(TRANSFER_DOCTYPE, lead_doc.active_transfer):
        existing_status = frappe.db.get_value(TRANSFER_DOCTYPE, lead_doc.active_transfer, "status")
        if existing_status in OPEN_STATUSES:
            frappe.throw(_("This lead already has a transfer agreement in progress."))

    requires_franchisor = not (_is_franchisor_coach(transferring_coach) or _is_franchisor_coach(receiving_coach))

    transfer = frappe.new_doc(TRANSFER_DOCTYPE)
    transfer.client_lead = lead
    transfer.client_name = lead_doc.client_name
    transfer.transferring_coach = transferring_coach
    transfer.receiving_coach = receiving_coach
    transfer.agreement_date = frappe.utils.nowdate()
    transfer.effective_transfer_date = coalesce_str("effective_transfer_date", effective_transfer_date) or frappe.utils.nowdate()
    transfer.reason_for_transfer = coalesce_str("reason_for_transfer", reason_for_transfer)
    transfer.transfer_fee_amount = flt(coalesce_raw("transfer_fee_amount", transfer_fee_amount)) or DEFAULT_TRANSFER_FEE
    transfer.requires_franchisor_signature = 1 if requires_franchisor else 0
    transfer.status = STATUS_AWAITING_RECEIVING
    transfer.append("activity", _log_row(
        "Created by {0} - {1} to {2}".format(
            get_fullname(frappe.session.user) or frappe.session.user,
            _coach_label(transferring_coach),
            _coach_label(receiving_coach),
        )
    ))
    transfer.insert(ignore_permissions=True)

    frappe.db.set_value(LEAD_DOCTYPE, lead, "active_transfer", transfer.name)
    frappe.db.commit()

    _notify_next_signer(transfer)

    return {"ok": True, "name": transfer.name, "sign_url": _sign_url(transfer.name)}


def _search_client_leads(query):
    """
    Word-by-word, case-insensitive match against BOTH client_name and
    contact_name (client_name alone missed "Doug Sale" live - turned out
    not to matter why; a contact/guardian name search or a different
    word order would hit the same wall) - every word in `query` must
    appear somewhere in one of those two fields, in any order, rather
    than requiring the exact phrase as a single substring.
    """
    words = [w for w in (query or "").strip().split() if w]
    if not words:
        return []

    filters = []
    for word in words:
        filters.append([LEAD_DOCTYPE, "client_name", "like", f"%{word}%"])

    name_matches = {row.name: row for row in frappe.get_all(
        LEAD_DOCTYPE, filters=filters, fields=["name", "client_name", "contact_name", "coach", "status"],
    )}

    contact_filters = [[LEAD_DOCTYPE, "contact_name", "like", f"%{word}%"] for word in words]
    for row in frappe.get_all(
        LEAD_DOCTYPE, filters=contact_filters, fields=["name", "client_name", "contact_name", "coach", "status"],
    ):
        name_matches[row.name] = row

    return [dict(row) for row in name_matches.values()]


@frappe.whitelist()
def find_client_leads(query=None):
    """
    Franchisor-only diagnostic search - read-only, changes nothing. Use
    this when backfill_client_transfer (or anything else taking a
    client_name) can't find a match, to see what's actually on file
    before guessing at spelling/word order.
    """
    if not is_franchisor_user():
        frappe.throw(_("You do not have permission to do this."), frappe.PermissionError)

    query = coalesce_str("query", query)
    if not query:
        frappe.throw(_("Provide a query (part of the client's or contact's name)."))

    return {"matches": _search_client_leads(query)}


@frappe.whitelist()
def backfill_client_transfer(
    lead=None, client_name=None, transferring_coach=None, receiving_coach=None,
    effective_transfer_date=None, reason_for_transfer=None,
):
    """
    Franchisor-only one-off: starts a REAL Client Transfer Agreement for a
    transfer that already took effect manually (the Client Lead's coach
    field was moved by hand) before this automation existed - so the two
    coaches involved can give genuine signatures and have real IP
    addresses captured, same as any live transfer, rather than a
    synthetic record with blank signature fields pretending they signed
    something they never saw.

    Deliberately does NOT touch Client Lead.coach at all (unlike
    create_transfer(), which derives transferring_coach from it) -
    receiving_coach must already match the lead's current coach (asserted
    below), so there's nothing to flip back and forth. That matters: if
    the receiving coach has already been working this client for a while
    (appointments held, things allocated to them), briefly moving the
    coach field away and back to trigger the normal "Reassign To" UI
    flow risks disrupting whatever's keyed off it in the meantime. This
    skips that entirely - transferring_coach/receiving_coach are passed
    in directly, the agreement is created straight in "Awaiting Receiving
    Coach" with the SAME notify/sign/complete path create_transfer() and
    sign_transfer() already use (Client Lead.active_transfer is set for
    the duration, which only shows a banner and disables the Coach
    dropdown on the Lead Details page - nothing appointment- or
    invoice-related reads it). On completion, Client Lead.coach is set to
    receiving_coach same as any transfer - a no-op here since it's
    already that value - and the transfer fee invoice is raised
    automatically, same as any transfer, once the receiving coach's own
    first invoice to this client is paid in full (see
    invoice_transfer_fee_on_client_payment). If that's already happened
    in the past (this is backfilled paperwork for a transfer that took
    effect a while ago), run backfill_transfer_fees_for_paid_invoices
    afterwards to catch it up.

    `lead` identifies the Client Lead directly if known; otherwise
    `client_name` is matched (case-insensitive substring) against
    Client Lead.client_name - it must resolve to exactly one record, or
    this throws listing every match so the right one can be re-run via
    `lead` instead. transferring_coach has no default and must be given
    explicitly, since nothing on the lead remembers who it was
    transferred from; receiving_coach must be given too, and is checked
    against the lead's current coach as a safety rail against pointing
    this at the wrong client.
    """
    if not is_franchisor_user():
        frappe.throw(_("You do not have permission to do this."), frappe.PermissionError)

    lead = coalesce_str("lead", lead)
    client_name = coalesce_str("client_name", client_name)

    if not lead:
        if not client_name:
            frappe.throw(_("Provide either lead or client_name."))

        matches = _search_client_leads(client_name)
        if not matches:
            frappe.throw(_(
                "No Client Lead found matching \"{0}\" (checked both client name and contact name). "
                "Try find_client_leads?query=... with just part of the name to see what's actually on file, "
                "then pass the exact record via `lead`."
            ).format(client_name))
        if len(matches) > 1:
            frappe.throw(_("Multiple Client Leads match \"{0}\" - pass the exact one via `lead` instead: {1}").format(
                client_name, ", ".join(f"{m['name']} ({m['client_name']}, {m['coach']}, {m['status']})" for m in matches)
            ))
        lead = matches[0]["name"]

    if not frappe.db.exists(LEAD_DOCTYPE, lead):
        frappe.throw(_("Lead not found."))

    lead_doc = frappe.get_doc(LEAD_DOCTYPE, lead)

    transferring_coach = _resolve_coach(coalesce_str("transferring_coach", transferring_coach))
    receiving_coach = _resolve_coach(coalesce_str("receiving_coach", receiving_coach))

    if not transferring_coach:
        frappe.throw(_("Transferring coach not found - pass their name, login email, or Coach record name via transferring_coach."))
    if not receiving_coach:
        frappe.throw(_("Receiving coach not found - pass their name, login email, or Coach record name via receiving_coach."))
    if receiving_coach == transferring_coach:
        frappe.throw(_("Transferring and receiving coach can't be the same."))

    if lead_doc.coach != receiving_coach:
        frappe.throw(_(
            "This lead's current coach ({0}) doesn't match receiving_coach ({1}) - "
            "double-check you have the right client before starting this."
        ).format(_coach_label(lead_doc.coach) or lead_doc.coach, _coach_label(receiving_coach)))

    if lead_doc.get("active_transfer") and frappe.db.exists(TRANSFER_DOCTYPE, lead_doc.active_transfer):
        existing_status = frappe.db.get_value(TRANSFER_DOCTYPE, lead_doc.active_transfer, "status")
        if existing_status in OPEN_STATUSES:
            frappe.throw(_("This lead already has a transfer agreement in progress: {0}").format(lead_doc.active_transfer))

    effective_transfer_date = coalesce_raw("effective_transfer_date", effective_transfer_date)
    if not effective_transfer_date:
        frappe.throw(_("Provide effective_transfer_date (the date the transfer actually took effect)."))
    effective_transfer_date = frappe.utils.getdate(effective_transfer_date)

    requires_franchisor = not (_is_franchisor_coach(transferring_coach) or _is_franchisor_coach(receiving_coach))

    transfer = frappe.new_doc(TRANSFER_DOCTYPE)
    transfer.client_lead = lead
    transfer.client_name = lead_doc.client_name
    transfer.transferring_coach = transferring_coach
    transfer.receiving_coach = receiving_coach
    transfer.agreement_date = frappe.utils.nowdate()
    transfer.effective_transfer_date = effective_transfer_date
    transfer.reason_for_transfer = (
        coalesce_str("reason_for_transfer", reason_for_transfer)
        or "Backfilled paperwork - this transfer already took effect on {0}, before this automation existed. "
           "Signatures below are real, collected now.".format(effective_transfer_date)
    )
    transfer.transfer_fee_amount = DEFAULT_TRANSFER_FEE
    transfer.requires_franchisor_signature = 1 if requires_franchisor else 0
    transfer.status = STATUS_AWAITING_RECEIVING
    transfer.append("activity", _log_row(
        "Backfill started by {0} - see Reason for Transfer for details.".format(
            get_fullname(frappe.session.user) or frappe.session.user,
        )
    ))
    transfer.insert(ignore_permissions=True)

    frappe.db.set_value(LEAD_DOCTYPE, lead, "active_transfer", transfer.name)
    frappe.db.commit()

    _notify_next_signer(transfer)

    return {"ok": True, "transfer": transfer.name, "sign_url": _sign_url(transfer.name)}


@frappe.whitelist()
def get_transfer_for_signing(name=None):
    ensure_logged_in()

    name = coalesce_str("name", name)
    if not name or not frappe.db.exists(TRANSFER_DOCTYPE, name):
        frappe.throw(_("Transfer agreement not found."))

    transfer = frappe.get_doc(TRANSFER_DOCTYPE, name)
    role = _current_signer_role(transfer)

    if not role and not is_franchisor_user():
        frappe.throw(_("You do not have permission to view this transfer agreement."), frappe.PermissionError)

    expected_role = _expected_role_for_status(transfer.status)
    can_act = bool(role) and role == expected_role and transfer.status in OPEN_STATUSES
    lead_fields = _lead_document_fields(transfer.client_lead)

    return {
        "name": transfer.name,
        "status": transfer.status,
        "client_name": transfer.client_name,
        "transferring_coach": transfer.transferring_coach,
        "transferring_coach_label": _coach_label(transfer.transferring_coach),
        "transferring_coach_territory": _coach_territory(transfer.transferring_coach),
        "receiving_coach": transfer.receiving_coach,
        "receiving_coach_label": _coach_label(transfer.receiving_coach),
        "receiving_coach_territory": _coach_territory(transfer.receiving_coach),
        "effective_transfer_date": str(transfer.effective_transfer_date or ""),
        "agreement_date": str(transfer.agreement_date or ""),
        "reason_for_transfer": transfer.reason_for_transfer or "",
        "transfer_fee_amount": transfer.transfer_fee_amount or 0,
        "parent_guardian_name": lead_fields["parent_guardian_name"],
        "date_first_registered": lead_fields["date_first_registered"],
        "client_reference": lead_fields["client_reference"],
        "requires_franchisor_signature": bool(transfer.requires_franchisor_signature),
        "receiving_signed_by": transfer.receiving_signed_by or "",
        "receiving_signed_on": str(transfer.receiving_signed_on or ""),
        "receiving_signature": transfer.receiving_signature or "",
        "franchisor_signed_by": transfer.franchisor_signed_by or "",
        "franchisor_signed_on": str(transfer.franchisor_signed_on or ""),
        "franchisor_signature": transfer.franchisor_signature or "",
        "transferring_signed_by": transfer.transferring_signed_by or "",
        "transferring_signed_on": str(transfer.transferring_signed_on or ""),
        "transferring_signature": transfer.transferring_signature or "",
        "invoice": transfer.invoice or "",
        "declined_by": transfer.declined_by or "",
        "declined_reason": transfer.declined_reason or "",
        "activity": [
            {
                "timestamp": str(row.timestamp or ""),
                "event": row.event or "",
                "user": row.user or "",
                "ip_address": row.ip_address or "",
            }
            for row in (transfer.activity or [])
        ],
        "current_user_role": role or "",
        "can_sign": can_act,
        "can_decline": can_act,
    }


@frappe.whitelist()
def sign_transfer(name=None, signature=None):
    ensure_logged_in()

    name = coalesce_str("name", name)
    signature = coalesce_str("signature", signature)

    if not signature or not signature.startswith("data:image"):
        frappe.throw(_("Please draw your signature before continuing."))

    if not name or not frappe.db.exists(TRANSFER_DOCTYPE, name):
        frappe.throw(_("Transfer agreement not found."))

    transfer = frappe.get_doc(TRANSFER_DOCTYPE, name)

    if transfer.status not in OPEN_STATUSES:
        frappe.throw(_("This transfer agreement has already been finalised."))

    role = _current_signer_role(transfer)
    expected_role = _expected_role_for_status(transfer.status)

    if not role or role != expected_role:
        frappe.throw(_("It's not your turn to sign this agreement yet."), frappe.PermissionError)

    signer_name = get_fullname(frappe.session.user) or frappe.session.user
    now = now_datetime()

    transfer.set(f"{role}_signature", signature)
    transfer.set(f"{role}_signed_by", signer_name)
    transfer.set(f"{role}_signed_on", now)
    transfer.set(f"{role}_signed_ip", getattr(frappe.local, "request_ip", "") or "")
    transfer.append("activity", _log_row(f"Signed by {signer_name} ({role})"))

    if transfer.status == STATUS_AWAITING_RECEIVING:
        new_status = STATUS_AWAITING_FRANCHISOR if transfer.requires_franchisor_signature else STATUS_AWAITING_TRANSFERRING
    elif transfer.status == STATUS_AWAITING_FRANCHISOR:
        new_status = STATUS_AWAITING_TRANSFERRING
    else:
        new_status = STATUS_COMPLETED

    transfer.status = new_status

    if new_status == STATUS_COMPLETED:
        # The transfer fee is deliberately NOT invoiced here, and never on
        # the lead converting to a Client either - per Ashley, Emily
        # shouldn't owe SJ anything until the client has actually paid
        # Emily. See invoice_transfer_fee_on_client_payment (Payment
        # Entry.on_submit hook, hooks.py): it's raised automatically the
        # moment the receiving coach's own first invoice to this client
        # is paid in full.
        transfer.append("activity", _log_row(
            "Transfer completed - fee will be invoiced once the client's first invoice at the new coach is paid in full"
        ))

    transfer.save(ignore_permissions=True)
    frappe.db.commit()

    if new_status == STATUS_COMPLETED:
        lead_doc = frappe.get_doc(LEAD_DOCTYPE, transfer.client_lead)
        lead_doc.coach = transfer.receiving_coach
        lead_doc.active_transfer = None
        lead_doc.save(ignore_permissions=True)
        frappe.db.commit()

        _notify_transfer_completed(transfer)
    else:
        _notify_next_signer(transfer)

    return {"ok": True, "status": transfer.status}


@frappe.whitelist()
def decline_transfer(name=None, reason=None):
    ensure_logged_in()

    name = coalesce_str("name", name)
    reason = coalesce_str("reason", reason)

    if not name or not frappe.db.exists(TRANSFER_DOCTYPE, name):
        frappe.throw(_("Transfer agreement not found."))

    transfer = frappe.get_doc(TRANSFER_DOCTYPE, name)

    if transfer.status not in OPEN_STATUSES:
        frappe.throw(_("This transfer agreement has already been finalised."))

    role = _current_signer_role(transfer)
    expected_role = _expected_role_for_status(transfer.status)

    if not role or role != expected_role:
        frappe.throw(_("It's not your turn to act on this agreement."), frappe.PermissionError)

    signer_name = get_fullname(frappe.session.user) or frappe.session.user

    transfer.status = STATUS_DECLINED
    transfer.declined_by = signer_name
    transfer.declined_reason = reason or ""
    transfer.append("activity", _log_row(
        f"Declined by {signer_name} ({role})" + (f": {reason}" if reason else "")
    ))
    transfer.save(ignore_permissions=True)

    frappe.db.set_value(LEAD_DOCTYPE, transfer.client_lead, "active_transfer", None)
    frappe.db.commit()

    _notify_transfer_declined(transfer)

    return {"ok": True}
