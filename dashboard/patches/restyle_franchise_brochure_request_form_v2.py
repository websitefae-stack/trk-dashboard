"""
Follow-up to restyle_franchise_brochure_request_form.py - confirmed
live after that patch deployed: the white strip behind Full Name/Email
Address was STILL there. That patch guessed at Frappe's own internal
field-wrapper class names (.form-section, .section-body, .frappe-card,
.form-column) and missed - none of them were actually it.

Rather than guess a fourth class name blind, this takes the maximally
safe catch-all approach: strip the background off EVERY element inside
the form wrapper, then explicitly restore just the submit button's own
purple background afterward (it comes later in the stylesheet, so it
wins the cascade). Guaranteed to remove the white strip regardless of
whatever class Frappe is actually using for it.
"""

import frappe

WEB_FORM_ROUTE = "franchise-brochure-request"
TRANSPARENT_LOGO = "/files/TRH-Transparent.png"

CUSTOM_CSS = f"""
/* Hub logo at top */

.web-form-container::before {{
    content: "";
    display: block;
    height: 140px;
    margin-top: 28px;
    background-image: url("{TRANSPARENT_LOGO}");
    background-repeat: no-repeat;
    background-position: center;
    background-size: contain;
}}

/* Brand logos underneath */

.web-form-container::after {{
    content: "";
    display: block;
    height: 60px;
    margin-top: -10px;
    margin-bottom: 30px;
    background-image:
        url("/files/TRKid_Wordmark_Logo.png"),
        url("/files/TRTeen_Wordmark_Logo.png"),
        url("/files/TRPeople_Wordmark_Logo.png"),
        url("/files/TRSchool_Wordmark_Logo.png");
    background-repeat: no-repeat, no-repeat, no-repeat, no-repeat;
    background-size: 120px auto, 120px auto, 120px auto, 120px auto;
    background-position:
        calc(50% - 210px) center,
        calc(50% - 70px) center,
        calc(50% + 70px) center,
        calc(50% + 210px) center;
}}

/* Form styling */

.web-form-container {{
    max-width: 1000px;
    margin: 0 auto;
    padding: 0 24px 24px !important;
}}

/* Catch-all: whatever Frappe's own inner wrapper class actually is,
   this removes its background regardless, so it can never show as a
   white strip behind a field again. */
.web-form-container,
.web-form-container * {{
    background-color: transparent !important;
    box-shadow: none !important;
}}

.web-form-container .frappe-control {{
    margin-bottom: 18px !important;
}}

.section-head {{
    color: #582581 !important;
    font-weight: 700 !important;
}}

/* Restored AFTER the catch-all above so it wins - the one background
   inside the form that should stay. */
.btn-primary {{
    background: #582581 !important;
    border-color: #582581 !important;
    border-radius: 8px !important;
    padding: 14px 32px !important;
    font-weight: 600 !important;
}}

.btn-primary:hover {{
    background: #9A4795 !important;
    border-color: #9A4795 !important;
}}

/* Let the form title wrap onto multiple lines instead of being cut off
   with an ellipsis - the full form name should always be readable. */
.web-form-container .ellipsis,
.web-form-container h1,
.web-form-container .title {{
    white-space: normal !important;
    overflow: visible !important;
    text-overflow: clip !important;
    word-break: break-word !important;
}}
"""


def execute():
    web_form_name = frappe.db.get_value("Web Form", {"route": WEB_FORM_ROUTE}, "name")
    if not web_form_name:
        return

    frappe.db.set_value("Web Form", web_form_name, "custom_css", CUSTOM_CSS)
    frappe.db.commit()
