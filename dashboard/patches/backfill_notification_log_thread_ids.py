"""
add_notification_log_thread_id.py only added the custom_thread_id field -
it never stamped one onto notifications that already existed, so every
"send to N recipients" call made before that fix still shows as N separate
cards instead of one shared conversation (see notifications.js's bucketFor
and _dedupe_notification_log_rows_by_thread in notifications.py).

There's no reliable record of which historical rows were originally part
of the same "send to N people" call - Notification Log's own schema never
tracked that. This is a best-effort heuristic backfill, not a perfect
reconstruction: rows with no thread_id yet are grouped by
(subject, message, from_user, linked document, creation rounded to the
minute) - a genuine multi-recipient send always shares all of those,
since every recipient's row is inserted in the same request. The
(small, accepted) risk is two different multi-recipient sends with
identical subject/message/sender/linked-record landing in the same
minute getting merged into one thread when they should be two - judged
unlikely enough in practice to be worth actually fixing the historical
mess. Groups of size 1 (nothing to merge) are left alone.

Also unions each group's existing custom_replies (deduped by
sent_by/sent_on/message) onto every row in the group, so scattered
replies from before this fix - written to whichever single row the
replier happened to be looking at - become visible on every card in the
newly-shared thread instead of staying stuck on just one of them.
"""

import frappe

NOTIFICATION_DOCTYPE = "Notification Log"


def execute():
    if not frappe.db.exists("DocType", NOTIFICATION_DOCTYPE):
        return

    meta = frappe.get_meta(NOTIFICATION_DOCTYPE)

    if not meta.has_field("custom_thread_id"):
        return

    has_replies_field = meta.has_field("custom_replies")

    rows = frappe.get_all(
        NOTIFICATION_DOCTYPE,
        filters={"custom_thread_id": ["in", ["", None]]},
        fields=["name", "subject", "email_content", "from_user", "document_type", "document_name", "creation"],
        order_by="creation asc",
        limit_page_length=0,
    )

    groups = {}
    for row in rows:
        creation_bucket = row.creation.strftime("%Y-%m-%d %H:%M") if row.creation else ""
        key = (
            row.subject or "",
            row.email_content or "",
            row.from_user or "",
            row.document_type or "",
            row.document_name or "",
            creation_bucket,
        )
        groups.setdefault(key, []).append(row.name)

    for names in groups.values():
        if len(names) < 2:
            continue

        thread_id = frappe.generate_hash(length=12)
        docs = [frappe.get_doc(NOTIFICATION_DOCTYPE, name) for name in names]

        merged_replies = None

        if has_replies_field:
            seen = set()
            merged_replies = []

            for doc in docs:
                for reply in doc.get("custom_replies") or []:
                    reply_key = (reply.get("sent_by"), str(reply.get("sent_on")), reply.get("message"))
                    if reply_key in seen:
                        continue
                    seen.add(reply_key)
                    merged_replies.append({
                        "message": reply.get("message"),
                        "attachment": reply.get("attachment"),
                        "sent_by": reply.get("sent_by"),
                        "sent_by_label": reply.get("sent_by_label"),
                        "sent_on": reply.get("sent_on"),
                    })

            merged_replies.sort(key=lambda r: str(r.get("sent_on") or ""))

        for doc in docs:
            doc.custom_thread_id = thread_id

            if merged_replies is not None:
                doc.set("custom_replies", [])
                for reply in merged_replies:
                    doc.append("custom_replies", reply)

            doc.save(ignore_permissions=True)

    frappe.db.commit()
