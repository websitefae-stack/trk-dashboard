import re

import frappe

_TOKEN_PATTERN = re.compile(r"[^a-zA-Z0-9]")


def get_context(context):
    context.no_cache = 1
    context.page_title = "Franchisee Intake Form"
    context.token = _TOKEN_PATTERN.sub("", frappe.form_dict.get("token") or "")
