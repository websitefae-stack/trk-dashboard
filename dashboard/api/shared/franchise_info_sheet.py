"""
Turns a submitted "Information Sheet - TRK Franchise" (Franchise
Information Sheet Response - see
patches/create_franchise_information_sheet_form.py) into a Client Lead,
so a franchise prospect who's filled this in shows up in Ashley's own
Leads pipeline - and gets the same Franchisee Call / Stage 1 treatment
(see leads.is_franchise_lead) - straight away, rather than only once
she's actually booked a call with them.

Matched to an existing lead by contact email first, rather than
blindly creating a duplicate, in case this person already reached
Ashley through some other route (e.g. already booked a call directly
from a coach's public profile - see public_booking.submit_public_booking,
which creates a Client Lead the same way).
"""

import frappe

from dashboard.api.shared.permissions import FRANCHISOR_USERS

LEAD_DOCTYPE = "Client Lead"


def _franchisor_coach_name():
    for email in FRANCHISOR_USERS:
        coach_name = (
            frappe.db.get_value("Coach", {"user": email}, "name")
            or frappe.db.get_value("Coach", {"coach_email": email}, "name")
        )
        if coach_name:
            return coach_name

    return None


def sync_franchise_info_sheet_to_lead(doc, method=None):
    if not doc.get("email") or doc.get("linked_lead"):
        return

    if not frappe.db.exists(LEAD_DOCTYPE, {"contact_email": doc.email}):
        lead = frappe.new_doc(LEAD_DOCTYPE)
        lead.status = "New"
        lead.source = "Franchise Information Sheet"
        lead.appointment_type = "Franchisee Call"
        lead.coach = _franchisor_coach_name()
        lead.contact_name = doc.full_name
        lead.contact_email = doc.email
        lead.contact_mobile = doc.phone_number or ""
        lead.client_name = doc.full_name
        lead.consent_given = 1
        lead.insert(ignore_permissions=True)
        frappe.db.commit()

    lead_name = frappe.db.get_value(LEAD_DOCTYPE, {"contact_email": doc.email}, "name")
    if lead_name:
        doc.db_set("linked_lead", lead_name, update_modified=False)
