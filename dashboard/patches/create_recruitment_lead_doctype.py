"""
Creates "Recruitment Lead" - a brand-new doctype for Franchisee Call and
Session Worker recruitment, deliberately separate from "Client Lead"
(ordinary client enquiries/bookings).

Why: Client Lead has accumulated so many recruitment-specific custom
fields across this app's history (Stage 1 pipeline, NDA/Intent to
Proceed/Franchise Agreement e-signing, Franchisee Intake + DBS form,
Safer Recruitment Checklist, Session Worker Fees Guide) that it hit
MySQL's 65,535-byte row-size limit on a live migration (see
fix_client_lead_row_too_large.py / add_franchise_lead_contract_fields.py's
own docstring) - and it will keep growing, since recruitment is still
an actively developed part of this app. Splitting recruitment onto its
own, narrower doctype both fixes the immediate pressure and stops it
recurring.

This is PHASE 1 of a 3-phase, deliberately cautious migration (Ashley's
own instruction - nothing moved away from the current leads yet):
  1. (this patch + the API/UI that follow) Build Recruitment Lead
     fully working, in parallel - Client Lead is completely untouched.
  2. Once confirmed working, migrate the real existing Franchisee Call/
     Session Worker Client Lead records into Recruitment Lead.
  3. Once migration is confirmed, remove the now-redundant
     recruitment fields from Client Lead.
Phases 2 and 3 are each their own separate, later patch - do not
attempt either from this one.

lead_type (Select: Franchisee/Session Worker) replaces Client Lead's
appointment_type-substring-matching (is_franchise_lead()/
is_session_worker_lead() in leads.py) as the authoritative discriminator
- cleaner for a fresh doctype, even though the two lead kinds still
share most of their fields below (NDA, Intake/DBS, Safer Recruitment
Checklist, and the first few Stage 1 milestones), same as they do today.

Field set, fieldtypes and labels are a direct, deliberate port of every
recruitment-relevant Client Lead custom field as it exists today
(confirmed against every patch that touches Client Lead) - see this
app's own patches/add_franchise_lead_*.py, add_franchisee_intake_fields.py,
add_safer_recruitment_checklist.py, add_session_worker_lead_fields.py
for the originals. Reuses the existing "Safer Recruitment Checklist
Item" and "Client Lead Note" child doctypes as-is (both are already
generic, not Client-Lead-specific) rather than duplicating them.

Deliberately NOT carried over: source_lead (legacy webshop Lead sync,
confirmed unrelated to recruitment), active_transfer (the Client
Transfer Agreement workflow is about reassigning an existing client's
coach, not a not-yet-converted recruitment candidate), the generic
client-intake fields (client_type, young_person_*/adult_*/school_*/
company_*, intake_sent_on/intake_email_status/intake_completed_on) -
all belong to the ordinary client-enquiry intake flow, never used by a
Franchisee Call or Session Worker lead.
"""

import frappe

DOCTYPE_NAME = "Recruitment Lead"


def _section(label, fieldname):
    return {"fieldname": fieldname, "fieldtype": "Section Break", "label": label}


def _column(fieldname):
    return {"fieldname": fieldname, "fieldtype": "Column Break"}


