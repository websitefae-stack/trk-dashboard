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

CLIENT_FIELDS = [
    "name", "full_name", "name1", "last_name",
    "status", "client_type",
    "primary_coach", "attending_coach", "session_worker",
    "billing_contact",
]

CONTACT_FIELDS = [
    "name", "full_name", "first_name", "last_name",
    "mobile_no", "email_id", "designation", "company_name",
    "is_billing_contact", "custom_customer",
]


# ---------------------------------------------------------------------------
# Public name helpers (preserved signatures)
# ---------------------------------------------------------------------------

def get_current_coach_name():
    return permissions_get_current_coach_name(optional=True)


def get_current_session_worker_name():
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


# ---------------------------------------------------------------------------
# Customer/contact helpers (preserved signatures)
# ---------------------------------------------------------------------------

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

    return frappe.db.get_value(
        "Dynamic Link",
        {
            "parenttype": "Address",
            "link_doctype": "Customer",
            "link_name": customer_name,
        },
        "parent",
    ) or ""


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
    """
    Preserved public function — used by other parts of the app.
    Resolves (or creates) a Contact for a given Customer.
    Do NOT call in a loop; use _bulk_resolve_customers_to_contacts() instead.
    """
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


# ---------------------------------------------------------------------------
# Bulk customer → contact resolution (no loops, no get_doc)
# ---------------------------------------------------------------------------

def _bulk_resolve_customers_to_contacts(customer_names):
    """
    Returns {customer_name: contact_name} for all resolvable customers.
    Two queries total regardless of input size.
    Does NOT create missing contacts — use get_contact_from_customer() for that.
    """
    if not customer_names:
        return {}

    customer_names = [c for c in customer_names if c]
    if not customer_names:
        return {}

    result = {}

    rows = frappe.get_all(
        CONTACT_DOCTYPE,
        filters={"custom_customer": ["in", customer_names]},
        fields=["name", "custom_customer"],
        ignore_permissions=True,
    )
    for row in rows:
        if row.get("custom_customer") and row["custom_customer"] not in result:
            result[row["custom_customer"]] = row["name"]

    remaining = [c for c in customer_names if c not in result]
    if remaining:
        dlinks = frappe.get_all(
            "Dynamic Link",
            filters={
                "parenttype": CONTACT_DOCTYPE,
                "link_doctype": "Customer",
                "link_name": ["in", remaining],
            },
            fields=["parent", "link_name"],
            ignore_permissions=True,
        )
        for dl in dlinks:
            if dl.get("link_name") and dl["link_name"] not in result:
                result[dl["link_name"]] = dl["parent"]

    return result


def _get_client_contact_doctype():
    """Returns the child DocType name for the client_contacts field."""
    return frappe.get_meta(CLIENT_DOCTYPE).get_field("client_contacts").options


def _client_info(client):
    return {
        "name": client.get("name"),
        "display_name": get_client_display_name(client),
        "primary_coach": client.get("primary_coach") or "",
        "attending_coach": client.get("attending_coach") or "",
        "session_worker": client.get("session_worker") or "",
        "status": client.get("status") or "",
        "client_type": client.get("client_type") or "",
    }


# ---------------------------------------------------------------------------
# Core map builder — the performance heart of this module
# ---------------------------------------------------------------------------

def _build_contact_client_map(clients):
    """
    Returns {contact_name: [client_info_dict, ...]} using exactly two queries:
      1. One query on the Client Contact child table for all clients.
      2. One bulk query to resolve customer names to contact names.

    Never calls frappe.get_doc() in a loop.
    """
    if not clients:
        return {}

    client_names = [c.get("name") for c in clients]
    client_by_name = {c.get("name"): c for c in clients}

    child_doctype = _get_client_contact_doctype()

    child_rows = frappe.get_all(
        child_doctype,
        filters={"parent": ["in", client_names], "parenttype": CLIENT_DOCTYPE},
        fields=["parent", "contact", "customer", "is_billing_contact"],
        ignore_permissions=True,
    )

    # Collect all customer names that need resolving
    customer_names = set()
    for row in child_rows:
        if row.get("customer"):
            customer_names.add(row["customer"])
    for client in clients:
        if client.get("billing_contact"):
            customer_names.add(client["billing_contact"])

    customer_contact_map = _bulk_resolve_customers_to_contacts(customer_names)

    # Build contact → [client_info] without duplicates per contact
    seen = {}        # contact_name -> set of client names already added
    result = {}      # contact_name -> [client_info]

    def _add(contact_name, client_name):
        if not contact_name or not client_name:
            return
        client = client_by_name.get(client_name)
        if not client:
            return
        if contact_name not in seen:
            seen[contact_name] = set()
            result[contact_name] = []
        if client_name not in seen[contact_name]:
            seen[contact_name].add(client_name)
            result[contact_name].append(_client_info(client))

    for row in child_rows:
        client_name = row.get("parent")

        if row.get("contact"):
            _add(row["contact"], client_name)

        if row.get("is_billing_contact") and row.get("customer"):
            contact_name = customer_contact_map.get(row["customer"])
            if contact_name:
                _add(contact_name, client_name)

    for client in clients:
        bc = client.get("billing_contact")
        if bc:
            contact_name = customer_contact_map.get(bc)
            if contact_name:
                _add(contact_name, client.get("name"))

    return result


# ---------------------------------------------------------------------------
# Legacy-compatible wrappers (preserved public names)
# ---------------------------------------------------------------------------

def get_contact_names_from_clients(clients, include_billing_contact=True):
    """
    Preserved public function. Now backed by bulk queries.
    include_billing_contact kept for API compatibility; billing contacts are
    always included via the same bulk mechanism.
    """
    return sorted(_build_contact_client_map(clients).keys())


