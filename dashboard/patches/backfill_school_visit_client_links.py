"""
One-time backfill: a School Visit/Company Meeting/School Session/Company
Session can be booked either by picking an existing School/Company Client
from a dropdown (school) or by just typing the name in free text
(school_manual_name) - see create_booking()'s own SCHOOL_LINKED_TYPES
handling in calendar.py. The typed-name path never sets custom_visit_client
(or custom_client, for the two pack-billed types) at all - the name only
ever ends up baked into the Event's own subject text ("Oak Cottage - School
Visit") - so every one of those bookings shows as "NOT YET LINKED" in the
Edit Session modal and has to be manually re-picked from the school
dropdown one at a time to actually link it, even when a Client record with
that exact name already exists (as it usually does - most of these are the
same handful of schools booked repeatedly).

This finds every such unlinked SCHOOL_LINKED_TYPES Event, recovers the
typed name from its subject (which is always built as "{name} -
{appointment_type}" - see create_booking()), and links it automatically
wherever that name matches exactly one existing School/Company Client by
display name. Only an exact, unambiguous match is auto-linked - anything
that matches zero or more than one Client is left alone and listed in a
summary Error Log entry for manual review, rather than risk linking the
wrong school automatically.

School Session/Company Session go through a normal doc.save() (these are
pack-billed against custom_client, and saving is what triggers the
existing Package Recalculate Balance logic) - School Visit/Company Meeting
are plain non-billable visits, so those are updated directly for speed
without needing that.

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

    # Build an exact-name -> Client lookup, restricted to School/Company
    # records (the only two types the school-linking dropdown ever offers)
    # - and drop any name that isn't unique, since an ambiguous match is
    # exactly the case that must be left for a human to pick correctly.
    name_field = "full_name" if client_meta.has_field("full_name") else "name"
    org_clients = frappe.get_all(
        "Client",
        filters={"client_type": ["in", ["School", "Company"]]},
        fields=["name", name_field],
    )

    by_name = {}
    ambiguous = set()
    for row in org_clients:
        key = (row.get(name_field) or "").strip().lower()
        if not key:
            continue
        if key in by_name and by_name[key] != row["name"]:
            ambiguous.add(key)
        else:
            by_name[key] = row["name"]

    for key in ambiguous:
        by_name.pop(key, None)

    if not by_name:
        return

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
            unresolved.append(f"{row['name']} (subject: {subject!r} - unexpected format)")
            continue

        candidate_name = subject[: -len(suffix)].strip()
        client = by_name.get(candidate_name.lower())

        if not client:
            unresolved.append(f"{row['name']} (typed name: {candidate_name!r} - no unique Client match)")
            continue

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
            frappe.log_error(frappe.get_traceback(), f"Backfill School Visit Link – {row['name']}")

    frappe.db.commit()

    if linked or unresolved:
        message = f"Auto-linked {linked} school/company calendar item(s) to their matching Client record.\n\n"
        if unresolved:
            message += (
                f"{len(unresolved)} item(s) could not be auto-linked (no exact, unambiguous Client "
                f"name match) - these still need the school picked manually from the Edit Session "
                f"modal:\n" + "\n".join(unresolved[:200])
            )
            if len(unresolved) > 200:
                message += f"\n... and {len(unresolved) - 200} more."

        frappe.log_error(message, "Backfill School Visit Client Links – summary")
