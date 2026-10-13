"""
Adds Knowledge Vault Resource.text_content - not every resource is a
file or a video. Confirmed live: some of the real content being loaded
in is plain text/instructions (e.g. email wording to copy), with no
image, link or file at all - the original doctype (file + video_url
only) had nowhere for that to go, so those resources were being saved
with nothing anyone could actually see.

Safe to run more than once - create_custom_fields skips any field that
already exists.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

RESOURCE_DOCTYPE = "Knowledge Vault Resource"

FIELDS = [
    {
        "fieldname": "text_content",
        "fieldtype": "Text",
        "label": "Text Content",
        "insert_after": "video_url",
        "description": "Plain text/instructions shown directly on the resource - for content that isn't a file or a video (e.g. email wording to copy).",
    },
]


def execute():
    create_custom_fields({RESOURCE_DOCTYPE: FIELDS}, ignore_validate=True)
    frappe.db.commit()