def get_linked_clients_for_contact(contact_name, clients):
    """
    Preserved public function. Now backed by bulk queries.
    Callers iterating many contacts should use get_contact_rows_for_clients()
    directly to avoid re-building the map per contact.
    """
    return _build_contact_client_map(clients).get(contact_name, [])


# ---------------------------------------------------------------------------
# Fast shared helper for view-mode pages
# ---------------------------------------------------------------------------

def get_contact_rows_for_clients(clients, scope="coach", ignore_permissions=True):
    """
    Returns fully-formatted contact rows for a given client list.
    Uses bulk queries — suitable for view-mode pages that supply their own
    client list (coach view-as, session-worker view-as, etc.).
    """
    if not clients:
        return []

    contact_client_map = _build_contact_client_map(clients)
    contact_names = list(contact_client_map.keys())

    if not contact_names:
        return []

    contacts = frappe.get_all(
        CONTACT_DOCTYPE,
        filters={"name": ["in", contact_names]},
        fields=CONTACT_FIELDS,
        order_by="full_name asc, first_name asc, last_name asc",
        limit_page_length=5000,
        ignore_permissions=ignore_permissions,
    )

    rows = _build_contact_rows(contacts, contact_client_map, scope)
    return dedupe_contacts_prefer_customer(rows)


# ---------------------------------------------------------------------------
# Allowed clients
# ---------------------------------------------------------------------------

def get_allowed_clients(scope, coach_scope="my"):
    ensure_logged_in()

    # Franchise-type clients represent coaches/HQ themselves (for cross-
    # coach/HQ invoicing) and aren't assigned to any one coach or session
    # worker - every coach/session worker needs to see them regardless
    # (matching the same carve-out in permissions.py's
    # get_allowed_client_or_filters()), otherwise a franchisee's own
    # billing contact is invisible to everyone but whoever happens to be
    # its primary/attending coach (usually nobody).

    if scope == "session_worker":
        session_worker = get_current_session_worker_name()
        if not session_worker:
            return []
        return frappe.get_all(
            CLIENT_DOCTYPE,
            filters=[
                [CLIENT_DOCTYPE, "session_worker", "=", session_worker],
                "or",
                [CLIENT_DOCTYPE, "client_type", "=", "Franchise"],
            ],
            fields=CLIENT_FIELDS,
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
                "or",
                [CLIENT_DOCTYPE, "client_type", "=", "Franchise"],
            ],
            fields=CLIENT_FIELDS,
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
            return frappe.get_all(
                CLIENT_DOCTYPE,
                fields=CLIENT_FIELDS,
                order_by="full_name asc, name1 asc, last_name asc",
                limit_page_length=10000,
            )

        coach_name = get_current_coach_name() if coach_scope.lower() == "my" else coach_scope
        if not coach_name:
            return []

        return frappe.get_all(
            CLIENT_DOCTYPE,
            filters=[
                [CLIENT_DOCTYPE, "primary_coach", "=", coach_name],
                "or",
                [CLIENT_DOCTYPE, "attending_coach", "=", coach_name],
                "or",
                [CLIENT_DOCTYPE, "client_type", "=", "Franchise"],
            ],
            fields=CLIENT_FIELDS,
            order_by="full_name asc, name1 asc, last_name asc",
            limit_page_length=10000,
        )

    return []


# ---------------------------------------------------------------------------
# Dedupe
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Row builder
# ---------------------------------------------------------------------------

def _build_contact_rows(contacts, contact_client_map, scope):
    rows = []

    for contact in contacts:
        linked_clients = contact_client_map.get(contact.get("name"), [])

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
            "name": contact.get("name"),
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

    return rows


# ---------------------------------------------------------------------------
# Core public API (preserved signatures)
# ---------------------------------------------------------------------------

def get_contacts_for_scope(scope, show_all=False, coach_scope="my"):
    ensure_logged_in()

    if scope == "franchisor" and show_all:
        if not is_franchisor_user():
            frappe.throw(_("You do not have permission to view all contacts."), frappe.PermissionError)
        allowed_clients = frappe.get_all(
            CLIENT_DOCTYPE,
            fields=CLIENT_FIELDS,
            limit_page_length=10000,
        )
    else:
        allowed_clients = get_allowed_clients(scope, coach_scope=coach_scope)

    if not allowed_clients:
        return []

    contact_client_map = _build_contact_client_map(allowed_clients)
    contact_names = list(contact_client_map.keys())

    if not contact_names:
        return []

    contacts = frappe.get_all(
        CONTACT_DOCTYPE,
        filters={"name": ["in", contact_names]},
        fields=CONTACT_FIELDS,
        order_by="full_name asc, first_name asc, last_name asc",
        limit_page_length=5000,
    )

    rows = _build_contact_rows(contacts, contact_client_map, scope)
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

    all_rows = get_contacts_for_scope(
        scope=scope,
        show_all=show_all,
        coach_scope=coach_scope,
    )

    if search:
        all_rows = [
            row for row in all_rows
            if search in (row.get("display_name") or "").lower()
            or search in (row.get("email_id") or "").lower()
            or search in (row.get("mobile_no") or "").lower()
            or search in (row.get("company_name") or "").lower()
            or search in (row.get("linked_client_text") or "").lower()
            or search in (row.get("coach_name") or "").lower()
            or search in (row.get("session_worker_name") or "").lower()
        ]

    total = len(all_rows)
    rows = all_rows[page_args["start"]:page_args["start"] + page_args["page_size"]]

    return {
        "contacts": rows,
        "pagination": make_pagination(
            total,
            page_args["page"],
            page_args["page_size"],
        ),
        "search": page_args["search"],
    }
