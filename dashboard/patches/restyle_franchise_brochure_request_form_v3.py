"""
Follow-up to restyle_franchise_brochure_request_form_v2.py - confirmed
live: that patch's catch-all (`.web-form-container *` with background
and box-shadow wiped) killed the white strip, but it ALSO wiped the
actual input boxes themselves - Full Name/Email Address had no visible
fill or border left at all, making them invisible and the form
unusable (confirmed live: a visitor had no idea where to click).

Same catch-all approach, but this time explicitly restores a visible
white, bordered box on the real input/textarea elements afterward -
belt-and-braces already proved the only safe way to find Frappe's own
internal class names without guessing, so inputs get the same
treatment as the submit button already did: stripped by the catch-all,
then explicitly put back since this one has to actually look like a
field.
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
   white strip behind a field. */
.web-form-container,
.web-form-container * {{
    background-color: transparent !important;
    box-shadow: none !important;
}}

.web-form-container .frappe-control {{
    margin-bottom: 18px !important;
}}

/* Restored AFTER the catch-all above, same as the submit button below -
   an actual text field has to look like one (visible fill + border),
   or there's nothing on screen to show a visitor where to click. */
.web-form-container input[type="text"],
.web-form-container input[type="email"],
.web-form-container input[type="password"],
.web-form-container input[type="number"],
.web-form-container input[type="date"],
.web-form-container input[type="tel"],
.web-form-container textarea,
.web-form-container select {{
    background: #FFFFFF !important;
    border: 1px solid #D9E6E6 !important;
    border-radius: 6px !important;
    padding: 8px 12px !important;
}}

.web-form-container input[type="text"]:focus,
.web-form-container input[type="email"]:focus,
.web-form-container textarea:focus {{
    border-color: #582581 !important;
    outline: none !important;
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
