import re

import frappe
from frappe import _

# autoname "hash" output is alphanumeric only - this is embedded directly
# into the page's own <script> block as a bare JS string literal, so
# anything else in the query string (a mistyped/corrupted link, or someone
# probing it) is stripped before it ever reaches the template.
_NAME_PATTERN = re.compile(r"[^a-zA-Z0-9]")


def get_context(context):
    if frappe.session.user == "Guest":
        frappe.throw(_("Login required"), frappe.PermissionError)

    context.no_cache = 1
    context.page_title = "Client Transfer Agreement"
    context.transfer_name = _NAME_PATTERN.sub("", frappe.form_dict.get("name") or "")
