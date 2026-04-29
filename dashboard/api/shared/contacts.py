import frappe
from frappe import _

CLIENT_DOCTYPE = "Client"
CONTACT_DOCTYPE = "Contact"
COACH_DOCTYPE = "Coach"
SESSION_WORKER_DOCTYPE = "Session Worker"

FRANCHISOR_EMAILS = {
    "ashley@theresilientkid.co.uk",
    "office@theresilientpeople.uk",
    "hq@theresilientkid.co.uk",
}

ASHLEY_COACH_NAME = "Ashley Costello"


def ensure_logged_in():
    if frappe.session.user == "Guest":
        frappe.throw(_("Login required"), frappe.PermissionError)


def is_franchisor_user():
    ensure_logged_in()
    return (frappe.session.user or "").lower() in FRANCHISOR_EMAILS


def get_linked_doc_name(doctype):
    ensure_logged_in()

    if not frappe.db.exists("DocType", doctype):
        return ""

    meta = frappe.get_meta(doctype)
    if not meta.has_field("user"):
        return ""

    return frappe.db.get_value(doctype, {"user": frappe.session.user}, "name") or ""


def get_current_coach_name():
    return get_linked_doc_name(COACH_DOCTYPE)


def get_current_session_worker_name():
    return get_linked_doc_name(SESSION_WORKER_DOCTYPE)


def get_contact_display_name(contact):
    return (
        contact.get("full_name")
        or " ".join(filter(None, [contact.get("first_name"), contact.get("last_name")])).strip()
        or contact.get("company_name")
        or contact.get("name")
        or ""
    )


def get_client_display_name(client):
    return (
        client.get("full_name")
        or " ".join(filter(None, [client.get("name1"), client.get("last_name")])).strip()
        or client.get("name")
        or ""
    )


def get_contact_from_customer(customer_name):
    if not customer_name:
        return ""

    contact = frappe.db.get_value(
        "Contact",
        {"custom_customer": customer_name},
        "name",
    )

    if contact:
        return contact

    links = frappe.get_all(
        "Dynamic Link",
        filters={
            "parenttype": "Contact",
            "link_doctype": "Customer",
            "link_name": customer_name,
        },
        pluck="parent",
        limit_page_length=1,
    )

    return links[0] if links else ""


def get_allowed_clients(scope):
    ensure_logged_in()

    fields = [
        "name",
        "full_name",
        "name1",
        "last_name",
        "status",
        "client_type",
        "primary_coach",
        "attending_coach",
        "session_worker",
        "billing_contact",
    ]

    if scope == "session_worker":
        session_worker = get_current_session_worker_name()
        if not session_worker:
            return []

        return frappe.get_all(
            CLIENT_DOCTYPE,
            filters={"session_worker": session_worker},
            fields=fields,
            order_by="full_name asc, name1 asc, last_name asc",
            limit_page_length=5000,
        )

    if scope == "coach":
        coach = get_current_coach_name()
        if not coach:
            return []

        return frappe.get_all(
            CLIENT_DOCTYPE,
            filters=[
                [CLIENT_DOCTYPE, "primary_coach", "=", coach],
                "or",
                [CLIENT_DOCTYPE, "attending_coach", "=", coach],
            ],
            fields=fields,
            order_by="full_name asc, name1 asc, last_name asc",
            limit_page_length=5000,
        )

    if scope == "franchisor":
        if not is_franchisor_user():
            frappe.throw(_("You do not have permission to access the Franchisor Dashboard."), frappe.PermissionError)

        return frappe.get_all(
            CLIENT_DOCTYPE,
            filters=[
                [CLIENT_DOCTYPE, "primary_coach", "=", ASHLEY_COACH_NAME],
                "or",
                [CLIENT_DOCTYPE, "attending_coach", "=", ASHLEY_COACH_NAME],
            ],
            fields=fields,
            order_by="full_name asc, name1 asc, last_name asc",
            limit_page_length=5000,
        )

    return []


