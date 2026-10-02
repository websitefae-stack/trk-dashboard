"""
Restyles the "Franchise Brochure Request" web form (create_franchise_
brochure_request_form.py only runs once, so an already-live site needs
a separate patch to update its custom_css):

- Padding above the logo banner (previously sat flush against the top
  of the popup/page) - and now generous padding around the Full Name/
  Email Address fields too, which sat flush against the card edges.
- Swaps the Hub logo to Ashley's actual transparent PNG
  (/files/TRH-Transparent.png) - TRHub_Logo.jpg is a JPG, which can
  never have a transparent background (it was showing as an opaque
  white rectangle sitting on top of the page's own mint background).
- Strips Frappe's own default white card background/border/shadow off
  the form wrapper AND its known inner field-section wrapper classes,
  so the whole popup reads as one consistent background instead of a
  white block sitting apart from it.
- Submit button changed from pink (#e84862) to brand purple
  (#582581, matching trh-franchise-brochure.css's --trh-purple-
  primary) - hover was already purple (#9A4795), so the base colour
  was the only one left inconsistent with the rest of the brand.
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
    background: transparent !important;
    box-shadow: none !important;
    border: none !important;
}}

/* Frappe's own web form wraps each section/field group in its own
   white "card" background by default - stripping the container above
   alone doesn't reach these nested wrappers, which is what was still
   showing as a white strip behind Full Name/Email Address. */
.web-form-container .form-section,
.web-form-container .section-body,
.web-form-container .frappe-card,
.web-form-container .form-column {{
    background: transparent !important;
    box-shadow: none !important;
    border: none !important;
    padding-left: 0 !important;
    padding-right: 0 !important;
}}

.web-form-container .frappe-control {{
    margin-bottom: 18px !important;
}}

.section-head {{
    color: #582581 !important;
    font-weight: 700 !important;
}}

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
