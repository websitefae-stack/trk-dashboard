import frappe
from frappe import _
from werkzeug.utils import secure_filename

from dashboard.api.shared.notifications import send_dashboard_notification


CHANGE_REQUEST_DOCTYPE = "Change Request"

OFFICE_USER = "office@theresilientpeople.uk"
ASHLEY_USER = "ashley@theresilientkid.co.uk"


ROLE_PROFILE_CONFIG = {
    "coach": {
        "doctype": "Coach",
        "user_fields": ["user", "coach_email"],
        "display_field": "coach_name",
        "email_field": "coach_email",
        "bank_account_field": "bank_account",
        "can_request_banking_change": 1,
        "can_edit_banking_directly": 0,
        "banking_change_for": "Coach",
        "banking_link_field": "banking_coach",
        "banking_notification_users": [
            ASHLEY_USER,
            OFFICE_USER,
        ],
       "editable_fields": [
            "first_name",
            "middle_name",
            "last_name",
            "phone",
            "gender",
            "location",
            "short_bio",
            "full_bio",
            "why_i_joined",
            "skills_strenghts",
            "message_from_coach",
            "facebook_url",
            "instagram_url",
            "linkedin_url",
        ],
        "user_update_fields": [
            "first_name",
            "middle_name",
            "last_name",
            "phone",
            "gender",
            "location",
            "birth_date",
        ],
        "legal_parentfields": {
            "dbs": "dbs",
            "dbs_update_service": "dbs_update_services",
            "insurance": "insurance",
            "indemnity": "indemnity",
        },
    },
    "franchisor": {
        "doctype": "Coach",
        "user_fields": ["user", "coach_email"],
        "display_field": "coach_name",
        "email_field": "coach_email",
        "bank_account_field": "bank_account",
        "can_request_banking_change": 0,
        "can_edit_banking_directly": 1,
        "banking_change_for": "Coach",
        "banking_link_field": "banking_coach",
        "banking_notification_users": [
            ASHLEY_USER,
            OFFICE_USER,
        ],
        "editable_fields": [
            "first_name",
            "middle_name",
            "last_name",
            "phone",
            "gender",
            "location",
            "short_bio",
            "full_bio",
            "why_i_joined",
            "skills_strenghts",
            "message_from_coach",
            "facebook_url",
            "instagram_url",
            "linkedin_url",
        ],
        "user_update_fields": [
            "first_name",
            "middle_name",
            "last_name",
            "phone",
            "gender",
            "location",
            "birth_date",
        ],
        "legal_parentfields": {
            "dbs": "dbs",
            "dbs_update_service": "dbs_update_services",
            "insurance": "insurance",
            "indemnity": "indemnity",
        },
    },
    "session_worker": {
        "doctype": "Session Worker",
        "user_fields": ["user", "sw_email"],
        "display_field": "sw_name",
        "email_field": "sw_email",
        "bank_account_field": "bank_account",
        "can_request_banking_change": 1,
        "can_edit_banking_directly": 0,
        "banking_change_for": "Session Worker",
        "banking_link_field": "banking_session_worker",
        "banking_notification_users": [
            OFFICE_USER,
            ASHLEY_USER,
        ],
        "editable_fields": [
            "first_name",
            "middle_name",
            "last_name",
            "phone",
            "gender",
            "location",
            "bio",
            "interest",
        ],
        "user_update_fields": [
            "first_name",
            "middle_name",
            "last_name",
            "phone",
            "gender",
            "location",
            "birth_date",
        ],
        "legal_parentfields": {
            "dbs": "dbs",
            "dbs_update_service": "dbs_update_service",
            "insurance": "insurance",
            "indemnity": "indemnity",
        },
    },
}