def get_contact_names_from_clients(clients, include_billing_contact=True):
    contact_names = set()

    for client in clients:
        try:
            client_doc = frappe.get_doc(CLIENT_DOCTYPE, client.name)
        except Exception:
            continue

        for row in client_doc.get("client_contacts") or []:
            if row.get("contact"):
                contact_names.add(row.get("contact"))

        if include_billing_contact and client.get("billing_contact"):
            billing_contact = get_contact_from_customer(client.get("billing_contact"))
            if billing_contact:
                contact_names.add(billing_contact)

    return sorted(contact_names)


def get_linked_clients_for_contact(contact_name, clients):
    linked_clients = []

    for client in clients:
        linked = False

        try:
            client_doc = frappe.get_doc(CLIENT_DOCTYPE, client.name)
        except Exception:
            continue

        for row in client_doc.get("client_contacts") or []:
            if row.get("contact") == contact_name:
                linked = True
                break

        if not linked and client.get("billing_contact"):
            billing_contact = get_contact_from_customer(client.get("billing_contact"))
            if billing_contact == contact_name:
                linked = True

        if linked:
            linked_clients.append({
                "name": client.name,
                "display_name": get_client_display_name(client),
                "primary_coach": client.get("primary_coach") or "",
                "attending_coach": client.get("attending_coach") or "",
                "session_worker": client.get("session_worker") or "",
                "status": client.get("status") or "",
                "client_type": client.get("client_type") or "",
            })

    return linked_clients


def get_contacts_for_scope(scope, show_all=False):
    ensure_logged_in()

    if scope == "franchisor" and show_all:
        if not is_franchisor_user():
            frappe.throw(_("You do not have permission to view all contacts."), frappe.PermissionError)

        filters = {}
        allowed_clients = frappe.get_all(
            CLIENT_DOCTYPE,
            fields=[
                "name",
                "full_name",
                "name1",
                "last_name",
                "status",
                "client_type",
                "primary_coach",
                "attending_coach",
                "session_worker",
                "billing_contact",
            ],
            limit_page_length=10000,
        )
    else:
        allowed_clients = get_allowed_clients(scope)
        contact_names = get_contact_names_from_clients(allowed_clients, include_billing_contact=True)

        if not contact_names:
            return []

        filters = {"name": ["in", contact_names]}

    contacts = frappe.get_all(
        CONTACT_DOCTYPE,
        filters=filters,
        fields=[
            "name",
            "full_name",
            "first_name",
            "last_name",
            "mobile_no",
            "email_id",
            "designation",
            "company_name",
            "is_billing_contact",
            "custom_customer",
        ],
        order_by="full_name asc, first_name asc, last_name asc",
        limit_page_length=5000,
    )

    rows = []

    for contact in contacts:
        linked_clients = get_linked_clients_for_contact(contact.name, allowed_clients)

        if scope != "franchisor" and not linked_clients:
            continue

        coach_names = sorted({
            c.get("primary_coach") or c.get("attending_coach")
            for c in linked_clients
            if c.get("primary_coach") or c.get("attending_coach")
        })

        rows.append({
            "name": contact.name,
            "display_name": get_contact_display_name(contact),
            "mobile_no": contact.get("mobile_no") or "",
            "email_id": contact.get("email_id") or "",
            "designation": contact.get("designation") or "",
            "company_name": contact.get("company_name") or "",
            "is_billing_contact": contact.get("is_billing_contact") or 0,
            "custom_customer": contact.get("custom_customer") or "",
            "linked_clients": linked_clients,
            "linked_client_text": ", ".join([c["display_name"] for c in linked_clients]),
            "coach_name": ", ".join(coach_names),
        })

    return rows


def ensure_contact_access(contact_name, scope):
    ensure_logged_in()

    if not contact_name:
        frappe.throw(_("Contact is required."))

    if scope == "franchisor" and is_franchisor_user():
        return

    contacts = get_contacts_for_scope(scope)
    allowed_names = {row["name"] for row in contacts}

    if contact_name not in allowed_names:
        frappe.throw(_("You do not have permission to access this contact."), frappe.PermissionError)
