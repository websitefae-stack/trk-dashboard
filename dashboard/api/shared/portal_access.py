"""
Manages Client Contact Link rows - the doctype the `client_portal` app
reads to decide who can log in to the client portal for a given Client,
and exactly what they're allowed to see there.

Portal Access is always attached to an *existing* Client Contact (a
client_contacts row / Contact doctype) rather than being entered from
scratch a second time - a person's name/email/phone only ever gets typed
once, in the existing Add New Contact / Select Existing Contact flow. For
an adult client's own self-access, add them as a contact with Relationship
"Self" using their own email first, then grant portal access the same way.

Nothing in this file changes the behaviour of client_contacts, Contact,
or any other existing feature - it only reads/writes the separate
Client Contact Link child table.
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
    "can_book_appointments",
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
    """Keyed by `contact` docname client-side, so the Client Contacts
    table can show each row's own portal-access status without a second
    round trip.
    """

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
def save_portal_access_row(client_name, contact, data):
    """`contact` is an existing Contact docname already linked to this
    client via client_contacts. Pass "" only when the person genuinely has
    no Contact record on file - the client_portal app itself falls back to
    matching by email_id alone in that case.
    """

    _ensure_can_manage_portal_access(client_name)

    if not frappe.get_meta(CLIENT_DOCTYPE).has_field(LINK_PARENTFIELD):
        frappe.throw(_("Portal access is not set up on this site yet. Please ask support to run the latest client_portal migration."))

    if isinstance(data, str):
        data = frappe.parse_json(data)

    data = data or {}
    contact = (contact or "").strip()
    email = (data.get("email_id") or "").strip()

    if not email:
        frappe.throw(_("This contact has no email address on file, so they cannot be given portal access."))

    client = frappe.get_doc(CLIENT_DOCTYPE, client_name)

    row = None
    for existing in client.get(LINK_PARENTFIELD) or []:
        if contact and existing.contact == contact:
            row = existing
            break
        if not contact and not existing.contact and existing.email_id == email:
            row = existing
            break

    if not row:
        row = client.append(LINK_PARENTFIELD, {})

    row.contact = contact or ""
    row.contact_name = data.get("contact_name") or ""
    row.email_id = email
    row.phone = data.get("phone") or ""
    row.relationship_type = data.get("relationship_type") or ""
    row.is_primary_contact = 1 if data.get("is_primary_contact") else 0
    row.is_billing_contact = 1 if data.get("is_billing_contact") else 0
    row.portal_access_enabled = 1 if data.get("portal_access_enabled") else 0

    for field in PERMISSION_FIELDS:
        row.set(field, 1 if data.get(field) else 0)

    client.save(ignore_permissions=True)
    frappe.db.commit()

    user_created = False

    if row.portal_access_enabled:
        user_created = _ensure_user_account(email, row.contact_name)

    if data.get("notify_by_email"):
        _send_portal_notification(email, row.contact_name, user_created)

    return {"success": True, "user_created": user_created}


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


def _ensure_user_account(email, full_name):
    """Creates a Frappe User for this email if one doesn't exist yet, with
    the password defaulted to their own email address so they can log in
    immediately. Never resets the password of an account that already
    exists, since they may have already changed it themselves.
    """

    if frappe.db.exists("User", email):
        return False

    user = frappe.new_doc("User")
    user.email = email
    user.first_name = (full_name or email.split("@")[0]).split(" ")[0]
    user.full_name = full_name or email
    user.send_welcome_email = 0
    user.user_type = "Website User"
    user.insert(ignore_permissions=True)

    from frappe.utils.password import update_password
    update_password(email, email)

    frappe.db.commit()

    return True


def _send_portal_notification(email, full_name, user_created):
    login_url = frappe.utils.get_url("/login")
    greeting = f"Hi {full_name}," if full_name else "Hi,"

    if user_created:
        message = f"""
            <p>{greeting}</p>
            <p>You've been given access to the client portal.</p>
            <p><a href="{login_url}">Log in here</a></p>
            <p>Your username is your email address: <strong>{email}</strong></p>
            <p>Your temporary password is your email address (the same as above). You can change this any time using "Forgot Password" on the login page.</p>
        """
    else:
        message = f"""
            <p>{greeting}</p>
            <p>Your access to the client portal has been updated.</p>
            <p><a href="{login_url}">Log in here</a></p>
            <p>Use your existing password, or click "Forgot Password" on the login page if you need to reset it.</p>
        """

    frappe.sendmail(
        recipients=[email],
        subject="Your client portal access",
        message=message,
        now=True,
    )
