import frappe
from frappe import _

from dashboard.api.shared.permissions import (
    CLIENT_DOCTYPE,
    COACH_DOCTYPE,
    get_allowed_client_or_filters,
    get_client_permissions,
    get_current_user_own_linked_client,
    ensure_client_access,
    ensure_logged_in,
)

from dashboard.api.shared.pagination import get_page_args, make_pagination


CLIENT_FIELDS = [
    "name",
    "name1",
    "last_name",
    "full_name",
    "preferred_name",
    "mobile",
    "email",
    "status",
    "client_type",
    "primary_coach",
    "attending_coach",
    "session_worker",
]


def get_client_types():
    if frappe.db.exists("DocType", "Client Type"):
        return frappe.get_all("Client Type", pluck="name", order_by="name asc")

    meta = frappe.get_meta(CLIENT_DOCTYPE)

    if meta.has_field("client_type"):
        df = meta.get_field("client_type")

        if df.fieldtype == "Select" and df.options:
            return [x.strip() for x in df.options.split("\n") if x.strip()]

    return ["Kid", "Teen", "Uni Student", "Adult", "School", "Company", "Franchise"]


def build_display_name(client):
    first_name = client.get("name1") or client.get("first_name") or ""
    last_name = client.get("last_name") or ""
    preferred_name = client.get("preferred_name") or ""

    formal_name = (
        client.get("full_name")
        or f"{first_name} {last_name}".strip()
        or client.get("name")
    )

    if preferred_name and first_name and preferred_name.strip().lower() != first_name.strip().lower():
        return f"{preferred_name} {last_name}".strip() + f" ({first_name})"

    return formal_name


def get_coach_label(coach_name):
    if not coach_name:
        return ""

    if not frappe.db.exists(COACH_DOCTYPE, coach_name):
        return coach_name

    return (
        frappe.db.get_value(COACH_DOCTYPE, coach_name, "coach_name")
        or coach_name
    )


def normalize_client_row(client, include_permissions=False):
    row = {
        "name": client.get("name"),
        "display_name": build_display_name(client),
        "full_name": client.get("full_name") or "",
        "name1": client.get("name1") or "",
        "last_name": client.get("last_name") or "",
        "preferred_name": client.get("preferred_name") or "",
        "mobile": client.get("mobile") or "",
        "email": client.get("email") or "",
        "status": client.get("status") or "Archived",
        "client_type": client.get("client_type") or "Not set",
        "primary_coach": client.get("primary_coach") or "",
        "primary_coach_label": get_coach_label(client.get("primary_coach")),
        "attending_coach": client.get("attending_coach") or "",
        "attending_coach_label": get_coach_label(client.get("attending_coach")),
        "session_worker": client.get("session_worker") or "",
    }

    if include_permissions:
        row["permissions"] = get_client_permissions(client.get("name"))

    return row


@frappe.whitelist()
def get_clients():
    ensure_logged_in()

    or_filters = get_allowed_client_or_filters()
    own_linked_client = get_current_user_own_linked_client()

    args = {
        "doctype": CLIENT_DOCTYPE,
        "fields": CLIENT_FIELDS,
        "order_by": "full_name asc",
        "limit_page_length": 5000,
    }

    if or_filters is not None:
        args["or_filters"] = or_filters

    if own_linked_client:
        # A coach's own linked_client (their internal billing record) is
        # visible to every coach as a Franchise-type client so franchisees
        # can invoice each other - but it isn't a client of theirs, so it
        # shouldn't show up in their own Clients list.
        args["filters"] = {"name": ["!=", own_linked_client]}

    clients = frappe.get_all(**args)

    return [normalize_client_row(c, include_permissions=True) for c in clients]


def _get_client_filter_args():
    """
    client_type/status/session_worker/coach for the franchisor Clients
    page, read straight off the query string like page_args["search"] -
    these used to be client-side-only filters applied after pagination had
    already sliced the rows, so paging past the first page silently
    dropped them (the dropdowns have no server-restored selected state)
    and showed an unrelated page's worth of clients with the filter
    dropdowns reset to "All". Same fix pattern as the invoices list.
    """
    return {
        "client_type": (frappe.form_dict.get("client_type") or "").strip(),
        "status": (frappe.form_dict.get("status") or "").strip(),
        "session_worker": (frappe.form_dict.get("session_worker") or "").strip(),
        "coach": (frappe.form_dict.get("coach") or "").strip(),
    }


