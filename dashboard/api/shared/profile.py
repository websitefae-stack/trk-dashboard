import frappe
from frappe import _
from werkzeug.utils import secure_filename

from dashboard.api.shared.notifications import create_trk_notification


CHANGE_REQUEST_DOCTYPE = "Change Request"

OFFICE_EMAIL = "office@theresilientpeople.uk"
ASHLEY_USER = "ashley@theresilientkid.co.uk"


LEGAL_TABLE_CONFIG = {
    "dbs": {
        "label": "DBS",
        "number_field": "dbs_number",
        "file_field": "dbs_file",
    },
    "dbs_update_service": {
        "label": "DBS Update Service",
        "number_field": "dbs_number",
        "file_field": "update_service_file",
    },
    "insurance": {
        "label": "Insurance",
        "number_field": "insurance_number",
        "file_field": "insurance_file",
        "insurer_field": "insurer_name",
    },
    "indemnity": {
        "label": "Indemnity",
        "number_field": "indemnity_number",
        "file_field": "indemnity_file",
        "insurer_field": "insurer_name",
    },
}


def ensure_logged_in():
    if frappe.session.user == "Guest":
        frappe.throw(_("Login required"), frappe.PermissionError)


def get_profile_doc(doctype_name, user_fieldnames, display_field=None):
    ensure_logged_in()

    profile_name = None

    for fieldname in user_fieldnames:
        profile_name = frappe.db.get_value(
            doctype_name,
            {fieldname: frappe.session.user},
            "name",
        )

        if profile_name:
            break

    if not profile_name:
        frappe.throw(
            _("No {0} profile linked.").format(doctype_name),
            frappe.PermissionError,
        )

    doc = frappe.get_doc(doctype_name, profile_name)

    display_name = (
        doc.get(display_field)
        if display_field and doc.get(display_field)
        else doc.name
    )

    return doc, display_name


@frappe.whitelist()
def update_profile(
    doctype_name,
    editable_fields=None,
    photo_field="photo",
    user_field="user",
):
    ensure_logged_in()

    editable_fields = editable_fields or []

    editable_fields = frappe.parse_json(editable_fields)

    profile_doc, _ = get_profile_doc(
        doctype_name,
        ["user", "coach_email", "sw_email"],
    )

    for fieldname in editable_fields:
        if profile_doc.meta.has_field(fieldname):
            profile_doc.set(fieldname, frappe.form_dict.get(fieldname))

    photo_url = _save_optional_file(
        "photo",
        doctype_name,
        profile_doc.name,
    )

    if photo_url and profile_doc.meta.has_field(photo_field):
        profile_doc.set(photo_field, photo_url)

    profile_doc.save(ignore_permissions=True)

    linked_user = (
        profile_doc.get(user_field)
        or frappe.session.user
    )

    if linked_user:
        user_updates = {}

        for fieldname in ["phone", "location", "gender"]:
            if frappe.form_dict.get(fieldname) is not None:
                user_updates[fieldname] = frappe.form_dict.get(fieldname)

        if photo_url:
            user_updates["user_image"] = photo_url

        if user_updates:
            frappe.db.set_value("User", linked_user, user_updates)

    frappe.db.commit()

    return {
        "ok": 1,
        "message": "Profile updated.",
    }


@frappe.whitelist()
def request_banking_change(
    doctype_name,
    link_field,
    display_name,
    request_for,
    notification_user,
    new_banking_details=None,
    banking_change_reason=None,
):
    ensure_logged_in()

    if not new_banking_details:
        frappe.throw(_("Enter new banking details."))

    profile_doc, resolved_display_name = get_profile_doc(
        doctype_name,
        ["user", "coach_email", "sw_email"],
        display_name,
    )

    doc = frappe.new_doc(CHANGE_REQUEST_DOCTYPE)

    doc.banking_change_for = request_for
    doc.set(link_field, profile_doc.name)

    doc.new_banking_details = new_banking_details
    doc.banking_change_reason = banking_change_reason
    doc.banking_change_status = "New"

    doc.change_requested_by = frappe.session.user
    doc.request_date = frappe.utils.now_datetime()

    doc.insert(ignore_permissions=True)

    create_trk_notification(
        recipient_user=notification_user,
        notification_type=f"{request_for} Banking Change",
        message=f"{resolved_display_name} submitted a banking change request.",
        priority="High",
        reference_doctype=CHANGE_REQUEST_DOCTYPE,
        reference_name=doc.name,
    )

    frappe.db.commit()

    return {
        "ok": 1,
        "message": "Request submitted.",
    }


@frappe.whitelist()
def add_legal_record(
    doctype_name,
    parentfield_map,
):
    ensure_logged_in()

    parentfield_map = frappe.parse_json(parentfield_map)

    profile_doc, _ = get_profile_doc(
        doctype_name,
        ["user", "coach_email", "sw_email"],
    )

    record_type = (frappe.form_dict.get("record_type") or "").strip()

    config = LEGAL_TABLE_CONFIG.get(record_type)

    if not config:
        frappe.throw(_("Invalid legal record type."))

    parentfield = parentfield_map.get(record_type)

    if not parentfield:
        frappe.throw(_("Missing parentfield mapping."))

    if not profile_doc.meta.has_field(parentfield):
        frappe.throw(_("Missing field: {0}").format(parentfield))

    file_url = _save_optional_file(
        config["file_field"],
        doctype_name,
        profile_doc.name,
    )

    if not file_url:
        frappe.throw(_("Please attach the required file."))

    child = profile_doc.append(parentfield, {})

    child.status = _get_status_from_expiry(
        frappe.form_dict.get("expiry_date")
    )

    child.date_received = frappe.form_dict.get("date_received")
    child.expiry_date = frappe.form_dict.get("expiry_date")

    child.set(
        config["number_field"],
        frappe.form_dict.get("number"),
    )

    if config.get("insurer_field"):
        child.set(
            config["insurer_field"],
            frappe.form_dict.get("insurer_name"),
        )

    child.set(config["file_field"], file_url)

    profile_doc.save(ignore_permissions=True)

    frappe.db.commit()

    return {
        "ok": 1,
        "message": f'{config["label"]} added successfully.',
    }


def _get_status_from_expiry(expiry_date):
    if not expiry_date:
        return "Expired"

    try:
        expiry = frappe.utils.getdate(expiry_date)
        today = frappe.utils.getdate(frappe.utils.today())

        return "Current" if expiry >= today else "Expired"

    except Exception:
        return "Expired"


def _save_optional_file(fieldname, doctype_name, docname):
    if not getattr(frappe, "request", None):
        return ""

    uploaded_file = frappe.request.files.get(fieldname)

    if not uploaded_file:
        return ""

    filename = secure_filename(
        uploaded_file.filename or "uploaded-file"
    )

    file_doc = frappe.get_doc({
        "doctype": "File",
        "file_name": filename,
        "attached_to_doctype": doctype_name,
        "attached_to_name": docname,
        "content": uploaded_file.stream.read(),
        "is_private": 1,
    })

    file_doc.save(ignore_permissions=True)

    return file_doc.file_url
