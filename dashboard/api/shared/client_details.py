import frappe
from frappe import _


CLIENT_DOCTYPE = "Client"
CONTACT_DOCTYPE = "Contact"
EVENT_DOCTYPE = "Event"

CLIENT_CONTACTS_PARENT_FIELD_CANDIDATES = (
    "client_contacts",
    "client_contact_link",
    "contacts",
)

CLIENT_CONTACT_LINK_FIELD_CANDIDATES = (
    "contact",
    "contact_name",
    "client_contact",
)

CLIENT_NOTES_PARENT_FIELD_CANDIDATES = (
    "notes",
    "client_notes",
    "session_notes",
)

CLIENT_NOTE_TEXT_FIELD_CANDIDATES = (
    "note",
    "notes",
    "note_text",
    "content",
)

CLIENT_NOTE_DATE_FIELD_CANDIDATES = (
    "session_date",
    "date",
    "note_date",
    "created_on",
)

CLIENT_NOTE_USER_FIELD_CANDIDATES = (
    "user",
    "owner",
    "owner_name",
    "created_by",
)

CLIENT_NOTE_CLIENT_FIELD_CANDIDATES = (
    "client",
)

CLIENT_NOTE_SESSION_TYPE_FIELD_CANDIDATES = (
    "session_type",
)


def require_logged_in_user():
    if frappe.session.user == "Guest":
        frappe.throw(_("Login required"), frappe.PermissionError)

    return frappe.session.user


def first_existing_field(meta, candidates):
    for fieldname in candidates:
        if meta.has_field(fieldname):
            return fieldname

    return None


def get_child_row_value(row, candidates):
    for fieldname in candidates:
        value = row.get(fieldname)
        if value not in (None, ""):
            return value

    return ""


def get_client_contacts_parent_field():
    meta = frappe.get_meta(CLIENT_DOCTYPE)
    return first_existing_field(meta, CLIENT_CONTACTS_PARENT_FIELD_CANDIDATES)


def get_client_notes_parent_field():
    meta = frappe.get_meta(CLIENT_DOCTYPE)
    return first_existing_field(meta, CLIENT_NOTES_PARENT_FIELD_CANDIDATES)


def get_user_display_name(user):
    if not user:
        return ""

    full_name = frappe.get_cached_value("User", user, "full_name")
    return full_name or user


def get_contact_display_name(contact):
    return (
        contact.get("full_name")
        or " ".join(filter(None, [contact.get("first_name"), contact.get("last_name")])).strip()
        or contact.get("company_name")
        or contact.get("name")
    )


def get_client_contacts(client_name, contact_detail_base_url):
    require_logged_in_user()

    if not client_name:
        return []

    doc = frappe.get_doc(CLIENT_DOCTYPE, client_name)

    contacts_parent_field = get_client_contacts_parent_field()
    if not contacts_parent_field:
        return []

    result = []

    for row in doc.get(contacts_parent_field) or []:
        contact_name = get_child_row_value(row, CLIENT_CONTACT_LINK_FIELD_CANDIDATES)

        if not contact_name or not frappe.db.exists(CONTACT_DOCTYPE, contact_name):
            continue

        contact = frappe.db.get_value(
            CONTACT_DOCTYPE,
            contact_name,
            [
                "name",
                "full_name",
                "first_name",
                "last_name",
                "email_id",
                "mobile_no",
                "phone",
                "company_name",
                "designation",
            ],
            as_dict=True,
        )

        if not contact:
            continue

        result.append(
            {
                "name": contact.get("name"),
                "display_name": get_contact_display_name(contact),
                "email": contact.get("email_id") or "",
                "mobile": contact.get("mobile_no") or contact.get("phone") or "",
                "company": contact.get("company_name") or "",
                "designation": contact.get("designation") or "",
                "relationship": row.get("relationship") or row.get("relation") or "",
                "link": f"{contact_detail_base_url}?name={contact.get('name')}",
            }
        )

    return result


def get_client_notes(client_name):
    require_logged_in_user()

    if not client_name:
        return []

    doc = frappe.get_doc(CLIENT_DOCTYPE, client_name)

    notes_parent_field = get_client_notes_parent_field()
    if not notes_parent_field:
        return []

    result = []

    for row in doc.get(notes_parent_field) or []:
        note_date = get_child_row_value(row, CLIENT_NOTE_DATE_FIELD_CANDIDATES)

        if hasattr(note_date, "strftime"):
            note_date = note_date.strftime("%Y-%m-%d")

        note_user = get_child_row_value(row, CLIENT_NOTE_USER_FIELD_CANDIDATES)

        result.append(
            {
                "name": row.get("name"),
                "note_text": get_child_row_value(row, CLIENT_NOTE_TEXT_FIELD_CANDIDATES),
                "note_date": note_date or "",
                "note_user": note_user,
                "note_user_name": get_user_display_name(note_user),
                "client": get_child_row_value(row, CLIENT_NOTE_CLIENT_FIELD_CANDIDATES) or client_name,
                "session_type": get_child_row_value(row, CLIENT_NOTE_SESSION_TYPE_FIELD_CANDIDATES),
                "idx": row.get("idx") or 0,
            }
        )

    result.sort(key=lambda d: ((d.get("note_date") or ""), d.get("idx") or 0), reverse=True)
    return result


def add_client_note(client_name, note_text, session_date=None, session_type=None):
    require_logged_in_user()

    if not client_name:
        frappe.throw(_("Client is required."))

    note_text = (note_text or "").strip()
    if not note_text:
        frappe.throw(_("Note text is required."))

    client_doc = frappe.get_doc(CLIENT_DOCTYPE, client_name)

    notes_parent_field = get_client_notes_parent_field()
    if not notes_parent_field:
        frappe.throw(_("No client notes child table field was found on Client."))

    child_doctype = client_doc.meta.get_field(notes_parent_field).options
    if not child_doctype:
        frappe.throw(_("Notes child table is not configured correctly."))

    child_meta = frappe.get_meta(child_doctype)

    note_text_field = first_existing_field(child_meta, CLIENT_NOTE_TEXT_FIELD_CANDIDATES)
    note_date_field = first_existing_field(child_meta, CLIENT_NOTE_DATE_FIELD_CANDIDATES)
    note_user_field = first_existing_field(child_meta, CLIENT_NOTE_USER_FIELD_CANDIDATES)
    note_client_field = first_existing_field(child_meta, CLIENT_NOTE_CLIENT_FIELD_CANDIDATES)
    note_session_type_field = first_existing_field(child_meta, CLIENT_NOTE_SESSION_TYPE_FIELD_CANDIDATES)

    row = {}

    if note_text_field:
        row[note_text_field] = note_text

    if note_date_field:
        row[note_date_field] = session_date or frappe.utils.nowdate()

    if note_user_field:
        row[note_user_field] = frappe.session.user

    if note_client_field:
        row[note_client_field] = client_doc.name

    if note_session_type_field and session_type not in (None, ""):
        row[note_session_type_field] = session_type

    client_doc.append(notes_parent_field, row)
    client_doc.save(ignore_permissions=True)
    frappe.db.commit()

    return {"ok": 1, "message": _("Note added successfully.")}