LEGAL_RECORD_CONFIG = {
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


def get_role_config(role):
    role = (role or "").strip()
    config = ROLE_PROFILE_CONFIG.get(role)

    if not config:
        frappe.throw(_("Invalid profile role."), frappe.PermissionError)

    return config


def get_profile_doc(role):
    ensure_logged_in()

    config = get_role_config(role)
    profile_name = None

    for fieldname in config["user_fields"]:
        profile_name = frappe.db.get_value(
            config["doctype"],
            {fieldname: frappe.session.user},
            "name",
        )

        if profile_name:
            break

    if not profile_name:
        frappe.throw(
            _("No {0} profile linked.").format(config["doctype"]),
            frappe.PermissionError,
        )

    return frappe.get_doc(config["doctype"], profile_name)


def get_profile_display_name(role):
    config = get_role_config(role)
    profile_doc = get_profile_doc(role)

    return (
        profile_doc.get(config["display_field"])
        or frappe.get_cached_value("User", frappe.session.user, "full_name")
        or profile_doc.name
    )


def get_franchisor_name():
    return (
        frappe.get_cached_value("User", frappe.session.user, "full_name")
        or frappe.session.user
    )


def get_profile_context(role):
    profile_doc = get_profile_doc(role)
    config = get_role_config(role)

    bank_account = None
    bank_account_field = config.get("bank_account_field")

    if bank_account_field and profile_doc.get(bank_account_field):
        bank_account = frappe.get_doc(
            "Bank Account",
            profile_doc.get(bank_account_field),
        )

    user_doc = frappe.get_doc("User", frappe.session.user)

    return {
        "profile_doc": profile_doc,
        "user_doc": user_doc,
        "bank_account": bank_account,
        "can_request_banking_change": config.get("can_request_banking_change", 0),
        "can_edit_banking_directly": config.get("can_edit_banking_directly", 0),
        "dbs_rows": profile_doc.get(config["legal_parentfields"]["dbs"]) or [],
        "dbs_update_service_rows": profile_doc.get(
            config["legal_parentfields"]["dbs_update_service"]
        ) or [],
        "insurance_rows": profile_doc.get(config["legal_parentfields"]["insurance"]) or [],
        "indemnity_rows": profile_doc.get(config["legal_parentfields"]["indemnity"]) or [],
    }


@frappe.whitelist()
def update_my_profile(role):
    ensure_logged_in()

    config = get_role_config(role)
    profile_doc = get_profile_doc(role)

    for fieldname in config["editable_fields"]:
        if profile_doc.meta.has_field(fieldname):
            profile_doc.set(fieldname, frappe.form_dict.get(fieldname))

    photo_url = _save_optional_file(
        "photo",
        config["doctype"],
        profile_doc.name,
    )

    if photo_url and profile_doc.meta.has_field("photo"):
        profile_doc.photo = photo_url

    profile_doc.save(ignore_permissions=True)

    linked_user = (
        profile_doc.get("user")
        or profile_doc.get(config.get("email_field"))
        or frappe.session.user
    )

    if linked_user:
        user_updates = {}

        user_meta = frappe.get_meta("User")

        for fieldname in config["user_update_fields"]:
            if frappe.form_dict.get(fieldname) is not None and user_meta.has_field(fieldname):
                user_updates[fieldname] = frappe.form_dict.get(fieldname)

        if photo_url and user_meta.has_field("user_image"):
            user_updates["user_image"] = photo_url

        if user_updates:
            frappe.db.set_value("User", linked_user, user_updates)

    frappe.db.commit()

    return {
        "ok": 1,
        "message": "Profile updated.",
    }


@frappe.whitelist()
def update_my_banking_details(
    role,
    account_name=None,
    bank=None,
    bank_account_no=None,
    branch_code=None,
    iban=None,
):
    ensure_logged_in()

    config = get_role_config(role)

    if not config.get("can_edit_banking_directly"):
        frappe.throw(
            _("You do not have permission to edit banking details directly."),
            frappe.PermissionError,
        )

    profile_doc = get_profile_doc(role)

    bank_account_field = config.get("bank_account_field")

    if not bank_account_field or not profile_doc.get(bank_account_field):
        frappe.throw(_("No bank account linked."))

    bank_account = frappe.get_doc(
        "Bank Account",
        profile_doc.get(bank_account_field),
    )

    bank_meta = frappe.get_meta("Bank Account")

    values = {
        "account_name": account_name,
        "bank": bank,
        "bank_account_no": bank_account_no,
        "branch_code": branch_code,
        "iban": iban,
    }

    for fieldname, value in values.items():
        if bank_meta.has_field(fieldname):
            bank_account.set(fieldname, value)

    bank_account.save(ignore_permissions=True)
    frappe.db.commit()

    return {
        "ok": 1,
        "message": "Banking details updated.",
    }


@frappe.whitelist()
def request_my_banking_change(
    role,
    account_name=None,
    bank=None,
    bank_account_no=None,
    branch_code=None,
    iban=None,
    banking_change_reason=None,
    new_banking_details=None,
):
    ensure_logged_in()

    config = get_role_config(role)

    if not config.get("can_request_banking_change"):
        frappe.throw(
            _("This dashboard does not use banking change requests."),
            frappe.PermissionError,
        )

    profile_doc = get_profile_doc(role)

    account_name = (account_name or "").strip()
    bank = (bank or "").strip()
    bank_account_no = (bank_account_no or "").strip()
    branch_code = (branch_code or "").strip()
    iban = (iban or "").strip()
    banking_change_reason = (banking_change_reason or "").strip()

    if not account_name:
        frappe.throw(_("Please enter the account name."))

    if not bank:
        frappe.throw(_("Please enter the bank name."))

    if not bank_account_no:
        frappe.throw(_("Please enter the account number."))

    if not branch_code:
        frappe.throw(_("Please enter the branch code."))

    if not frappe.db.exists("DocType", CHANGE_REQUEST_DOCTYPE):
        frappe.throw(_("Change Request DocType does not exist."))

    new_banking_details_text = "\n".join([
        "Account Name: {0}".format(account_name),
        "Bank: {0}".format(bank),
        "Account Number: {0}".format(bank_account_no),
        "Branch Code: {0}".format(branch_code),
        "IBAN: {0}".format(iban or "Not provided"),
    ])

    if new_banking_details:
        new_banking_details_text = new_banking_details

    change_request = frappe.new_doc(CHANGE_REQUEST_DOCTYPE)
    change_request_meta = frappe.get_meta(CHANGE_REQUEST_DOCTYPE)

    values = {
        "banking_change_for": config["banking_change_for"],
        config["banking_link_field"]: profile_doc.name,
        "new_banking_details": new_banking_details_text,
        "banking_change_reason": banking_change_reason,
        "banking_change_status": "New",
        "change_requested_by": frappe.session.user,
        "request_date": frappe.utils.now_datetime(),
    }

    for fieldname, value in values.items():
        if change_request_meta.has_field(fieldname):
            change_request.set(fieldname, value)

    change_request.insert(ignore_permissions=True)

    display_name = profile_doc.get(config["display_field"]) or profile_doc.name

    request_title = "{0} Banking Change Request".format(
        config["banking_change_for"]
    )

    notification_message = """{request_title}

{display_name} has submitted a banking change request.

Requested banking details:
Account Name: {account_name}
Bank: {bank}
Account Number: {bank_account_no}
Branch Code: {branch_code}
IBAN: {iban}

Reason / notes:
{reason}

Please update the bank account, reply when completed, then archive this conversation.""".format(
        request_title=request_title,
        display_name=display_name,
        account_name=account_name,
        bank=bank,
        bank_account_no=bank_account_no,
        branch_code=branch_code,
        iban=iban or "Not provided",
        reason=banking_change_reason or "No reason provided.",
    )

    notification_names = []

    recipient_users = [
        user for user in (config.get("banking_notification_users") or [])
        if user
    ]
    
    if recipient_users:
        notification_result = send_dashboard_notification(
            recipient_users=recipient_users,
            notification_type="Approval Request",
            title=request_title,
            message=notification_message,
            priority="High",
            reference_doctype=CHANGE_REQUEST_DOCTYPE,
            reference_name=change_request.name,
            requires_response=1,
        )
    
        notification_name = notification_result.get("name") if notification_result else ""
    
        if notification_name:
            notification_names.append(notification_name)

    if notification_names:
        for fieldname in [
            "notification",
            "notification_log",
            "dashboard_notification",
            "dashboard_conversation",
            "conversation",
        ]:
            if change_request_meta.has_field(fieldname):
                change_request.set(fieldname, notification_names[0])
                change_request.save(ignore_permissions=True)
                break

    frappe.db.commit()

    return {
        "ok": 1,
        "name": change_request.name,
        "notifications": notification_names,
        "notification": notification_names[0] if notification_names else "",
        "message": "Banking change request submitted successfully.",
    }


@frappe.whitelist()
def add_my_legal_record(role):
    ensure_logged_in()

    config = get_role_config(role)
    profile_doc = get_profile_doc(role)

    record_type = (frappe.form_dict.get("record_type") or "").strip()
    record_config = LEGAL_RECORD_CONFIG.get(record_type)

    if not record_config:
        frappe.throw(_("Invalid legal record type."))

    parentfield = config["legal_parentfields"].get(record_type)

    if not parentfield:
        frappe.throw(_("Legal record type is not configured."))

    if not profile_doc.meta.has_field(parentfield):
        frappe.throw(
            _("{0} is missing field: {1}").format(
                config["doctype"],
                parentfield,
            )
        )

    file_url = _save_optional_file(
        record_config["file_field"],
        config["doctype"],
        profile_doc.name,
    )

    if not file_url:
        frappe.throw(_("Please attach the required file."))

    child = profile_doc.append(parentfield, {})

    child.status = _get_status_from_expiry(frappe.form_dict.get("expiry_date"))
    child.date_received = frappe.form_dict.get("date_received")
    child.expiry_date = frappe.form_dict.get("expiry_date")

    child.set(record_config["number_field"], frappe.form_dict.get("number"))

    if record_config.get("insurer_field"):
        child.set(record_config["insurer_field"], frappe.form_dict.get("insurer_name"))

    child.set(record_config["file_field"], file_url)

    profile_doc.save(ignore_permissions=True)
    frappe.db.commit()

    return {
        "ok": 1,
        "message": "{0} added successfully.".format(record_config["label"]),
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


def _save_optional_file(fieldname, attached_to_doctype, attached_to_name):
    if not getattr(frappe, "request", None):
        return ""

    uploaded_file = frappe.request.files.get(fieldname)

    if not uploaded_file:
        return ""

    filename = secure_filename(uploaded_file.filename or "uploaded-file")

    file_doc = frappe.get_doc({
        "doctype": "File",
        "file_name": filename,
        "attached_to_doctype": attached_to_doctype,
        "attached_to_name": attached_to_name,
        "content": uploaded_file.stream.read(),
        "is_private": 1,
    })

    file_doc.save(ignore_permissions=True)

    return file_doc.file_url
