import frappe


def get_client_types():
    if frappe.db.exists("DocType", "Client Type"):
        return frappe.get_all("Client Type", pluck="name", order_by="name asc")

    # fallback if no doctype exists
    return ["Kid", "Teen", "Adult", "Uni Student", "School/Company"]


def build_display_name(client):
    return (
        client.get("full_name")
        or f"{client.get('name1') or ''} {client.get('last_name') or ''}".strip()
        or client.get("name")
    )


def normalize_client_row(client):
    return {
        "name": client.get("name"),
        "display_name": build_display_name(client),
        "preferred_name": client.get("preferred_name") or "",
        "mobile": client.get("mobile") or "",
        "email": client.get("email") or "",
        "status": client.get("status") or "Archived",
        "client_type": client.get("client_type") or "Not set",
        "primary_coach": client.get("primary_coach") or "",
        "session_worker": client.get("session_worker") or "",
    }
