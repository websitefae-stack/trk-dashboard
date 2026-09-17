import frappe
from frappe import _
from frappe.utils import now_datetime, get_url, get_fullname, flt

from dashboard.api.shared.permissions import ensure_logged_in, is_franchisor_user, get_current_coach_name
from dashboard.api.shared.utils import coalesce_str, coalesce_raw
from dashboard.api.shared.notifications import create_trk_notification, FRANCHISOR_USERS
from dashboard.api.shared.item_access import _get_coach_login
from dashboard.api.shared import invoices as invoices_api


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
        message = "A Client Transfer Agreement for {0} needs your signature.".format(transfer.client_name)
        for user in FRANCHISOR_USERS:
            try:
                create_trk_notification(
                    recipient_user=user,
                    notification_type="Task",
                    message=message,
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

    item_group = frappe.db.get_value("Item Group", {"is_group": 0}, "name") or "All Item Groups"

    item = frappe.new_doc("Item")
    item.item_code = TRANSFER_FEE_ITEM_CODE
    item.item_name = TRANSFER_FEE_ITEM_CODE
    item.item_group = item_group
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
    from dashboard.api.shared.item_access import DEFAULT_PRICE_LIST

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
    bank_account = frappe.db.get_value("Coach", transfer.transferring_coach, "bank_account")

    if not bank_account:
        frappe.throw(_(
            "{0} doesn't have a bank account set on their Coach record - add one before this transfer can be completed."
        ).format(_coach_label(transfer.transferring_coach)))

    receiving_client = _get_or_create_coach_linked_client(transfer.receiving_coach)
    receiving_customer = _get_or_create_billing_customer(receiving_client, transfer.receiving_coach)
    item_code = _ensure_transfer_fee_item()

    payload = {
        "custom_client": receiving_client,
        "customer": receiving_customer,
        "bank_account": bank_account,
        "posting_date": frappe.utils.nowdate(),
        "items": [{
            "item_code": item_code,
            "qty": 1,
            "rate": flt(transfer.transfer_fee_amount) or DEFAULT_TRANSFER_FEE,
            "description": "Client transfer fee - {0} transferred from {1} to {2}".format(
                transfer.client_name,
                _coach_label(transfer.transferring_coach),
                _coach_label(transfer.receiving_coach),
            ),
        }],
    }

    result = invoices_api.submit_invoice(docname=None, data=payload)
    return result.get("name")


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

    return {
        "name": transfer.name,
        "status": transfer.status,
        "client_name": transfer.client_name,
        "transferring_coach": transfer.transferring_coach,
        "transferring_coach_label": _coach_label(transfer.transferring_coach),
        "receiving_coach": transfer.receiving_coach,
        "receiving_coach_label": _coach_label(transfer.receiving_coach),
        "effective_transfer_date": str(transfer.effective_transfer_date or ""),
        "agreement_date": str(transfer.agreement_date or ""),
        "reason_for_transfer": transfer.reason_for_transfer or "",
        "transfer_fee_amount": transfer.transfer_fee_amount or 0,
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
        # Raised (and committed) before this doc is saved - if it throws
        # (e.g. the transferring coach has no bank account on file), the
        # signature itself is never persisted, so they can fix the problem
        # and sign again rather than the agreement silently completing
        # with no invoice.
        transfer.invoice = _create_transfer_fee_invoice(transfer)
        transfer.append("activity", _log_row(f"Transfer fee invoice {transfer.invoice} created"))

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
