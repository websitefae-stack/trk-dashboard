import frappe
from frappe import _

from dashboard.api.shared.contact_details import get_contact_context
from dashboard.api.shared.session_worker_view_mode import (
    get_session_worker_view_mode,
    get_clients_for_view_session_worker,
)


def get_context(context):
    if frappe.session.user == "Guest":
        frappe.throw(_("Login required"), frappe.PermissionError)

    view_as = frappe.form_dict.get("view_as")
    viewer = frappe.form_dict.get("viewer")

    view_mode = get_session_worker_view_mode(
        scope=viewer,
        worker_name=view_as,
    )

    context.no_cache = 1
    context.active_page = "contacts"
    context.dashboard_notifications_url = "/session_worker_db/notifications"

    context.session_worker_view_mode = view_mode
    context.session_worker_view_query = view_mode.get("query_string") or ""
    context.session_worker_is_view_mode = view_mode.get("is_view_mode") or 0
    context.session_worker_view_return_to = view_mode.get("return_to") or ""
    context.session_worker_view_display_name = view_mode.get("view_worker_display_name") or ""

    if context.session_worker_is_view_mode:
        context.dashboard_user_name = context.session_worker_view_display_name

        data = get_contact_context_for_view_session_worker(
            contact_name=frappe.form_dict.get("name"),
            worker_name=view_mode.get("view_worker_name"),
        )

    else:
        context.dashboard_user_name = frappe.db.get_value(
            "Session Worker",
            {"user": frappe.session.user},
            "sw_name",
        ) or frappe.session.user

        data = get_contact_context(
            scope="session_worker",
            contact_name=frappe.form_dict.get("name"),
            is_new=False,
        )

    context.page_title = data["contact_display_name"]

    for key, value in data.items():
        context[key] = value


def get_contact_context_for_view_session_worker(contact_name, worker_name):
    contact_name = (contact_name or "").strip()
    worker_name = (worker_name or "").strip()

    if not contact_name:
        frappe.throw(_("Contact not found."))

    if not worker_name:
        frappe.throw(_("Session Worker not found."), frappe.PermissionError)

    if not frappe.db.exists("Contact", contact_name):
        frappe.throw(_("Contact not found."))

    clients = get_clients_for_view_session_worker(worker_name)
    linked_clients = get_linked_clients_for_view_contact(contact_name, clients)

    if not linked_clients:
        frappe.throw(
            _("You do not have permission to view this contact for this session worker."),
            frappe.PermissionError,
        )

    contact = frappe.get_doc("Contact", contact_name)

    return {
        "contact": contact,
        "contact_display_name": get_contact_display_name(contact),
        "is_new": 0,
        "linked_clients": linked_clients,
        "contact_invoices": [],
        "contact_details_scope": "session_worker",
        "contact_details_base_url": "/session_worker_db",
        "contact_details_save_method": "dashboard.api.shared.contact_details.save_contact",
    }


def get_linked_clients_for_view_contact(contact_name, clients):
    linked_clients = []

    for client in clients:
        client_name = client.get("name")

        if not client_name or not frappe.db.exists("Client", client_name):
            continue

        client_doc = frappe.get_doc("Client", client_name)

        linked = False
        relationship = "Client Contact"

        for row in client_doc.get("client_contacts") or []:
            if row.get("contact") == contact_name:
                linked = True
                relationship = row.get("relationship") or "Client Contact"
                break

        if not linked:
            billing_contact = get_contact_from_customer(client_doc.get("billing_contact"))

            if billing_contact == contact_name:
                linked = True
                relationship = "Billing Contact"

        if linked:
            linked_clients.append({
                "name": client_doc.name,
                "display_name": get_client_display_name(client_doc),
                "status": client_doc.get("status") or "",
                "client_type": client_doc.get("client_type") or "",
                "primary_coach": client_doc.get("primary_coach") or "",
                "primary_coach_display": client_doc.get("primary_coach") or "",
                "relationship": relationship,
                "is_billing_client": relationship == "Billing Contact",
                "is_general_linked": relationship != "Billing Contact",
            })

    return linked_clients


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
        ignore_permissions=True,
    )

    return links[0] if links else ""


def get_contact_display_name(contact):
    return (
        contact.get("full_name")
        or " ".join(
            part for part in [
                contact.get("first_name"),
                contact.get("last_name"),
            ]
            if part
        )
        or contact.get("company_name")
        or contact.get("name")
        or "Contact Details"
    )


def get_client_display_name(client):
    return (
        client.get("full_name")
        or " ".join(
            part for part in [
                client.get("name1"),
                client.get("last_name"),
            ]
            if part
        )
        or client.get("name")
        or ""
    )
