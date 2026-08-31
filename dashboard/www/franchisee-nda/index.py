import re

import frappe

# frappe.generate_hash() output is alphanumeric only - anything else in
# the query string is either a mistyped/corrupted link or someone
# probing it, never a real token. Stripped here (rather than trusted
# straight into the page's own <script> block) so what actually reaches
# the template is always safe to embed as a bare JS string literal.
_TOKEN_PATTERN = re.compile(r"[^a-zA-Z0-9]")


def get_context(context):
    context.no_cache = 1
    context.page_title = "Non-Disclosure Agreement"
    context.token = _TOKEN_PATTERN.sub("", frappe.form_dict.get("token") or "")
