"""
One-off cleanup - Ashley identified Practice Document 25001/25002/25003
as accidental duplicates and tried to delete them in Desk, blocked by
Frappe's own link-protection ("Cannot delete or cancel because Practice
Document 25003 is linked with Coach Document Requirement 19003", etc.
for each of the 3).

Deletes, for each of the 3 Practice Documents: every Coach Document
Requirement row linked to it, every Client Document Share row linked to
it (the other doctype that links to Practice Document - see
allocate_document_to_client in practice_documents.py), then the
Practice Document itself. Cancels first wherever a row is submitted
(docstatus 1) - Frappe refuses to delete a submitted doc directly.

Confirmed by Ashley: just delete them, no need to check whether any
linked requirement already shows as completed by a coach.

Safe to run more than once - everything here is a no-op once already
deleted.
"""

import frappe

PRACTICE_DOCUMENT_DOCTYPE = "Practice Document"
COACH_DOCUMENT_REQUIREMENT_DOCTYPE = "Coach Document Requirement"
CLIENT_DOCUMENT_SHARE_DOCTYPE = "Client Document Share"

TARGET_PRACTICE_DOCUMENTS = ["25001", "25002", "25003"]


def _cancel_then_delete(doctype, name):
    if not frappe.db.exists(doctype, name):
        return

    doc = frappe.get_doc(doctype, name)

    if doc.meta.is_submittable and doc.docstatus == 1:
        doc.cancel()

    doc.delete(ignore_permissions=True)


def execute():
    if not frappe.db.exists("DocType", PRACTICE_DOCUMENT_DOCTYPE):
        return

    for practice_document in TARGET_PRACTICE_DOCUMENTS:
        if not frappe.db.exists(PRACTICE_DOCUMENT_DOCTYPE, practice_document):
            continue

        if frappe.db.exists("DocType", COACH_DOCUMENT_REQUIREMENT_DOCTYPE):
            requirement_names = frappe.get_all(
                COACH_DOCUMENT_REQUIREMENT_DOCTYPE,
                filters={"practice_document": practice_document},
                pluck="name",
            )
            for name in requirement_names:
                _cancel_then_delete(COACH_DOCUMENT_REQUIREMENT_DOCTYPE, name)

        if frappe.db.exists("DocType", CLIENT_DOCUMENT_SHARE_DOCTYPE):
            share_names = frappe.get_all(
                CLIENT_DOCUMENT_SHARE_DOCTYPE,
                filters={"practice_document": practice_document},
                pluck="name",
            )
            for name in share_names:
                _cancel_then_delete(CLIENT_DOCUMENT_SHARE_DOCTYPE, name)

        _cancel_then_delete(PRACTICE_DOCUMENT_DOCTYPE, practice_document)

    frappe.db.commit()
