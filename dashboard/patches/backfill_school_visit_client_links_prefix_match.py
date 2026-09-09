"""
Follow-up to backfill_school_visit_client_links: that patch only linked a
typed name to a Client when it matched the Client's full name exactly -
"Oak Cottage" links to a Client literally named "Oak Cottage" fine, but
someone typing just "Langley" for "Langley School" matched nothing at
all, even though there's obviously only one school that could be, and
was left for manual review instead of being linked.

Adds a second, still-conservative pass: for anything still unlinked, also
match when the typed name is the START of a School/Company Client's full
name followed by a space (so "Langley" -> "Langley School" or "Langley
Primary School", but never "Langley" -> "Langleybury" or some unrelated
"Langley Road Company"-type false match on a shared prefix mid-word).
Still only auto-links an UNAMBIGUOUS match - typed text matching the start
of more than one Client's name is left alone, same as before.

Runs automatically on the next `bench migrate` (part of a normal deploy) -
no manual step needed.
"""

import frappe

SCHOOL_LINKED_TYPES = ("School Visit", "Company Meeting", "School Session", "Company Session")
PACK_LINKED_SCHOOL_TYPES = ("School Session", "Company Session")


def execute():
    if not frappe.db.exists("DocType", "Event") or not frappe.db.exists("DocType", "Client"):
        return

    event_meta = frappe.get_meta("Event")
    if not event_meta.has_field("custom_visit_client") or not event_meta.has_field("custom_session_type"):
        return

    client_meta = frappe.get_meta("Client")
    if not client_meta.has_field("client_type"):
        return

    name_field = "full_name" if client_meta.has_field("full_name") else "name"
    org_clients = frappe.get_all(
        "Client",
        filters={"client_type": ["in", ["School", "Company"]]},
        fields=["name", name_field],
    )

    org_names = [
        (row["name"], (row.get(name_field) or "").strip())
        for row in org_clients
        if (row.get(name_field) or "").strip()
    ]

    unlinked = frappe.get_all(
        "Event",
        filters={
            "custom_session_type": ["in", list(SCHOOL_LINKED_TYPES)],
            "custom_visit_client": ["in", ["", None]],
        },
        fields=["name", "subject", "custom_session_type"],
    )

    linked = 0
    unresolved = []

    for row in unlinked:
        subject = (row.get("subject") or "").strip()
        session_type = row.get("custom_session_type")
        suffix = f" - {session_type}"
        if not subject.endswith(suffix):
            continue

        candidate_name = subject[: -len(suffix)].strip().lower()
        if not candidate_name:
            continue

        prefix = candidate_name + " "
        matches = [
            client_id for client_id, full_name in org_names
            if full_name.lower() == candidate_name or full_name.lower().startswith(prefix)
        ]
        matches = list(dict.fromkeys(matches))

        if len(matches) != 1:
            if len(matches) > 1:
                unresolved.append(f"{row['name']} (typed name: {candidate_name!r} - matches {len(matches)} clients)")
            continue

        client = matches[0]

        try:
            if session_type in PACK_LINKED_SCHOOL_TYPES:
                doc = frappe.get_doc("Event", row["name"])
                doc.custom_visit_client = client
                if event_meta.has_field("custom_client"):
                    doc.custom_client = client
                doc.save(ignore_permissions=True)
            else:
                frappe.db.set_value("Event", row["name"], "custom_visit_client", client, update_modified=False)
            linked += 1
        except Exception:
            frappe.log_error(frappe.get_traceback(), f"Backfill School Visit Link (prefix) – {row['name']}")

    frappe.db.commit()

    if linked or unresolved:
        message = f"Auto-linked {linked} more school/company calendar item(s) via a prefix match on the Client name.\n\n"
        if unresolved:
            message += (
                f"{len(unresolved)} item(s) matched more than one Client by prefix and were left alone - "
                f"these need the school picked manually:\n" + "\n".join(unresolved[:200])
            )
        frappe.log_error(message, "Backfill School Visit Client Links (prefix match) – summary")
