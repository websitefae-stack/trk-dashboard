"""
Franchisor-facing "School License" admin - lets Ashley/office grant
School Dashboard portal access to a Client (client_type "School")
without going into Desk and hand-editing the Customer record that
backs it. Every field here already exists - client_portal's own
"Portal Organisation" layer on Customer (is_portal_organisation,
organisation_type, assigned_account_manager, portal_active,
licence_type/_start/_end, number_of_seats, seats_used - see that app's
own add_organisation_fields_to_customer.py and README for the full
design). This module is purely a friendlier way to set those fields,
resolving the Client -> Customer link via billing_contact (same chain
client_transfers.py's own _get_or_create_billing_customer walks for a
coach) rather than requiring a Customer to be picked or created by
hand in Desk.

Read/write Customer's organisation fields directly via frappe.db/
frappe.get_doc rather than importing anything from client_portal -
this app has no Python dependency on it, only the reverse (see that
app's own README) - exactly the same reasoning resilient_domains'
login_redirect.py already uses for its own Organisation Membership
check.

The one hard rule this was built around: a school can only ever be
added here by picking an existing Client (client_type "School") - never
typed in freehand, never a new Customer/organisation created from
scratch.
"""

import frappe
from frappe import _

from dashboard.api.shared.permissions import ensure_logged_in, is_franchisor_user

CLIENT_DOCTYPE = "Client"
CUSTOMER_DOCTYPE = "Customer"
SCHOOL_CLIENT_TYPE = "School"

ORGANISATION_FIELDS = [
    "is_portal_organisation", "organisation_type", "assigned_account_manager",
    "portal_active", "licence_type", "licence_start", "licence_end",
    "number_of_seats", "seats_used",
]


def _ensure_franchisor():
    ensure_logged_in()
    if not is_franchisor_user():
        frappe.throw(_("Only the franchisor can manage school licenses."), frappe.PermissionError)


def _organisation_fields_available():
    return frappe.get_meta(CUSTOMER_DOCTYPE).has_field("is_portal_organisation")


def _client_display(client_doc):
    from dashboard.api.shared.dashboard import _get_client_display

    return _get_client_display(client_doc.as_dict()) or client_doc.name


def _get_or_create_customer_for_client(client_name):
    """Same Client -> Customer billing_contact chain used everywhere else
    a Client needs a billing identity (see client_transfers.py's own
    _get_or_create_billing_customer) - creates one only if this Client
    genuinely has none yet, never touches an existing one beyond
    linking it."""
    existing = frappe.db.get_value(CLIENT_DOCTYPE, client_name, "billing_contact")
    if existing and frappe.db.exists(CUSTOMER_DOCTYPE, existing):
        return existing

    client_doc = frappe.get_doc(CLIENT_DOCTYPE, client_name)

    customer_doc = frappe.new_doc(CUSTOMER_DOCTYPE)
    customer_doc.customer_type = "Company"
    customer_doc.customer_name = _client_display(client_doc)
    customer_doc.insert(ignore_permissions=True)

    if frappe.get_meta(CLIENT_DOCTYPE).has_field("billing_contact"):
        frappe.db.set_value(CLIENT_DOCTYPE, client_name, "billing_contact", customer_doc.name)

    return customer_doc.name


@frappe.whitelist()
def get_school_client_options():
    """Every Client of type School, for the "+ Add School License"
    picker - the one hard rule: a school can only be added by selecting
    one of these, never typed in freehand. Flags which ones already
    have a license set up, so the picker can grey those out rather than
    risk creating a confusing second Customer for the same school."""
    _ensure_franchisor()

    if not frappe.db.exists("DocType", CLIENT_DOCTYPE):
        return []

    meta = frappe.get_meta(CLIENT_DOCTYPE)
    if not meta.has_field("client_type"):
        return []

    from dashboard.api.shared.dashboard import _get_client_display_name

    rows = frappe.get_all(
        CLIENT_DOCTYPE,
        filters={"client_type": SCHOOL_CLIENT_TYPE},
        fields=["name", "billing_contact"],
        order_by="creation desc",
    )

    org_flags = {}
    if rows and _organisation_fields_available():
        customer_names = [row.billing_contact for row in rows if row.billing_contact]
        if customer_names:
            org_flags = {
                c.name: bool(c.is_portal_organisation)
                for c in frappe.get_all(
                    CUSTOMER_DOCTYPE, filters={"name": ["in", customer_names]},
                    fields=["name", "is_portal_organisation"],
                )
            }

    options = [
        {
            "name": row.name,
            "client_name": _get_client_display_name(row.name),
            "already_licensed": org_flags.get(row.billing_contact, False),
        }
        for row in rows
    ]
    options.sort(key=lambda option: option["client_name"].lower())
    return options


