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
from dashboard.api.shared.mail_throttle import send_email

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
    "view_reports",
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
    "portal_access_granted_on",
    "portal_access_notified_on",
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


def _merge_rows_by_email(rows):
    """The same real person can end up with more than one Client Contact
    Link row if they were added as a client contact more than once (e.g.
    two separate Contact records that both happen to be "Emma", each
    with their own portal-access row) - shown as-is, that reads as one
    person being both granted and not granted access at the same time.
    Collapses every group of rows that share an email address into a
    single display row (access/permissions = enabled if ANY row in the
    group is enabled, dates = the latest of the group), and carries every
    underlying row's name in `row_names` so a Grant/Revoke or permission
    change made against the merged row can be mirrored onto all of them.
    """

    groups = {}
    order = []

    for row in rows:
        key = (row.get("email_id") or "").strip().lower() or ("name:" + row.get("name"))
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(row)

    merged = []

    for key in order:
        group = groups[key]

        if len(group) == 1:
            single = dict(group[0])
            single["row_names"] = [single["name"]]
            merged.append(single)
            continue

        enabled_rows = [row for row in group if row.get("portal_access_enabled")]
        combined = dict(enabled_rows[0] if enabled_rows else group[0])
        combined["row_names"] = [row["name"] for row in group]
        combined["portal_access_enabled"] = 1 if enabled_rows else 0
        combined["is_primary_contact"] = 1 if any(row.get("is_primary_contact") for row in group) else 0
        combined["is_billing_contact"] = 1 if any(row.get("is_billing_contact") for row in group) else 0

        for prefer_field in ("contact", "contact_name", "phone", "relationship_type"):
            if not combined.get(prefer_field):
                for row in group:
                    if row.get(prefer_field):
                        combined[prefer_field] = row.get(prefer_field)
                        break

        for date_field in ("portal_access_granted_on", "portal_access_notified_on"):
            dates = [row.get(date_field) for row in group if row.get(date_field)]
            if dates:
                combined[date_field] = max(dates)

        for field in PERMISSION_FIELDS:
            combined[field] = 1 if any(row.get(field) for row in group) else 0

        merged.append(combined)

    return merged


@frappe.whitelist()
def get_portal_access_rows(client_name):
    """Keyed by `contact` docname client-side, so the Client Contacts
    table can show each row's own portal-access status without a second
    round trip.
    """

    ensure_client_access(client_name)

    if not frappe.db.exists("DocType", LINK_DOCTYPE):
        return {"rows": [], "relationship_options": RELATIONSHIP_OPTIONS, "can_manage": False}

    link_meta = frappe.get_meta(LINK_DOCTYPE)
    fetch_fields = [field for field in LINK_FIELDS if link_meta.has_field(field) or field == "name"]

    rows = frappe.get_all(
        LINK_DOCTYPE,
        filters={"parenttype": CLIENT_DOCTYPE, "parent": client_name},
        fields=fetch_fields,
        order_by="idx asc",
    )

    return {
        "rows": _merge_rows_by_email(rows),
        "relationship_options": RELATIONSHIP_OPTIONS,
        "can_manage": _can_manage_portal_access(client_name),
    }


@frappe.whitelist()
def save_portal_access_row(client_name, contact, data, also_row_names=None):
    """`contact` is an existing Contact docname already linked to this
    client via client_contacts. Pass "" only when the person genuinely has
    no Contact record on file - the client_portal app itself falls back to
    matching by email_id alone in that case.

    `also_row_names` is the rest of a `_merge_rows_by_email` group (every
    other underlying Client Contact Link row name that was merged into
    this one for display) - their access/permissions/dates are mirrored
    to match this save, so a duplicate person-row never comes back with
    the opposite access state right after being changed.
    """

    _ensure_can_manage_portal_access(client_name)

    if not frappe.get_meta(CLIENT_DOCTYPE).has_field(LINK_PARENTFIELD):
        frappe.throw(_("Portal access is not set up on this site yet. Please ask support to run the latest client_portal migration."))

    if isinstance(data, str):
        data = frappe.parse_json(data)

    if isinstance(also_row_names, str):
        also_row_names = frappe.parse_json(also_row_names)

    data = data or {}
    also_row_names = also_row_names or []
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

    was_enabled = bool(row and row.portal_access_enabled)

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

    link_meta = frappe.get_meta(LINK_DOCTYPE)

    # "Date access was given" tracks the most recent off -> on transition,
    # not every save - editing an already-enabled contact's other
    # permissions (or re-saving with no real change) must never bump it.
    if row.portal_access_enabled and not was_enabled and link_meta.has_field("portal_access_granted_on"):
        row.portal_access_granted_on = frappe.utils.today()

    for other in client.get(LINK_PARENTFIELD) or []:
        if other.name == row.name or other.name not in also_row_names:
            continue

        other_was_enabled = bool(other.portal_access_enabled)
        other.portal_access_enabled = row.portal_access_enabled

        for field in PERMISSION_FIELDS:
            other.set(field, row.get(field))

        if row.portal_access_enabled and not other_was_enabled and link_meta.has_field("portal_access_granted_on"):
            other.portal_access_granted_on = row.portal_access_granted_on or frappe.utils.today()

    client.save(ignore_permissions=True)
    frappe.db.commit()

    user_created = False

    if row.portal_access_enabled:
        user_created = _ensure_user_account(email, row.contact_name)

    if data.get("notify_by_email"):
        _send_portal_notification(email, row.contact_name, user_created, client_name)

        # Only recorded once the send above didn't raise - a failed
        # send (bad mail config, throttled, etc.) must never look like
        # "they were notified" in the report.
        if link_meta.has_field("portal_access_notified_on"):
            notified_on = frappe.utils.today()
            frappe.db.set_value(LINK_DOCTYPE, row.name, "portal_access_notified_on", notified_on)
            for other_name in also_row_names:
                if other_name != row.name:
                    frappe.db.set_value(LINK_DOCTYPE, other_name, "portal_access_notified_on", notified_on)

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


def _send_portal_notification(email, full_name, user_created, client_name):
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

    send_email(
        recipients=[email],
        subject="Your client portal access",
        message=message,
        reference_doctype=CLIENT_DOCTYPE,
        reference_name=client_name,
    )
