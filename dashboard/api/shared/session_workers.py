import frappe
from frappe import _

from dashboard.api.shared.permissions import (
    ensure_logged_in,
    is_franchisor_user,
    get_current_coach_name,
)


SESSION_WORKER_DOCTYPE = "Session Worker"
CLIENT_DOCTYPE = "Client"
COACH_DOCTYPE = "Coach"


SESSION_WORKER_LABEL_FIELDS = [
    "sw_name",
    "session_worker_name",
    "full_name",
    "employee_name",
    "user_full_name",
    "title",
    "name",
]

SESSION_WORKER_EMAIL_FIELDS = [
    "sw_email",
    "session_worker_email",
    "email",
    "email_id",
    "user",
    "user_id",
]

SESSION_WORKER_MOBILE_FIELDS = [
    "phone",
    "mobile",
    "mobile_no",
    "contact_number",
]

COACH_LABEL_FIELDS = [
    "coach_name",
    "full_name",
    "employee_name",
    "user_full_name",
    "title",
    "name",
]


PROFILE_FIELD_CONFIG = [
    {"label": "Name", "fields": ["sw_name", "session_worker_name", "full_name", "name"]},
    {"label": "First Name", "fields": ["first_name"]},
    {"label": "Middle Name", "fields": ["middle_name"]},
    {"label": "Last Name", "fields": ["last_name"]},
    {"label": "Mobile", "fields": ["mobile", "mobile_no", "phone"]},
    {"label": "Email", "fields": ["sw_email", "session_worker_email", "email", "email_id", "user"]},
    {"label": "Linked Coaches", "key": "linked_coach_label"},
    {"label": "Phone", "fields": ["phone"]},
    {"label": "Gender", "fields": ["gender"]},
    {"label": "Location", "fields": ["location"]},
    {"label": "Birthday", "fields": ["birth_date", "birthday", "date_of_birth"]},
    {"label": "Bio", "fields": ["bio"], "full_width": 1},
    {"label": "Interest", "fields": ["interest"], "full_width": 1},
]

LEGAL_PARENTFIELDS = {
    "dbs": "dbs",
    "dbs_update_service": "dbs_update_service",
    "insurance": "insurance",
    "indemnity": "indemnity",
}

LEGAL_LABELS = {
    "dbs": "DBS",
    "dbs_update_service": "DBS Update Service",
    "insurance": "Insurance",
    "indemnity": "Indemnity",
}

BILLING_FIELD_CONFIG = [
    {"label": "Invoice Frequency", "fields": ["invoice_frequency"]},
    {"label": "Invoice Cycle Start Date", "fields": ["invoice_cycle_start_date"]},
    {"label": "Billing Type", "fields": ["billing_type"]},
    {"label": "Hourly Rate", "fields": ["hourly_rate"]},
    {"label": "Session Rate", "fields": ["session_rate"]},
]

BANK_ACCOUNT_FIELD_CONFIG = [
    {"label": "Account Name", "fields": ["account_name"]},
    {"label": "Bank", "fields": ["bank"]},
    {"label": "Bank Account No", "fields": ["bank_account_no"]},
    {"label": "Branch Code", "fields": ["branch_code"]},
    {"label": "IBAN", "fields": ["iban"]},
]


def has_doctype(doctype):
    return frappe.db.exists("DocType", doctype)


def has_field(doctype, fieldname):
    if not has_doctype(doctype):
        return False

    return frappe.get_meta(doctype).has_field(fieldname)


def get_existing_fields(doctype, candidates):
    if not has_doctype(doctype):
        return []

    meta = frappe.get_meta(doctype)
    fields = []

    for fieldname in candidates:
        if fieldname == "name" or meta.has_field(fieldname):
            fields.append(fieldname)

    return fields


def get_first_value(row, fields):
    for fieldname in fields:
        value = (row.get(fieldname) or "").strip()
        if value:
            return value

    return ""


def get_value_from_config(row, config):
    if config.get("key"):
        return row.get(config["key"]) or ""

    for fieldname in config.get("fields") or []:
        value = row.get(fieldname)
        if value not in [None, ""]:
            return value

    return ""


