import frappe
from frappe import _

from dashboard.api.shared.permissions import (
    ensure_logged_in,
    is_franchisor_user,
    get_current_coach_name as permissions_get_current_coach_name,
    get_current_session_worker_name as permissions_get_current_session_worker_name,
)

from dashboard.api.shared.pagination import get_page_args, make_pagination


CLIENT_DOCTYPE = "Client"
CONTACT_DOCTYPE = "Contact"
COACH_DOCTYPE = "Coach"
SESSION_WORKER_DOCTYPE = "Session Worker"


def get_current_coach_name():
    """
    Used by coach/franchisor contact pages.
    Keeps the old public function name so existing imports keep working.
    """
    return permissions_get_current_coach_name(optional=True)


def get_current_session_worker_name():
    """
    Used by session worker contact pages.
    """
    return permissions_get_current_session_worker_name(optional=True)


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

def get_customer_address(customer_name):
    if not customer_name:
        return ""

    address_name = frappe.db.get_value(
        "Address",
        {"link_doctype": "Customer", "link_name": customer_name},
        "name",
    )

    if address_name:
        return address_name

    address_name = frappe.db.get_value(
        "Dynamic Link",
        {
            "parenttype": "Address",
            "link_doctype": "Customer",
            "link_name": customer_name,
        },
        "parent",
    )

    return address_name or ""


def link_address_to_contact(address_name, contact_name):
    if not address_name or not contact_name:
        return

    if not frappe.db.exists("Address", address_name):
        return

    address = frappe.get_doc("Address", address_name)

    existing_links = {
        (row.link_doctype, row.link_name)
        for row in address.get("links") or []
    }

    if ("Contact", contact_name) not in existing_links:
        address.append("links", {
            "link_doctype": "Contact",
            "link_name": contact_name,
        })
        address.save(ignore_permissions=True)


def get_contact_from_customer(customer_name):
    if not customer_name:
        return ""

    contact = frappe.db.get_value(
        CONTACT_DOCTYPE,
        {"custom_customer": customer_name},
        "name",
    )

    if contact:
        address_name = get_customer_address(customer_name)
        if address_name:
            frappe.db.set_value(CONTACT_DOCTYPE, contact, "address", address_name)
            link_address_to_contact(address_name, contact)

        return contact

    links = frappe.get_all(
        "Dynamic Link",
        filters={
            "parenttype": CONTACT_DOCTYPE,
            "link_doctype": "Customer",
            "link_name": customer_name,
        },
        pluck="parent",
        limit_page_length=1,
    )

    if links:
        contact = links[0]
        address_name = get_customer_address(customer_name)
        if address_name:
            frappe.db.set_value(CONTACT_DOCTYPE, contact, "address", address_name)
            link_address_to_contact(address_name, contact)

        return contact

    if not frappe.db.exists("Customer", customer_name):
        return ""

    customer = frappe.get_doc("Customer", customer_name)

    contact_doc = frappe.new_doc(CONTACT_DOCTYPE)
    contact_doc.first_name = customer.customer_name or customer.name
    contact_doc.full_name = customer.customer_name or customer.name
    contact_doc.company_name = customer.customer_name or ""
    contact_doc.is_billing_contact = 1
    contact_doc.custom_customer = customer.name

    address_name = get_customer_address(customer.name)

    if address_name:
        contact_doc.address = address_name

    contact_doc.append("links", {
        "link_doctype": "Customer",
        "link_name": customer.name,
    })

    contact_doc.insert(ignore_permissions=True)

    if address_name:
        link_address_to_contact(address_name, contact_doc.name)

    customer.customer_primary_contact = contact_doc.name

    if address_name:
        customer.customer_primary_address = address_name

    customer.save(ignore_permissions=True)

    frappe.db.commit()

    return contact_doc.name


