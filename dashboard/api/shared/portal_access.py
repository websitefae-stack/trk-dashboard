"""
Manages Client Contact Link rows - the doctype the `client_portal` app
reads to decide who can log in to the client portal for a given Client,
and exactly what they're allowed to see there. This is intentionally
separate from client_contacts (this app's own contact directory/billing-
contact feature in contacts.py/contact_details.py) - a person can be a
plain office contact without ever getting portal access, and vice versa.

Nothing in this file is called by, or changes the behaviour of, any
existing page - it's only used by the new Portal Access panel on the
client details page.
"""

import frappe
from frappe import _

from dashboard.api.shared.permissions import ensure_client_access, get_client_permissions

CLIENT_DOCTYPE = "Client"
LINK_DOCTYPE = "Client Contact Link"
LINK_PARENTFIELD = "client_contact_link"

PERMISSION_FIELDS = [
    "view_profile",
    "can_edit_profile",
    "can_view_appointments",
    "can_view_invoices",
    "can_pay_invoices",
    "can_view_courses_and_products",
    "can_view_downloads",
    "can_view_admin_details",
    "can_monitor_courses",
    "can_manage_staff_access",
    "can_view_sensitive_details",
]

LINK_FIELDS = [
    "name",
    "contact",
    "contact_name",
    "email_id",
    "phone",
    "relationship_type",
    "is_primary_contact",
    "is_billing_contact",
    "portal_access_enabled",
    *PERMISSION_FIELDS,
]

# Matches the Relationship Type select options already defined on the
# Client Contact Link doctype in Desk.
RELATIONSHIP_OPTIONS = [
    "Self",
    "Parent/Guardian",
    "Billing Contact",
    "School Admin",
    "School Staff",
    "Company Admin",
    "Company Billing",
    "Employee",
    "Referrer",
    "Emergency Contact",
    "Other",
]


def _can_manage_portal_access(client_name):
    permissions = get_client_permissions(client_name)
    return bool(permissions.get("can_edit"))


def _ensure_can_manage_portal_access(client_name):
    """Portal access controls what a parent/school/company can see of a
    client's data, so this is gated the same way as editing the client
    itself (client_details_can_edit) - franchisors and the client's own
    primary coach, not attending coaches or session workers.
    """
    ensure_client_access(client_name)

    if not _can_manage_portal_access(client_name):
        frappe.throw(
            _("You do not have permission to manage portal access for this client."),
            frappe.PermissionError,
        )


@frappe.whitelist()
def get_portal_access_rows(client_name):
    ensure_client_access(client_name)

    if not frappe.db.exists("DocType", LINK_DOCTYPE):
        return {"rows": [], "relationship_options": RELATIONSHIP_OPTIONS, "can_manage": False}

    rows = frappe.get_all(
        LINK_DOCTYPE,
        filters={"parenttype": CLIENT_DOCTYPE, "parent": client_name},
        fields=LINK_FIELDS,
        order_by="idx asc",
    )

    return {
        "rows": rows,
        "relationship_options": RELATIONSHIP_OPTIONS,
        "can_manage": _can_manage_portal_access(client_name),
    }


@frappe.whitelist()
def save_portal_access_row(client_name, data):
    _ensure_can_manage_portal_access(client_name)

    if not frappe.get_meta(CLIENT_DOCTYPE).has_field(LINK_PARENTFIELD):
        frappe.throw(_("Portal access is not set up on this site yet. Please ask support to run the latest client_portal migration."))

    if isinstance(data, str):
        data = frappe.parse_json(data)

    data = data or {}

    if not (data.get("email_id") or "").strip():
        frappe.throw(_("Email is required so this person can log in to the portal."))

    client = frappe.get_doc(CLIENT_DOCTYPE, client_name)

    row_name = data.get("name")
    row = None

    if row_name:
        for existing in client.get(LINK_PARENTFIELD) or []:
            if existing.name == row_name:
                row = existing
                break

    if not row:
        row = client.append(LINK_PARENTFIELD, {})

    row.contact_name = data.get("contact_name") or ""
    row.email_id = data.get("email_id") or ""
    row.phone = data.get("phone") or ""
    row.relationship_type = data.get("relationship_type") or ""
    row.is_primary_contact = 1 if data.get("is_primary_contact") else 0
    row.is_billing_contact = 1 if data.get("is_billing_contact") else 0
    row.portal_access_enabled = 1 if data.get("portal_access_enabled") else 0

    for field in PERMISSION_FIELDS:
        row.set(field, 1 if data.get(field) else 0)

    client.save(ignore_permissions=True)
    frappe.db.commit()

    return {"success": True}


@frappe.whitelist()
def remove_portal_access_row(client_name, row_name):
    _ensure_can_manage_portal_access(client_name)

    client = frappe.get_doc(CLIENT_DOCTYPE, client_name)

    client.set(
        LINK_PARENTFIELD,
        [row for row in client.get(LINK_PARENTFIELD) or [] if row.name != row_name],
    )

    client.save(ignore_permissions=True)
    frappe.db.commit()

    return {"success": True}