def _primary_contact_for_organisation(customer):
    """The one person who can invite the rest of a school's own staff
    (can_manage_users=1) - raw queries against client_portal's own
    doctypes rather than a Python import, same reasoning as everywhere
    else in this module. Prefers an already-Active membership; falls
    back to a still-pending Portal Invitation so a franchisor granting
    a license can see "invited, not yet accepted" rather than nothing."""
    if not frappe.db.exists("DocType", "Organisation Membership"):
        return None

    active = frappe.db.get_value(
        "Organisation Membership",
        {"organisation": customer, "can_manage_users": 1, "membership_status": "Active"},
        ["email", "user"], as_dict=True, order_by="creation asc",
    )
    if active:
        return {"email": active.email or active.user or "", "status": "Active"}

    if not frappe.db.exists("DocType", "Portal Invitation"):
        return None

    invited = frappe.db.get_value(
        "Portal Invitation",
        {"invitation_type": "Organisation Membership", "organisation": customer, "status": "Sent"},
        "email", order_by="creation desc",
    )
    if invited:
        return {"email": invited, "status": "Invited"}

    return None


@frappe.whitelist()
def get_school_licenses():
    """Every Client currently flagged as a School Portal Organisation -
    the franchisor's management list."""
    _ensure_franchisor()

    if not _organisation_fields_available():
        return []

    customers = frappe.get_all(
        CUSTOMER_DOCTYPE,
        filters={"is_portal_organisation": 1, "organisation_type": SCHOOL_CLIENT_TYPE},
        fields=["name", "customer_name", *ORGANISATION_FIELDS],
        order_by="customer_name asc",
    )

    if not customers:
        return []

    from dashboard.api.shared.dashboard import _get_client_display_name

    client_by_customer = {
        row.billing_contact: row
        for row in frappe.get_all(
            CLIENT_DOCTYPE, filters={"billing_contact": ["in", [c.name for c in customers]]},
            fields=["name", "billing_contact"],
        )
    }

    results = []
    for customer in customers:
        client = client_by_customer.get(customer.name)
        contact = _primary_contact_for_organisation(customer.name)
        results.append({
            "customer": customer.name,
            "client": client.name if client else "",
            "client_name": (_get_client_display_name(client.name) if client else "") or customer.customer_name,
            "account_manager": customer.assigned_account_manager or "",
            "portal_active": bool(customer.portal_active),
            "licence_type": customer.licence_type or "",
            "licence_start": str(customer.licence_start or ""),
            "licence_end": str(customer.licence_end or ""),
            "number_of_seats": customer.number_of_seats or 0,
            "seats_used": customer.seats_used or 0,
            "primary_contact_email": contact["email"] if contact else "",
            "primary_contact_status": contact["status"] if contact else "",
        })

    return results


@frappe.whitelist()
def save_school_license(
    client=None, account_manager=None, portal_active=1,
    licence_type=None, licence_start=None, licence_end=None, number_of_seats=None,
):
    """Creates or updates the School License for a Client. `client` must
    already be a real Client record of type School - nothing here ever
    creates a school from scratch, only resolves/creates the Customer
    that backs an already-real Client."""
    _ensure_franchisor()

    client = (client or "").strip()
    if not client or not frappe.db.exists(CLIENT_DOCTYPE, client):
        frappe.throw(_("Choose a school from the Client list first."))

    client_doc = frappe.get_doc(CLIENT_DOCTYPE, client)
    if (client_doc.get("client_type") or "") != SCHOOL_CLIENT_TYPE:
        frappe.throw(_("This client isn't a School - the license picker should only ever offer School clients."))

    customer_name = _get_or_create_customer_for_client(client)
    customer = frappe.get_doc(CUSTOMER_DOCTYPE, customer_name)

    customer.is_portal_organisation = 1
    customer.organisation_type = SCHOOL_CLIENT_TYPE
    customer.assigned_account_manager = (account_manager or "").strip() or None
    customer.portal_active = 1 if int(portal_active or 0) else 0
    customer.licence_type = (licence_type or "").strip()
    customer.licence_start = licence_start or None
    customer.licence_end = licence_end or None
    customer.number_of_seats = int(number_of_seats) if str(number_of_seats or "").strip() else 0

    customer.save(ignore_permissions=True)
    frappe.db.commit()

    return {"ok": True, "customer": customer.name}


@frappe.whitelist()
def set_school_license_active(customer=None, active=1):
    """Soft on/off switch only - never deletes the organisation or its
    staff memberships, same non-destructive "kill switch" pattern
    client_portal's own is_organisation_portal_active() already relies
    on (a lapsed/paused school keeps its history, just loses live
    portal access)."""
    _ensure_franchisor()

    customer = (customer or "").strip()
    if not customer or not frappe.db.exists(CUSTOMER_DOCTYPE, customer):
        frappe.throw(_("School license not found."))

    frappe.db.set_value(CUSTOMER_DOCTYPE, customer, "portal_active", 1 if int(active or 0) else 0)
    frappe.db.commit()

    return {"ok": True}
