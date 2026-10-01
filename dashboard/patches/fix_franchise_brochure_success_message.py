"""
Fixes two compounding bugs in the "Franchise Brochure Request" web
form's success_message (set in create_franchise_brochure_request_form.
py, which only runs once - an already-live site needs a separate patch
to update it):

1. Frappe's current web form renderer doesn't render success_message
   as HTML - it was showing the raw "<p>Thanks! <a href=...>" tags as
   visible text to the visitor instead of a clickable link.

2. Even rendered correctly, that link pointed at /franchise-brochure
   with no token - resilient_domains' own index.py always bounces a
   tokenless visit straight back to this same request form (see its
   NO_ACCESS_REDIRECT), so it could never have worked anyway.

Switches to a plain-text message with no markup and no link, matching
what the original patch's own docstring already said was the intended
design: the real, working, token-bearing link only ever comes through
the email send_brochure_link fires immediately after this insert.
"""

import frappe

WEB_FORM_ROUTE = "franchise-brochure-request"

NEW_SUCCESS_MESSAGE = (
    "Thanks! Check your email - we've just sent your personal link to the brochure."
)


def execute():
    web_form_name = frappe.db.get_value("Web Form", {"route": WEB_FORM_ROUTE}, "name")
    if not web_form_name:
        return

    frappe.db.set_value("Web Form", web_form_name, "success_message", NEW_SUCCESS_MESSAGE)
    frappe.db.commit()
