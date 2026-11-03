"""
Ashley asked that Practice Document always list alphabetically (by
title), rather than Desk's own default (most recently updated first) -
confirmed live, the list view was jumbling duplicates/related documents
out of title order (e.g. 25001/25003/25002 instead of 25001/25002/25003).

Sets the DocType's own sort_field/sort_order, which is what Desk's list
view falls back to whenever nobody's picked a different sort for their
own session - this doesn't override someone's own manually-chosen sort,
just the default everyone otherwise lands on.

Safe to run more than once.
"""

import frappe

DOCTYPE = "Practice Document"


def execute():
    if not frappe.db.exists("DocType", DOCTYPE):
        return

    meta = frappe.get_meta(DOCTYPE)
    if not meta.has_field("document_title"):
        return

    frappe.db.set_value("DocType", DOCTYPE, {"sort_field": "document_title", "sort_order": "ASC"})
    frappe.clear_cache(doctype=DOCTYPE)
    frappe.db.commit()
