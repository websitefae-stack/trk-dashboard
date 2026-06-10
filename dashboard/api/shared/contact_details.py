import json
import frappe
from frappe import _

from dashboard.api.shared.contacts import (
    ensure_contact_access,
    get_current_coach_name,
    get_current_session_worker_name,
    is_franchisor_user,
)
from dashboard.api.shared.permissions import ensure_logged_in


EDITABLE_CONTACT_FIELDS = [
    "full_name",
    "first_name",
    "last_name",
    "email_id",
    "mobile_no",
    "designation",
    "company_name",

    # billing contact fields
    "is_billing_contact",
    "custom_customer",

    # address fields
    "address_line1",
    "address_line2",
    "city",
    "county",
    "state",
    "pincode",
    "country",
]


def parse_payload(value):
    if isinstance(value, str):
        return json.loads(value) if value else {}

    return value or {}


def contact_display_name(contact):
    return (
        contact.get("full_name")
        or " ".join(filter(None, [contact.get("first_name"), contact.get("last_name")])).strip()
        or contact.get("company_name")
        or contact.get("name")
        or "Contact Details"
    )


def client_display_name(client):
    return (
        client.get("full_name")
        or " ".join(filter(None, [client.get("name1"), client.get("last_name")])).strip()
        or client.get("name")
    )


def coach_display_name(coach):
    if coach and frappe.db.exists("Coach", coach):
        return frappe.db.get_value("Coach", coach, "coach_name") or coach

    return coach or ""


def get_contact_customer_names(contact):
    customers = set()

    if contact.get("custom_customer"):
        customers.add(contact.get("custom_customer"))

    for link in contact.get("links") or []:
        if link.get("link_doctype") == "Customer" and link.get("link_name"):
            customers.add(link.get("link_name"))

    return customers


def get_linked_clients(contact, scope, view_coach_name=None):
    if not contact or not contact.name:
        return []

    contact_customers = get_contact_customer_names(contact)

    clients = frappe.get_all(
        "Client",
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
            "pricelist",
            "banking",
        ],
        order_by="full_name asc, name1 asc, last_name asc",
        limit_page_length=5000,
    )

    current_coach = (view_coach_name or "").strip() or get_current_coach_name()
    current_sw = get_current_session_worker_name()

    rows = []

    for client in clients:
        is_general_linked = 0
        is_billing_client = 0

        if client.get("billing_contact") and client.get("billing_contact") in contact_customers:
            is_billing_client = 1

        try:
            client_doc = frappe.get_doc("Client", client.name)
        except Exception:
            continue

        for row in client_doc.get("client_contacts") or []:
            if row.get("contact") == contact.name:
                is_general_linked = 1
                break

        if not is_general_linked and not is_billing_client:
            continue

        if scope == "session_worker" and client.get("session_worker") != current_sw:
            continue

        if scope == "coach":
            if client.get("primary_coach") != current_coach and client.get("attending_coach") != current_coach:
                continue

        if scope == "franchisor" and not is_franchisor_user():
            continue

        rows.append({
            "name": client.name,
            "display_name": client_display_name(client),
            "status": client.get("status") or "",
            "client_type": client.get("client_type") or "",
            "primary_coach": client.get("primary_coach") or "",
            "primary_coach_display": coach_display_name(client.get("primary_coach")),
            "attending_coach": client.get("attending_coach") or "",
            "attending_coach_display": coach_display_name(client.get("attending_coach")),
            "session_worker": client.get("session_worker") or "",
            "is_general_linked": is_general_linked,
            "is_billing_client": is_billing_client,
            "default_price_list": client.get("pricelist") or "",
            "default_bank_account": client.get("banking") or "",
        })

    return rows


def get_contact_invoices(linked_clients):
    billing_clients = [row["name"] for row in linked_clients if row.get("is_billing_client")]

    if not billing_clients:
        return []

    invoices = frappe.get_all(
        "Sales Invoice",
        filters={"custom_client": ["in", billing_clients]},
        fields=[
            "name",
            "custom_client",
            "posting_date",
            "due_date",
            "status",
            "grand_total",
            "outstanding_amount",
            "docstatus",
        ],
        order_by="posting_date desc, creation desc",
        limit_page_length=500,
    )

    client_map = {row["name"]: row["display_name"] for row in linked_clients}

    return [{
        "name": row.name,
        "client": row.custom_client,
        "client_display": client_map.get(row.custom_client) or row.custom_client,
        "posting_date": row.posting_date,
        "due_date": row.due_date,
        "status": row.status,
        "grand_total": row.grand_total,
        "outstanding_amount": row.outstanding_amount,
        "docstatus": row.docstatus,
    } for row in invoices]