def _fields():
    return [
        # -----------------------------------------------------------
        # Lead Info
        # -----------------------------------------------------------
        _section("Lead Info", "section_lead_info"),
        {"fieldname": "lead_type", "fieldtype": "Select", "label": "Lead Type",
         "options": "Franchisee\nSession Worker", "reqd": 1, "in_list_view": 1, "in_standard_filter": 1},
        {"fieldname": "status", "fieldtype": "Select", "label": "Status",
         "options": "New\nConverted\nDeclined", "default": "New", "in_list_view": 1, "in_standard_filter": 1},
        {"fieldname": "source", "fieldtype": "Select", "label": "Source",
         "options": "Coach Added\nCalendar Booking\nPublic Booking\nWebsite Enquiry\nFranchise Brochure"},
        {"fieldname": "appointment_type", "fieldtype": "Data", "label": "Appointment Type",
         "description": "The original booking's appointment type label, kept for display/reporting parity."},
        {"fieldname": "coach", "fieldtype": "Link", "label": "Coach", "options": "Coach",
         "description": "Sponsoring/owning coach - the franchisor for a Franchisee Call, the sponsoring coach for a Session Worker."},
        _column("column_lead_info_1"),
        {"fieldname": "contact_name", "fieldtype": "Data", "label": "Contact Name", "reqd": 1, "in_list_view": 1},
        {"fieldname": "contact_email", "fieldtype": "Data", "label": "Contact Email", "options": "Email"},
        {"fieldname": "contact_mobile", "fieldtype": "Data", "label": "Contact Mobile"},
        {"fieldname": "client_name", "fieldtype": "Data", "label": "Display Name",
         "description": "Shown as this lead's own title - usually the same as Contact Name."},

        _section("Location & Notes", "section_location"),
        {"fieldname": "postal_code", "fieldtype": "Data", "label": "Postal Code"},
        {"fieldname": "location_address", "fieldtype": "Small Text", "label": "Location / Address"},
        {"fieldname": "how_heard", "fieldtype": "Data", "label": "How They Heard About Us"},
        {"fieldname": "consent_given", "fieldtype": "Check", "label": "Consent To Be Contacted"},
        _column("column_location_1"),
        {"fieldname": "event", "fieldtype": "Link", "label": "Booked Call", "options": "Event"},
        {"fieldname": "decline_reason", "fieldtype": "Small Text", "label": "Decline Reason",
         "depends_on": "eval:doc.status=='Declined'"},

        # -----------------------------------------------------------
        # Stage 1 - Decide & Commit
        # -----------------------------------------------------------
        _section("Stage 1 - Decide & Commit", "section_stage1"),
        {"fieldname": "stage1_call_done", "fieldtype": "Check", "label": "Call With Ashley (Founder) / Franchise Call"},
        {"fieldname": "stage1_call_date", "fieldtype": "Date", "label": "Call Date"},
        _column("stage1_col_1"),
        {"fieldname": "stage1_nda_done", "fieldtype": "Check", "label": "Sign NDA"},
        {"fieldname": "stage1_nda_date", "fieldtype": "Date", "label": "NDA Signed Date"},
        _column("stage1_col_2"),
        {"fieldname": "stage1_discovery_day_done", "fieldtype": "Check", "label": "Discovery Day",
         "depends_on": "eval:doc.lead_type=='Franchisee'"},
        {"fieldname": "stage1_discovery_day_date", "fieldtype": "Date", "label": "Discovery Day Date"},
        _column("stage1_col_3"),
        {"fieldname": "stage1_intent_deposit_dbs_done", "fieldtype": "Check", "label": "Intent to Proceed",
         "depends_on": "eval:doc.lead_type=='Franchisee'"},
        {"fieldname": "stage1_intent_deposit_dbs_date", "fieldtype": "Date", "label": "Intent to Proceed Date"},
        _column("stage1_col_4"),
        {"fieldname": "stage1_agreement_invoice_done", "fieldtype": "Check",
         "label": "Franchisee Intake + DBS/Insurance Submitted"},
        {"fieldname": "stage1_agreement_invoice_date", "fieldtype": "Date", "label": "Date"},
        _column("stage1_col_5"),
        {"fieldname": "stage1_recruitment_questions_done", "fieldtype": "Check", "label": "Recruitment Questions Reviewed",
         "depends_on": "eval:doc.lead_type=='Franchisee'"},
        {"fieldname": "stage1_recruitment_questions_date", "fieldtype": "Date", "label": "Date"},
        _column("stage1_col_6"),
        {"fieldname": "stage1_contract_sent_done", "fieldtype": "Check", "label": "Full Contract Signed",
         "depends_on": "eval:doc.lead_type=='Franchisee'"},
        {"fieldname": "stage1_contract_sent_date", "fieldtype": "Date", "label": "Date"},
        _column("stage1_col_7"),
        {"fieldname": "stage1_final_invoice_done", "fieldtype": "Check", "label": "Final Invoice Raised",
         "depends_on": "eval:doc.lead_type=='Franchisee'"},
        {"fieldname": "stage1_final_invoice_date", "fieldtype": "Date", "label": "Date"},

        # -----------------------------------------------------------
        # NDA
        # -----------------------------------------------------------
        _section("Non-Disclosure Agreement", "section_nda"),
        {"fieldname": "nda_token", "fieldtype": "Data", "label": "NDA Sign Link Token", "unique": 1, "no_copy": 1, "read_only": 1},
        {"fieldname": "nda_sent_at", "fieldtype": "Datetime", "label": "NDA Sent At", "read_only": 1},
        {"fieldname": "nda_agreement_date", "fieldtype": "Date", "label": "NDA Agreement Date", "read_only": 1},
        {"fieldname": "nda_term_expiry", "fieldtype": "Date", "label": "NDA Term Expiry", "read_only": 1},
        _column("column_nda_1"),
        {"fieldname": "nda_recipient_name", "fieldtype": "Data", "label": "NDA Recipient Name", "read_only": 1},
        {"fieldname": "nda_recipient_address", "fieldtype": "Small Text", "label": "NDA Recipient Address", "read_only": 1},
        {"fieldname": "nda_signature_name", "fieldtype": "Data", "label": "NDA Signature", "read_only": 1},
        {"fieldname": "nda_signed_snapshot", "fieldtype": "Text Editor", "label": "Signed NDA (Snapshot)", "read_only": 1},
        {"fieldname": "nda_signed_at", "fieldtype": "Datetime", "label": "NDA Signed At", "read_only": 1},
        {"fieldname": "nda_signer_ip", "fieldtype": "Small Text", "label": "NDA Signer IP Address", "read_only": 1},
        {"fieldname": "nda_signer_user_agent", "fieldtype": "Small Text", "label": "NDA Signer Browser/Device", "read_only": 1},

        # -----------------------------------------------------------
        # Intent to Proceed (Franchisee only)
        # -----------------------------------------------------------
        _section("Deposit and Intent to Proceed Agreement", "section_intent"),
        {"fieldname": "intent_token", "fieldtype": "Data", "label": "Intent to Proceed Sign Link Token", "unique": 1, "no_copy": 1, "read_only": 1},
        {"fieldname": "intent_sent_at", "fieldtype": "Datetime", "label": "Intent to Proceed Sent At", "read_only": 1},
        {"fieldname": "intent_agreement_date", "fieldtype": "Date", "label": "Intent to Proceed Agreement Date", "read_only": 1},
        {"fieldname": "intent_territory", "fieldtype": "Data", "label": "Territory", "read_only": 1},
        {"fieldname": "intent_deposit_amount", "fieldtype": "Currency", "label": "Deposit Amount", "read_only": 1},
        {"fieldname": "intent_end_date", "fieldtype": "Date", "label": "Agreement End Date (if no Franchise Agreement by then)", "read_only": 1},
        _column("column_intent_1"),
        {"fieldname": "intent_recipient_name", "fieldtype": "Data", "label": "Intent to Proceed Recipient Name", "read_only": 1},
        {"fieldname": "intent_recipient_address", "fieldtype": "Small Text", "label": "Intent to Proceed Recipient Address", "read_only": 1},
        {"fieldname": "intent_signature_name", "fieldtype": "Data", "label": "Intent to Proceed Signature", "read_only": 1},
        {"fieldname": "intent_signed_snapshot", "fieldtype": "Text Editor", "label": "Signed Intent to Proceed (Snapshot)", "read_only": 1},
        {"fieldname": "intent_signed_at", "fieldtype": "Datetime", "label": "Intent to Proceed Signed At", "read_only": 1},
        {"fieldname": "intent_signer_ip", "fieldtype": "Small Text", "label": "Intent to Proceed Signer IP Address", "read_only": 1},
        {"fieldname": "intent_signer_user_agent", "fieldtype": "Small Text", "label": "Intent to Proceed Signer Browser/Device", "read_only": 1},

        # -----------------------------------------------------------
        # Franchise Agreement (Franchisee only)
        # -----------------------------------------------------------
        _section("Franchise Agreement", "section_contract"),
        {"fieldname": "contract_token", "fieldtype": "Data", "label": "Franchise Agreement Sign Link Token", "unique": 1, "no_copy": 1, "read_only": 1},
        {"fieldname": "contract_sent_at", "fieldtype": "Datetime", "label": "Franchise Agreement Sent At", "read_only": 1},
        {"fieldname": "contract_agreement_date", "fieldtype": "Date", "label": "Franchise Agreement Date", "read_only": 1},
        {"fieldname": "contract_commencement_date", "fieldtype": "Date", "label": "Commencement Date", "read_only": 1},
        {"fieldname": "contract_expiry_date", "fieldtype": "Date", "label": "Expiry Date",
         "description": "Always exactly 3 years after the Commencement Date - computed, never typed in.", "read_only": 1},
        {"fieldname": "contract_territory_description", "fieldtype": "Small Text", "label": "Territory", "read_only": 1},
        {"fieldname": "contract_permitted_area", "fieldtype": "Small Text", "label": "Permitted Area", "read_only": 1},
        _column("column_contract_1"),
        {"fieldname": "contract_recipient_name", "fieldtype": "Small Text", "label": "Franchise Agreement Recipient Name", "read_only": 1},
        {"fieldname": "contract_recipient_address", "fieldtype": "Small Text", "label": "Franchise Agreement Recipient Address", "read_only": 1},
        {"fieldname": "contract_signature_name", "fieldtype": "Small Text", "label": "Franchise Agreement Signature", "read_only": 1},
        {"fieldname": "contract_signed_snapshot", "fieldtype": "Text Editor", "label": "Signed Franchise Agreement (Snapshot)", "read_only": 1},
        {"fieldname": "contract_signed_at", "fieldtype": "Datetime", "label": "Franchise Agreement Signed At", "read_only": 1},
        {"fieldname": "contract_signer_ip", "fieldtype": "Small Text", "label": "Franchise Agreement Signer IP Address", "read_only": 1},
        {"fieldname": "contract_signer_user_agent", "fieldtype": "Small Text", "label": "Franchise Agreement Signer Browser/Device", "read_only": 1},
        {"fieldname": "contract_franchisor_signature_name", "fieldtype": "Small Text", "label": "Franchisor Signature", "read_only": 1},
        {"fieldname": "contract_franchisor_signed_at", "fieldtype": "Datetime", "label": "Franchisor Signed At", "read_only": 1},
        {"fieldname": "contract_franchisor_signer_ip", "fieldtype": "Small Text", "label": "Franchisor Signer IP", "read_only": 1},
        {"fieldname": "contract_franchisor_signer_user_agent", "fieldtype": "Small Text", "label": "Franchisor Signer Browser/Device", "read_only": 1},
        {"fieldname": "contract_territory_map", "fieldtype": "Attach Image", "label": "Territory Map Image",
         "description": "Shown in Schedule 2 - upload the area map for this franchisee's postcode territory before generating the sign link."},

        # -----------------------------------------------------------
        # Intake + DBS/Insurance
        # -----------------------------------------------------------
        _section("Intake + DBS/Insurance Form", "section_intake"),
        {"fieldname": "franchisee_intake_token", "fieldtype": "Data", "label": "Intake Form Token", "unique": 1, "no_copy": 1, "read_only": 1},
        {"fieldname": "franchisee_intake_sent_at", "fieldtype": "Datetime", "label": "Intake Form Sent At", "read_only": 1},
        {"fieldname": "franchisee_intake_submitted", "fieldtype": "Check", "label": "Intake Form Submitted", "read_only": 1},
        {"fieldname": "franchisee_intake_submitted_at", "fieldtype": "Datetime", "label": "Intake Form Submitted At", "read_only": 1},
        {"fieldname": "franchisee_intake_first_name", "fieldtype": "Data", "label": "First Name", "read_only": 1},
        {"fieldname": "franchisee_intake_last_name", "fieldtype": "Data", "label": "Last Name", "read_only": 1},
        {"fieldname": "franchisee_intake_phone", "fieldtype": "Data", "label": "Phone", "read_only": 1},
        {"fieldname": "franchisee_intake_gender", "fieldtype": "Select", "label": "Gender",
         "options": "\nFemale\nMale\nNon-binary\nPrefer not to say\nOther", "read_only": 1},
        {"fieldname": "franchisee_intake_dob", "fieldtype": "Date", "label": "Date of Birth", "read_only": 1},
        _column("column_intake_1"),
        {"fieldname": "franchisee_intake_dbs_number", "fieldtype": "Data", "label": "DBS Number", "read_only": 1},
        {"fieldname": "franchisee_intake_dbs_date_received", "fieldtype": "Date", "label": "DBS Date Received", "read_only": 1},
        {"fieldname": "franchisee_intake_dbs_expiry_date", "fieldtype": "Date", "label": "DBS Expiry Date", "read_only": 1},
        {"fieldname": "franchisee_intake_dbs_certificate", "fieldtype": "Attach", "label": "DBS Certificate", "read_only": 1},
        {"fieldname": "franchisee_intake_additional_document", "fieldtype": "Attach", "label": "Additional Document (e.g. Proof of Insurance)", "read_only": 1},
        {"fieldname": "franchisee_intake_public_liability_insurer", "fieldtype": "Small Text", "label": "Public Liability Insurer", "read_only": 1},
        {"fieldname": "franchisee_intake_indemnity_insurer", "fieldtype": "Small Text", "label": "Professional Indemnity Insurer", "read_only": 1},
        {"fieldname": "franchisee_intake_insurance_renewal_date", "fieldtype": "Date", "label": "Insurance Renewal Date", "read_only": 1},

        _section("Self-Reported Background (Safer Recruitment)", "section_self_report"),
        {"fieldname": "franchisee_intake_qualifications", "fieldtype": "Small Text", "label": "Qualifications", "read_only": 1},
        {"fieldname": "franchisee_intake_work_locations", "fieldtype": "Small Text", "label": "Work Locations", "read_only": 1},
        {"fieldname": "franchisee_intake_id_document_type", "fieldtype": "Small Text", "label": "ID Document Type", "read_only": 1},
        {"fieldname": "franchisee_intake_right_to_work_status", "fieldtype": "Select", "label": "Right to Work Status",
         "options": "\nBritish/Irish Citizen\nSettled/Pre-Settled Status\nVisa - Right to Work\nTo Be Confirmed", "read_only": 1},
        {"fieldname": "franchisee_intake_right_to_work_expiry", "fieldtype": "Date", "label": "Right to Work Expiry", "read_only": 1},
        _column("column_self_report_1"),
        {"fieldname": "franchisee_intake_address_history", "fieldtype": "Small Text", "label": "Address History (Last 5 Years)", "read_only": 1},
        {"fieldname": "franchisee_intake_overseas_checks", "fieldtype": "Small Text", "label": "Overseas Checks", "read_only": 1},
        {"fieldname": "franchisee_intake_work_history", "fieldtype": "Small Text", "label": "Work History", "read_only": 1},
        {"fieldname": "franchisee_intake_reference1_details", "fieldtype": "Small Text", "label": "Reference 1 Details", "read_only": 1},
        {"fieldname": "franchisee_intake_reference2_details", "fieldtype": "Small Text", "label": "Reference 2 Details", "read_only": 1},

        # -----------------------------------------------------------
        # Safer Recruitment Checklist
        # -----------------------------------------------------------
        _section("Safer Recruitment Checklist", "section_safer_recruitment"),
        {"fieldname": "safer_recruitment_checklist", "fieldtype": "Table", "label": "Safer Recruitment Checklist",
         "options": "Safer Recruitment Checklist Item"},
        {"fieldname": "safer_recruitment_outstanding_actions", "fieldtype": "Small Text", "label": "Outstanding Actions & Conditions"},

        # -----------------------------------------------------------
        # Session Worker - Fees and Expectations Guide + setup
        # -----------------------------------------------------------
        _section("Fees and Expectations Guide", "section_fees_guide"),
        {"fieldname": "fees_guide_token", "fieldtype": "Data", "label": "Fees Guide Sign Link Token", "unique": 1, "no_copy": 1, "read_only": 1,
         "depends_on": "eval:doc.lead_type=='Session Worker'"},
        {"fieldname": "fees_guide_sent_at", "fieldtype": "Datetime", "label": "Fees Guide Sent At", "read_only": 1},
        {"fieldname": "fees_guide_agreement_date", "fieldtype": "Date", "label": "Effective From", "read_only": 1},
        {"fieldname": "fees_guide_rate_1to1", "fieldtype": "Currency", "label": "1:1 Rate", "read_only": 1},
        {"fieldname": "fees_guide_rate_group", "fieldtype": "Currency", "label": "Group Rate", "read_only": 1},
        {"fieldname": "fees_guide_rate_workshop", "fieldtype": "Currency", "label": "Workshop Rate", "read_only": 1},
        {"fieldname": "fees_guide_invoicing_frequency", "fieldtype": "Select", "label": "Invoicing Frequency",
         "options": "\nWeekly\nFortnightly\nMonthly", "read_only": 1},
        _column("column_fees_guide_1"),
        {"fieldname": "fees_guide_recipient_name", "fieldtype": "Small Text", "label": "Fees Guide Recipient Name", "read_only": 1},
        {"fieldname": "fees_guide_signature_name", "fieldtype": "Small Text", "label": "Fees Guide Signature", "read_only": 1},
        {"fieldname": "fees_guide_signed_snapshot", "fieldtype": "Text Editor", "label": "Signed Fees Guide (Snapshot)", "read_only": 1, "no_copy": 1},
        {"fieldname": "fees_guide_signed_at", "fieldtype": "Datetime", "label": "Fees Guide Signed At", "read_only": 1, "no_copy": 1},
        {"fieldname": "fees_guide_signer_ip", "fieldtype": "Small Text", "label": "Fees Guide Signer IP Address", "read_only": 1, "no_copy": 1},
        {"fieldname": "fees_guide_signer_user_agent", "fieldtype": "Small Text", "label": "Fees Guide Signer Browser/Device", "read_only": 1, "no_copy": 1},
        {"fieldname": "fees_guide_done", "fieldtype": "Check", "label": "Fees and Expectations Guide Signed"},
        {"fieldname": "fees_guide_date", "fieldtype": "Date", "label": "Date"},

        _section("Set Up As Session Worker", "section_sw_setup"),
        {"fieldname": "sw_setup_done", "fieldtype": "Check", "label": "Set Up As Session Worker"},
        {"fieldname": "sw_setup_date", "fieldtype": "Date", "label": "Date"},

        # -----------------------------------------------------------
        # Conversion tracking
        # -----------------------------------------------------------
        _section("Conversion", "section_conversion"),
        {"fieldname": "converted_client", "fieldtype": "Link", "label": "Converted Client", "options": "Client", "read_only": 1, "no_copy": 1},
        {"fieldname": "converted_contact", "fieldtype": "Link", "label": "Converted Contact", "options": "Contact", "read_only": 1, "no_copy": 1},
        {"fieldname": "converted_session_worker", "fieldtype": "Link", "label": "Converted Session Worker", "options": "Session Worker", "read_only": 1, "no_copy": 1},

        # -----------------------------------------------------------
        # Notes
        # -----------------------------------------------------------
        _section("Notes", "section_notes"),
        {"fieldname": "notes", "fieldtype": "Table", "label": "Notes", "options": "Client Lead Note"},
    ]


def execute():
    if frappe.db.exists("DocType", DOCTYPE_NAME):
        return

    doc = frappe.get_doc({
        "doctype": "DocType",
        "name": DOCTYPE_NAME,
        "module": "Dashboard",
        "custom": 1,
        "naming_rule": "Random",
        "autoname": "hash",
        "fields": _fields(),
        "permissions": [
            {
                "role": "System Manager",
                "read": 1, "write": 1, "create": 1, "delete": 1,
                "report": 1, "export": 1, "print": 1, "email": 1, "share": 1,
            },
        ],
        "sort_field": "creation",
        "sort_order": "DESC",
        "track_changes": 1,
    })
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