def get_session_worker_fields():
    fields = ["name"]

    for fieldname in SESSION_WORKER_LABEL_FIELDS + SESSION_WORKER_EMAIL_FIELDS + SESSION_WORKER_MOBILE_FIELDS:
        if fieldname not in fields:
            fields.append(fieldname)

    for config in PROFILE_FIELD_CONFIG + BILLING_FIELD_CONFIG:
        for fieldname in config.get("fields") or []:
            if fieldname not in fields:
                fields.append(fieldname)

    extra_fields = [
        "photo",
        "bank_account",
    ]

    for fieldname in extra_fields:
        if fieldname not in fields:
            fields.append(fieldname)

    return get_existing_fields(SESSION_WORKER_DOCTYPE, fields)


def get_client_fields():
    return get_existing_fields(
        CLIENT_DOCTYPE,
        [
            "name",
            "full_name",
            "name1",
            "last_name",
            "primary_coach",
            "attending_coach",
            "session_worker",
            "status",
            "client_type",
        ],
    )


def get_coach_fields():
    fields = ["name"]

    for fieldname in COACH_LABEL_FIELDS:
        if fieldname not in fields:
            fields.append(fieldname)

    return get_existing_fields(COACH_DOCTYPE, fields)


def get_session_worker_label(worker_name):
    if not worker_name:
        return ""

    if not has_doctype(SESSION_WORKER_DOCTYPE):
        return worker_name

    row = frappe.db.get_value(
        SESSION_WORKER_DOCTYPE,
        worker_name,
        get_session_worker_fields(),
        as_dict=True,
    )

    if not row:
        return worker_name

    return get_first_value(row, SESSION_WORKER_LABEL_FIELDS) or worker_name


def get_coach_label(coach_name):
    if not coach_name:
        return ""

    if not has_doctype(COACH_DOCTYPE):
        return coach_name

    row = frappe.db.get_value(
        COACH_DOCTYPE,
        coach_name,
        get_coach_fields(),
        as_dict=True,
    )

    if not row:
        return coach_name

    return get_first_value(row, COACH_LABEL_FIELDS) or coach_name


def get_client_display_name(client):
    return (
        client.get("full_name")
        or " ".join(
            part.strip()
            for part in [
                client.get("name1") or "",
                client.get("last_name") or "",
            ]
            if part and part.strip()
        )
        or client.get("name")
        or ""
    )


def get_clients_for_coach(coach_name):
    if not coach_name or not has_doctype(CLIENT_DOCTYPE):
        return []

    fields = get_client_fields()
    rows_by_name = {}
    meta = frappe.get_meta(CLIENT_DOCTYPE)

    if meta.has_field("primary_coach"):
        for row in frappe.get_all(
            CLIENT_DOCTYPE,
            filters={"primary_coach": coach_name},
            fields=fields,
            limit_page_length=10000,
            ignore_permissions=True,
        ):
            rows_by_name[row.name] = row

    if meta.has_field("attending_coach"):
        for row in frappe.get_all(
            CLIENT_DOCTYPE,
            filters={"attending_coach": coach_name},
            fields=fields,
            limit_page_length=10000,
            ignore_permissions=True,
        ):
            rows_by_name[row.name] = row

    return list(rows_by_name.values())


def get_all_clients():
    if not has_doctype(CLIENT_DOCTYPE):
        return []

    return frappe.get_all(
        CLIENT_DOCTYPE,
        fields=get_client_fields(),
        limit_page_length=10000,
        ignore_permissions=True,
    )


def get_all_session_worker_docs():
    if not has_doctype(SESSION_WORKER_DOCTYPE):
        return []

    return frappe.get_all(
        SESSION_WORKER_DOCTYPE,
        fields=get_session_worker_fields(),
        order_by="name asc",
        limit_page_length=10000,
        ignore_permissions=True,
    )


