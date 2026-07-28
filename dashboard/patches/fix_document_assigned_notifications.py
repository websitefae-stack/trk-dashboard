"""
Retroactive cleanup for Coach Document Requirement assignment
notifications created with the invalid conversation_type "Document
Assigned" (fixed going forward in
api/shared/practice_documents.notify_requirement_assigned). Existing
records with that value fail validation on their very next save (e.g.
archiving), since "Document Assigned" was never one of Dashboard
Conversation's valid Type options.

This also applies the new rule that only Acknowledge/Sign assignments
belong in the notifications inbox at all - a "Read Only" document is
just a file sitting in the library, not something requiring action, so
those existing notifications are removed rather than only having their
type corrected.
"""

import frappe

CONVERSATION_DOCTYPE = "Dashboard Conversation"
MESSAGE_DOCTYPE = "Dashboard Conversation Message"
REQUIREMENT_DOCTYPE = "Coach Document Requirement"

REQUIRED_ACTION_NOTIFICATION_TYPE = {
    "Acknowledge": "Task",
    "Sign": "Approval Request",
}


def execute():
    if not frappe.db.exists("DocType", CONVERSATION_DOCTYPE):
        return

    rows = frappe.get_all(
        CONVERSATION_DOCTYPE,
        filters={"conversation_type": "Document Assigned"},
        fields=["name", "reference_doctype", "reference_name"],
    )

    for row in rows:
        required_action = None

        if (
            row.reference_doctype == REQUIREMENT_DOCTYPE
            and row.reference_name
            and frappe.db.exists(REQUIREMENT_DOCTYPE, row.reference_name)
        ):
            required_action = frappe.db.get_value(REQUIREMENT_DOCTYPE, row.reference_name, "required_action")

        notification_type = REQUIRED_ACTION_NOTIFICATION_TYPE.get(required_action)

        if notification_type:
            frappe.db.set_value(CONVERSATION_DOCTYPE, row.name, "conversation_type", notification_type)
            continue

        # Read Only (or the requirement no longer exists) - this shouldn't
        # have been notified about at all, so remove it rather than leave
        # a stray "just a file" notice sitting in anyone's inbox.
        if frappe.db.exists("DocType", MESSAGE_DOCTYPE):
            for message_name in frappe.get_all(MESSAGE_DOCTYPE, filters={"conversation": row.name}, pluck="name"):
                frappe.delete_doc(MESSAGE_DOCTYPE, message_name, ignore_permissions=True, force=True)

        frappe.delete_doc(CONVERSATION_DOCTYPE, row.name, ignore_permissions=True, force=True)

    frappe.db.commit()