def get_allowed_clients(scope, coach_scope="my"):
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
            frappe.throw(
                _("You do not have permission to access the Franchisor Dashboard."),
                frappe.PermissionError,
            )

        coach_scope = (coach_scope or "my").strip()

        if coach_scope.lower() == "all":
            filters = {}
        else:
            coach_name = get_current_coach_name() if coach_scope.lower() == "my" else coach_scope

            if not coach_name:
                return []

            filters = [
                [CLIENT_DOCTYPE, "primary_coach", "=", coach_name],
                "or",
                [CLIENT_DOCTYPE, "attending_coach", "=", coach_name],
            ]

        return frappe.get_all(
            CLIENT_DOCTYPE,
            filters=filters,
            fields=fields,
            order_by="full_name asc, name1 asc, last_name asc",
            limit_page_length=10000,
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

        for row in client_doc.get("client_contacts") or []:
            if row.get("is_billing_contact") and row.get("customer"):
                billing_contact = get_contact_from_customer(row.get("customer"))

                if billing_contact:
                    contact_names.add(billing_contact)

        if include_billing_contact and client_doc.get("billing_contact"):
            billing_contact = get_contact_from_customer(client_doc.get("billing_contact"))

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

        if not linked and client_doc.get("billing_contact"):
            billing_contact = get_contact_from_customer(client_doc.get("billing_contact"))

            if billing_contact == contact_name:
                linked = True

        if not linked:

            for row in client_doc.get("client_contacts") or []:
        
                if not row.get("is_billing_contact"):
                    continue
        
                if not row.get("customer"):
                    continue
        
                billing_contact = get_contact_from_customer(
                    row.get("customer")
                )
        
                if billing_contact == contact_name:
                    linked = True
                    break

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


def dedupe_contacts_prefer_customer(rows):
    by_key = {}

    for row in rows:
        key = (row.get("email_id") or "").strip().lower() or row.get("name")

        existing = by_key.get(key)

        if not existing:
            by_key[key] = row
            continue

        existing_is_customer = bool(existing.get("custom_customer") or existing.get("is_billing_contact"))
        row_is_customer = bool(row.get("custom_customer") or row.get("is_billing_contact"))

        if row_is_customer and not existing_is_customer:
            by_key[key] = row

    return sorted(by_key.values(), key=lambda x: (x.get("display_name") or "").lower())


def get_contacts_for_scope(scope, show_all=False, coach_scope="my"):
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
        allowed_clients = get_allowed_clients(scope, coach_scope=coach_scope)
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

        session_worker_names = sorted({
            c.get("session_worker")
            for c in linked_clients
            if c.get("session_worker")
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
            "session_worker_name": ", ".join(session_worker_names),
        })

    return dedupe_contacts_prefer_customer(rows)


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


@frappe.whitelist()
def get_contacts(scope="coach", show_all=0, coach_scope="my"):
    """
    Shared endpoint for all dashboards.

    scope:
    - coach
    - franchisor
    - session_worker
    """
    return get_contacts_for_scope(
        scope=scope,
        show_all=bool(int(show_all or 0)),
        coach_scope=coach_scope or "my",
    )


def get_paginated_contacts_for_scope(scope, show_all=False, coach_scope="my"):
    page_args = get_page_args()
    search = page_args["search"].lower()

    if scope in ["coach", "session_worker"]:
        page_args["start"] = 0
        page_args["page"] = 1
        page_args["page_size"] = 5000

    if scope == "franchisor" and show_all:
        if not is_franchisor_user():
            frappe.throw(_("You do not have permission to view all contacts."), frappe.PermissionError)

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
        allowed_clients = get_allowed_clients(scope, coach_scope=coach_scope)

    if not allowed_clients:
        return {
            "contacts": [],
            "pagination": make_pagination(0, page_args["page"], page_args["page_size"]),
            "search": page_args["search"],
        }

    client_names = [c.get("name") for c in allowed_clients if c.get("name")]
    client_map = {c.get("name"): c for c in allowed_clients if c.get("name")}

    contact_to_client_names = {}
    customer_names = set()

    client_contact_doctype = ""
    try:
        client_contact_field = frappe.get_meta(CLIENT_DOCTYPE).get_field("client_contacts")
        client_contact_doctype = client_contact_field.options if client_contact_field else ""
    except Exception:
        client_contact_doctype = ""

    child_rows = []

    if client_contact_doctype and client_names:
        child_rows = frappe.get_all(
            client_contact_doctype,
            filters={"parent": ["in", client_names]},
            fields=["parent", "contact", "is_billing_contact", "customer"],
            limit_page_length=0,
            ignore_permissions=True,
        )

    for row in child_rows:
        parent = row.get("parent")

        if row.get("contact"):
            contact_to_client_names.setdefault(row.get("contact"), set()).add(parent)

        if row.get("is_billing_contact") and row.get("customer"):
            customer_names.add(row.get("customer"))

    for client in allowed_clients:
        if client.get("billing_contact"):
            customer_names.add(client.get("billing_contact"))

    customer_contact_map = {}

    for customer_name in customer_names:
        contact_name = get_contact_from_customer(customer_name)

        if contact_name:
            customer_contact_map[customer_name] = contact_name

    for row in child_rows:
        parent = row.get("parent")

        if row.get("is_billing_contact") and row.get("customer"):
            contact_name = customer_contact_map.get(row.get("customer"))

            if contact_name:
                contact_to_client_names.setdefault(contact_name, set()).add(parent)

    for client in allowed_clients:
        customer_name = client.get("billing_contact")
        contact_name = customer_contact_map.get(customer_name)

        if contact_name:
            contact_to_client_names.setdefault(contact_name, set()).add(client.get("name"))

    contact_names = sorted(contact_to_client_names.keys())

    if not contact_names:
        return {
            "contacts": [],
            "pagination": make_pagination(0, page_args["page"], page_args["page_size"]),
            "search": page_args["search"],
        }

    contact_filters = {"name": ["in", contact_names]}

    if search:
        contact_rows = frappe.get_all(
            CONTACT_DOCTYPE,
            filters=contact_filters,
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
            limit_page_length=0,
            ignore_permissions=True,
        )

        contact_rows = [
            c for c in contact_rows
            if search in (get_contact_display_name(c) or "").lower()
            or search in (c.get("email_id") or "").lower()
            or search in (c.get("mobile_no") or "").lower()
            or search in (c.get("company_name") or "").lower()
        ]

        total = len(contact_rows)
        contact_rows = contact_rows[page_args["start"]:page_args["start"] + page_args["page_size"]]

    else:
        total = len(contact_names)

        contact_rows = frappe.get_all(
            CONTACT_DOCTYPE,
            filters=contact_filters,
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
            start=page_args["start"],
            page_length=page_args["page_size"],
            ignore_permissions=True,
        )

    rows = []

    for contact in contact_rows:
        linked_clients = []

        for client_name in sorted(contact_to_client_names.get(contact.name, set())):
            client = client_map.get(client_name)

            if not client:
                continue

            linked_clients.append({
                "name": client.get("name"),
                "display_name": get_client_display_name(client),
                "primary_coach": client.get("primary_coach") or "",
                "attending_coach": client.get("attending_coach") or "",
                "session_worker": client.get("session_worker") or "",
                "status": client.get("status") or "",
                "client_type": client.get("client_type") or "",
            })

        coach_names = sorted({
            c.get("primary_coach") or c.get("attending_coach")
            for c in linked_clients
            if c.get("primary_coach") or c.get("attending_coach")
        })

        session_worker_names = sorted({
            c.get("session_worker")
            for c in linked_clients
            if c.get("session_worker")
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
            "session_worker_name": ", ".join(session_worker_names),
        })

    return {
        "contacts": rows,
        "pagination": make_pagination(
            total,
            page_args["page"],
            page_args["page_size"],
        ),
        "search": page_args["search"],
    }