def build_worker_map():
    workers = {}

    for worker in get_all_session_worker_docs():
        worker_name = worker.get("name")

        if not worker_name:
            continue

        workers[worker_name] = {
            "name": worker_name,
            "display_name": get_first_value(worker, SESSION_WORKER_LABEL_FIELDS) or worker_name,
            "mobile": get_first_value(worker, SESSION_WORKER_MOBILE_FIELDS),
            "email": get_first_value(worker, SESSION_WORKER_EMAIL_FIELDS),
            "linked_coaches": [],
            "linked_coach_labels": [],
            "linked_clients_count": 0,
            "linked_clients": [],
        }

    return workers


def add_client_context_to_workers(workers, clients, restrict_to_coach=None):
    coach_names_by_worker = {}
    client_count_by_worker = {}
    clients_by_worker = {}

    for client in clients:
        worker_name = client.get("session_worker")

        if not worker_name:
            continue

        if worker_name not in workers:
            workers[worker_name] = {
                "name": worker_name,
                "display_name": get_session_worker_label(worker_name),
                "mobile": "",
                "email": "",
                "linked_coaches": [],
                "linked_coach_labels": [],
                "linked_clients_count": 0,
                "linked_clients": [],
            }

        coach_names_by_worker.setdefault(worker_name, set())
        clients_by_worker.setdefault(worker_name, [])
        client_count_by_worker[worker_name] = client_count_by_worker.get(worker_name, 0) + 1

        for coach_field in ["primary_coach", "attending_coach"]:
            coach_name = client.get(coach_field)

            if not coach_name:
                continue

            if restrict_to_coach and coach_name != restrict_to_coach:
                continue

            coach_names_by_worker[worker_name].add(coach_name)

        clients_by_worker[worker_name].append({
            "name": client.get("name"),
            "display_name": get_client_display_name(client),
            "status": client.get("status") or "",
            "client_type": client.get("client_type") or "",
            "primary_coach": client.get("primary_coach") or "",
            "primary_coach_label": get_coach_label(client.get("primary_coach")),
            "attending_coach": client.get("attending_coach") or "",
            "attending_coach_label": get_coach_label(client.get("attending_coach")),
        })

    for worker_name, worker in workers.items():
        linked_coaches = sorted(coach_names_by_worker.get(worker_name, set()))

        worker["linked_coaches"] = [
            {
                "name": coach_name,
                "display_name": get_coach_label(coach_name),
            }
            for coach_name in linked_coaches
        ]

        worker["linked_coach_labels"] = [
            row["display_name"]
            for row in worker["linked_coaches"]
            if row.get("display_name")
        ]

        worker["linked_coach_label"] = ", ".join(worker["linked_coach_labels"])
        worker["linked_clients_count"] = client_count_by_worker.get(worker_name, 0)
        worker["linked_clients"] = sorted(
            clients_by_worker.get(worker_name, []),
            key=lambda row: (row.get("display_name") or "").lower(),
        )

    return workers


def normalize_rows(workers, scope):
    rows = []

    for worker in workers.values():
        if scope == "coach" and not worker.get("linked_clients_count"):
            continue

        rows.append(worker)

    return sorted(rows, key=lambda row: (row.get("display_name") or "").lower())


def build_profile_fields(worker_row):
    fields = []

    for config in PROFILE_FIELD_CONFIG:
        fields.append({
            "label": config.get("label"),
            "value": get_value_from_config(worker_row, config),
            "full_width": config.get("full_width", 0),
        })

    return fields


def get_child_rows(doc, parentfield):
    if not parentfield:
        return []

    if not doc.meta.has_field(parentfield):
        return []

    rows = []

    for row in doc.get(parentfield) or []:
        rows.append(row.as_dict() if hasattr(row, "as_dict") else dict(row))

    return rows


def build_legal_sections(doc):
    sections = []

    for key, parentfield in LEGAL_PARENTFIELDS.items():
        rows = get_child_rows(doc, parentfield)

        sections.append({
            "key": key,
            "label": LEGAL_LABELS.get(key) or key.replace("_", " ").title(),
            "rows": rows,
        })

    return sections