def get_contact_context(scope, contact_name=None, is_new=False, view_coach_name=None):
    ensure_logged_in()

    if is_new:
        if scope == "session_worker":
            frappe.throw(_("Session workers cannot create contacts."), frappe.PermissionError)

        contact = frappe.new_doc("Contact")

        return {
            "contact": contact.as_dict(),
            "contact_docname": "",
            "contact_display_name": "New Contact",
            "is_new": 1,
            "linked_clients": [],
            "contact_invoices": [],
            "clients": frappe.get_all(
                "Client",
                fields=[
                    "name",
                    "full_name",
                    "name1",
                    "last_name"
                ],
                order_by="full_name asc, name1 asc",
                limit_page_length=5000,
            ),
            "contact_details_scope": scope,
            "contact_details_base_url": get_base_url_for_scope(scope),
            "contact_details_save_method": "dashboard.api.shared.contact_details.save_contact",
        }

    if not contact_name:
        frappe.throw(_("Contact not found."))

    contact = frappe.get_doc("Contact", contact_name)
    linked_clients = get_linked_clients(
        contact,
        scope,
        view_coach_name=view_coach_name,
    )

    if scope in ("session_worker", "coach"):
        if not linked_clients:
            frappe.throw(_("You do not have permission to access this contact."), frappe.PermissionError)

    elif scope == "franchisor":
        if not is_franchisor_user():
            frappe.throw(_("You do not have permission to access this contact."), frappe.PermissionError)

    else:
        ensure_contact_access(contact_name, scope)

    return {
        "contact": contact.as_dict(),
        "contact_docname": contact.name,
        "clients": frappe.get_all(
            "Client",
            fields=[
                "name",
                "full_name",
                "name1",
                "last_name"
            ],
            order_by="full_name asc, name1 asc",
            limit_page_length=5000,
        ),
        "contact_display_name": contact_display_name(contact),
        "is_new": 0,
        "linked_clients": linked_clients,
        "contact_invoices": get_contact_invoices(linked_clients),
        "contact_details_scope": scope,
        "contact_details_base_url": get_base_url_for_scope(scope),
        "contact_details_save_method": "dashboard.api.shared.contact_details.save_contact",
    }


def get_base_url_for_scope(scope):
    if scope == "franchisor":
        return "/franchisor_db"

    if scope == "session_worker":
        return "/session_worker_db"

    return "/coach_db"


def save_contact_for_scope(scope, docname=None, data=None):
    ensure_logged_in()

    if scope == "session_worker":
        frappe.throw(_("Session workers cannot edit contacts."), frappe.PermissionError)

    payload = parse_payload(data)

    linked_client = (payload.get("linked_client") or "").strip()
    relationship_type = (payload.get("relationship_type") or "").strip()
    is_billing_contact = int(payload.get("is_billing_contact") or 0)

    email = (payload.get("email_id") or "").strip()

    if docname:
        ensure_contact_access(docname, scope)
        contact = frappe.get_doc("Contact", docname)
    else:
        existing_contact = frappe.db.get_value("Contact", {"email_id": email}, "name") if email else None
        contact = frappe.get_doc("Contact", existing_contact) if existing_contact else frappe.new_doc("Contact")

    for fieldname in EDITABLE_CONTACT_FIELDS:
        if fieldname in payload and contact.meta.has_field(fieldname):
            contact.set(fieldname, payload.get(fieldname))

    first_name = (payload.get("first_name") or "").strip()
    last_name = (payload.get("last_name") or "").strip()
    full_name = (payload.get("full_name") or "").strip()
    email = (payload.get("email_id") or "").strip()
    mobile = (payload.get("mobile_no") or "").strip()
    company_name = (payload.get("company_name") or "").strip()
    
    if not full_name:
        full_name = " ".join([p for p in [first_name, last_name] if p]).strip()
    
    if not full_name and company_name:
        full_name = company_name
    
    if not full_name and email:
        full_name = email
    
    if full_name and not first_name:
        first_name = full_name
    
    contact.first_name = first_name
    contact.last_name = last_name
    contact.full_name = full_name
    contact.email_id = email
    contact.mobile_no = mobile
    contact.company_name = company_name
    contact.is_billing_contact = is_billing_contact

    if not (contact.get("first_name") or contact.get("full_name") or contact.get("company_name")):
        frappe.throw(_("Please enter at least a First Name, Full Name or Company Name."))
    
    if not contact.get("full_name"):
        contact.full_name = (
            contact.get("first_name")
            or contact.get("company_name")
            or contact.get("email_id")
            or contact.name
        )
    
    contact.save(ignore_permissions=True)

    if is_billing_contact and not contact.get("custom_customer"):
        customer_doc = frappe.new_doc("Customer")
        customer_doc.customer_type = "Individual"
        customer_doc.customer_name = (
            contact.get("full_name")
            or contact.get("company_name")
            or contact.get("email_id")
            or contact.name
        )

        customer_doc.save(ignore_permissions=True)

        contact.custom_customer = customer_doc.name
        contact.is_billing_contact = 1

        contact.append("links", {
            "link_doctype": "Customer",
            "link_name": customer_doc.name,
        })

        contact.save(ignore_permissions=True)

    if contact.get("custom_customer") and frappe.db.exists("Customer", contact.get("custom_customer")):
        customer_doc = frappe.get_doc("Customer", contact.get("custom_customer"))
        customer_doc.customer_name = (
            contact.get("full_name")
            or contact.get("company_name")
            or contact.get("email_id")
            or contact.name
        )
        customer_doc.save(ignore_permissions=True)

    if linked_client and frappe.db.exists("Client", linked_client):
        client = frappe.get_doc("Client", linked_client)

        existing_row = None

        for row in client.get("client_contacts") or []:
            if row.get("contact") == contact.name:
                existing_row = row
                break

        if not existing_row:
            existing_row = client.append("client_contacts", {})

        existing_row.contact = contact.name
        existing_row.contact_name = contact_display_name(contact)
        existing_row.email_id = contact.get("email_id") or ""
        existing_row.phone = contact.get("mobile_no") or ""
        existing_row.relationship_type = relationship_type
        existing_row.is_billing_contact = is_billing_contact

        if hasattr(existing_row, "customer"):
            existing_row.customer = contact.get("custom_customer") or ""

        if is_billing_contact and contact.get("custom_customer"):
            client.billing_contact = contact.get("custom_customer")

        client.save(ignore_permissions=True)

    frappe.db.commit()

    return {
        "name": contact.name,
        "display_name": contact_display_name(contact),
        "customer": contact.get("custom_customer") or "",
    }


@frappe.whitelist()
def save_contact(scope="coach", docname=None, data=None):
    return save_contact_for_scope(
        scope=scope or "coach",
        docname=docname,
        data=data,
    )