def _apply_client_filter_args(filters, filter_args):
    client_type = filter_args["client_type"]
    status = filter_args["status"]
    session_worker = filter_args["session_worker"]
    coach = filter_args["coach"]

    if client_type and client_type != "All":
        filters.append(["client_type", "=", client_type])

    if status and status != "All":
        filters.append(["status", "=", status])

    # Franchise-type clients represent coaches themselves (for cross-coach/
    # HQ invoicing) and aren't assigned to any one coach or session worker,
    # so the Session Worker/Coach filters must never hide them - resolved
    # here (rather than as a plain equality filter) so that carve-out
    # still applies, matching the previous client-side clientMatches().
    if session_worker and session_worker != "All":
        names = frappe.get_all(
            CLIENT_DOCTYPE,
            or_filters=[
                ["session_worker", "=", session_worker],
                ["client_type", "=", "Franchise"],
            ],
            pluck="name",
            limit_page_length=0,
        )
        filters.append(["name", "in", names])

    if coach and coach != "All":
        names = frappe.get_all(
            CLIENT_DOCTYPE,
            or_filters=[
                ["primary_coach", "=", coach],
                ["attending_coach", "=", coach],
                ["client_type", "=", "Franchise"],
            ],
            pluck="name",
            limit_page_length=0,
        )
        filters.append(["name", "in", names])

    return filters


def get_paginated_clients():
    ensure_logged_in()

    page_args = get_page_args()
    search = page_args["search"]
    filter_args = _get_client_filter_args()

    path = ""
    try:
        path = frappe.request.path or ""
    except Exception:
        path = ""

    load_all_for_dashboard = (
        "/coach_db/clients" in path
        or "/session_worker_db/clients" in path
    )

    if load_all_for_dashboard:
        page_args["start"] = 0
        page_args["page"] = 1
        page_args["page_size"] = 5000

    filters = []

    if search:
        # Some clients (e.g. Franchise-type records representing a coach
        # for cross-coach/HQ invoicing) may not have full_name populated,
        # only name1/last_name/preferred_name - search across all of them
        # so those records are still findable by name.
        search_names = frappe.get_all(
            CLIENT_DOCTYPE,
            or_filters=[
                ["full_name", "like", f"%{search}%"],
                ["name1", "like", f"%{search}%"],
                ["last_name", "like", f"%{search}%"],
                ["preferred_name", "like", f"%{search}%"],
            ],
            pluck="name",
            limit_page_length=0,
        )

        if not search_names:
            return {
                "clients": [],
                "pagination": make_pagination(0, page_args["page"], page_args["page_size"]),
                "search": search,
                **filter_args,
            }

        filters.append(["name", "in", search_names])

    if not load_all_for_dashboard:
        _apply_client_filter_args(filters, filter_args)

    own_linked_client = get_current_user_own_linked_client()
    if own_linked_client:
        # A coach's own linked_client (their internal billing record) is
        # visible to every coach as a Franchise-type client so franchisees
        # can invoice each other - but it isn't a client of theirs, so it
        # shouldn't show up in their own Clients list.
        filters.append(["name", "!=", own_linked_client])

    or_filters = get_allowed_client_or_filters()

    args = {
        "doctype": CLIENT_DOCTYPE,
        "fields": CLIENT_FIELDS,
        "filters": filters,
        "order_by": "full_name asc",
        "start": page_args["start"],
        "page_length": page_args["page_size"],
    }

    count_args = {
        "filters": filters,
    }

    if or_filters is not None:
        args["or_filters"] = or_filters
        count_args["or_filters"] = or_filters

    rows = frappe.get_all(**args)

    total_rows = frappe.get_all(
        CLIENT_DOCTYPE,
        filters=count_args.get("filters"),
        or_filters=count_args.get("or_filters"),
        pluck="name",
        limit_page_length=0,
    )

    total = len(total_rows)
    return {
        "clients": [
            normalize_client_row(c, include_permissions=True)
            for c in rows
        ],
        "pagination": make_pagination(
            total,
            page_args["page"],
            page_args["page_size"],
        ),
        "search": search,
        **filter_args,
    }


@frappe.whitelist()
def get_client(client_name):
    ensure_logged_in()
    client = ensure_client_access(client_name)

    data = normalize_client_row(client.as_dict(), include_permissions=True)
    return data


@frappe.whitelist()
def get_client_page_context():
    """
    Optional helper for pages that want filters and clients from one API.
    """

    ensure_logged_in()

    clients = get_clients()

    return {
        "clients": clients,
        "client_types": get_client_types(),
    }
