import frappe
from frappe import _

from dashboard.api.shared.contacts import get_contacts_for_scope
from dashboard.api.shared.session_worker_view_mode import get_session_worker_view_mode


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
    context.page_title = "Contacts"
    context.active_page = "contacts"
    context.dashboard_notifications_url = "/session_worker_db/notifications"

    context.session_worker_view_mode = view_mode
    context.session_worker_view_query = view_mode.get("query_string") or ""
    context.session_worker_is_view_mode = view_mode.get("is_view_mode") or 0
    context.session_worker_view_return_to = view_mode.get("return_to") or ""
    context.session_worker_view_display_name = view_mode.get("view_worker_display_name") or ""

    if context.session_worker_is_view_mode:
        context.dashboard_user_name = context.session_worker_view_display_name
        context.contacts = get_contacts_for_view_session_worker(
            view_mode.get("view_worker_name")
        )
    else:
        context.dashboard_user_name = frappe.db.get_value(
            "Session Worker",
            {"user": frappe.session.user},
            "sw_name",
        ) or frappe.session.user

        context.contacts = get_contacts_for_scope("session_worker")


def get_contacts_for_view_session_worker(worker_name):
    worker_name = (worker_name or "").strip()

    if not worker_name:
        return []

    clients = frappe.get_all(
        "Client",
        filters={"session_worker": worker_name},
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
        order_by="full_name asc, name1 asc, last_name asc",
        limit_page_length=5000,
        ignore_permissions=True,
    )

    if not clients:
        return []

    contact_names = get_contact_names_from_clients_for_view(clients)

    if not contact_names:
        return []

    contacts = frappe.get_all(
        "Contact",
        filters={"name": ["in", contact_names]},
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
        ignore_permissions=True,
    )

    rows = []

    for contact in contacts:
        linked_clients = get_linked_clients_for_contact_for_view(
            contact.name,
            clients,
        )

        rows.append({
            "name": contact.name,
            "display_name": (
                contact.full_name
                or " ".join(
                    part for part in [contact.first_name, contact.last_name] if part
                )
                or contact.company_name
                or contact.name
            ),
            "mobile_no": contact.mobile_no or "",
            "email_id": contact.email_id or "",
            "designation": contact.designation or "",
            "company_name": contact.company_name or "",
            "is_billing_contact": contact.is_billing_contact or 0,
            "custom_customer": contact.custom_customer or "",
            "linked_clients": linked_clients,
            "linked_client_text": ", ".join(
                [c.get("display_name") for c in linked_clients if c.get("display_name")]
            ),
        })

    return rows


def get_contact_names_from_clients_for_view(clients):
    contact_names = set()

    for client in clients:
        try:
            client_doc = frappe.get_doc("Client", client.name)
        except Exception:
            continue

        for row in client_doc.get("client_contacts") or []:
            if row.get("contact"):
                contact_names.add(row.get("contact"))

        billing_contact = get_contact_from_customer_for_view(
            client.get("billing_contact")
        )

        if billing_contact:
            contact_names.add(billing_contact)

    return sorted(contact_names)


def get_contact_from_customer_for_view(customer_name):
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


def get_linked_clients_for_contact_for_view(contact_name, clients):
    linked_clients = []

    for client in clients:
        linked = False

        try:
            client_doc = frappe.get_doc("Client", client.name)
        except Exception:
            continue

        for row in client_doc.get("client_contacts") or []:
            if row.get("contact") == contact_name:
                linked = True
                break

        if not linked:
            billing_contact = get_contact_from_customer_for_view(
                client.get("billing_contact")
            )

            if billing_contact == contact_name:
                linked = True

        if linked:
            linked_clients.append({
                "name": client.name,
                "display_name": (
                    client.get("full_name")
                    or " ".join(
                        part for part in [client.get("name1"), client.get("last_name")] if part
                    )
                    or client.name
                ),
                "status": client.get("status") or "",
                "client_type": client.get("client_type") or "",
                "primary_coach": client.get("primary_coach") or "",
                "attending_coach": client.get("attending_coach") or "",
                "session_worker": client.get("session_worker") or "",
            })

    return linked_clients