def build_billing_fields(worker_row):
    fields = []

    for config in BILLING_FIELD_CONFIG:
        value = get_value_from_config(worker_row, config)

        if value not in [None, ""]:
            fields.append({
                "label": config.get("label"),
                "value": value,
            })

    return fields


def build_bank_account_fields(doc):
    bank_account_name = doc.get("bank_account")

    if not bank_account_name:
        return []

    if not frappe.db.exists("Bank Account", bank_account_name):
        return []

    fields_to_fetch = ["name"]

    for config in BANK_ACCOUNT_FIELD_CONFIG:
        for fieldname in config.get("fields") or []:
            if has_field("Bank Account", fieldname) and fieldname not in fields_to_fetch:
                fields_to_fetch.append(fieldname)

    bank_account = frappe.db.get_value(
        "Bank Account",
        bank_account_name,
        fields_to_fetch,
        as_dict=True,
    )

    if not bank_account:
        return []

    fields = [
        {
            "label": "Bank Account",
            "value": bank_account.get("name"),
        }
    ]

    for config in BANK_ACCOUNT_FIELD_CONFIG:
        fields.append({
            "label": config.get("label"),
            "value": get_value_from_config(bank_account, config),
        })

    return fields


@frappe.whitelist()
def get_session_workers(scope=None):
    ensure_logged_in()

    scope = (scope or "").strip().lower()

    if scope not in ["coach", "franchisor"]:
        frappe.throw(_("Invalid session worker scope."), frappe.PermissionError)

    if scope == "coach":
        coach_name = get_current_coach_name(optional=True)

        if not coach_name:
            return {
                "scope": "coach",
                "current_coach": "",
                "current_coach_label": "",
                "session_workers": [],
            }

        clients = get_clients_for_coach(coach_name)
        workers = build_worker_map()
        workers = add_client_context_to_workers(workers, clients, restrict_to_coach=coach_name)

        return {
            "scope": "coach",
            "current_coach": coach_name,
            "current_coach_label": get_coach_label(coach_name),
            "session_workers": normalize_rows(workers, scope="coach"),
        }

    if scope == "franchisor":
        if not is_franchisor_user():
            frappe.throw(
                _("You do not have permission to access session workers."),
                frappe.PermissionError,
            )

        clients = get_all_clients()
        workers = build_worker_map()
        workers = add_client_context_to_workers(workers, clients)

        return {
            "scope": "franchisor",
            "current_coach": "",
            "current_coach_label": "",
            "session_workers": normalize_rows(workers, scope="franchisor"),
        }


@frappe.whitelist()
def get_session_worker_details(scope=None, worker_name=None):
    ensure_logged_in()

    scope = (scope or "").strip().lower()
    worker_name = (worker_name or "").strip()

    if scope not in ["coach", "franchisor"]:
        frappe.throw(_("Invalid session worker scope."), frappe.PermissionError)

    if not worker_name:
        frappe.throw(_("Session Worker not found."))

    data = get_session_workers(scope=scope)
    allowed_workers = data.get("session_workers") or []

    selected_worker = None

    for worker in allowed_workers:
        if worker.get("name") == worker_name:
            selected_worker = worker
            break

    if not selected_worker:
        frappe.throw(
            _("You do not have permission to view this session worker."),
            frappe.PermissionError,
        )

    if not frappe.db.exists(SESSION_WORKER_DOCTYPE, worker_name):
        frappe.throw(_("Session Worker not found."))

    doc = frappe.get_doc(SESSION_WORKER_DOCTYPE, worker_name)

    worker_row = doc.as_dict()
    worker_row.update(selected_worker)

    return {
        "scope": scope,
        "session_worker": selected_worker,
        "profile_fields": build_profile_fields(worker_row),
        "photo": worker_row.get("photo") or "",
        "legal_sections": build_legal_sections(doc),
        "billing_fields": build_billing_fields(worker_row),
        "bank_account_fields": build_bank_account_fields(doc),
        "linked_clients": selected_worker.get("linked_clients") or [],
        "back_url": f"/{scope}_db/session_workers",
        "client_details_base_url": f"/{scope}_db/client_details",
    }
