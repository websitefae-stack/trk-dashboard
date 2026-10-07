"""
Follow-up to add_franchise_lead_contract_fields, fixing three gaps Ashley
flagged once she could actually review the live Franchise Agreement flow:

1. The document hardcoded Ashley's own signature ("AJC") directly in the
   template text - the agreement was effectively "pre-signed" by the
   franchisor with no real sign action, audit trail, or requirement that
   she actually do it before a franchisee ever saw it. These new
   contract_franchisor_* fields capture a real signing step (typed name +
   IP + user agent + timestamp, same as the franchisee's own) - see
   sign_contract_as_franchisor() in leads.py, which get_contract_sign_url
   now requires before a sign link can even be generated.

2. Schedule 2's Territory map and Schedule 3's Trade Mark certificate
   were both left as "attach this manually in Desk" placeholder notes -
   not a real feature. These two Attach Image fields let the franchisor
   upload the actual per-deal map / certificate image, rendered directly
   into the document.

Only Small Text/Attach Image/Datetime fields here (no Data/varchar) -
Client Lead already hit MySQL's row-size limit once (see
fix_client_lead_row_too_large.py / add_franchise_lead_contract_fields.py)
and these field types don't count against that same byte budget.
"""

import frappe


DOCTYPE = "Client Lead"

FIELDS = [
    {"fieldname": "contract_franchisor_signature_name", "fieldtype": "Small Text",
     "label": "Franchisor Signature", "read_only": 1,
     "description": "Set automatically once Ashley signs via Generate Sign Link - not editable here."},
    {"fieldname": "contract_franchisor_signed_at", "fieldtype": "Datetime",
     "label": "Franchisor Signed At", "read_only": 1},
    {"fieldname": "contract_franchisor_signer_ip", "fieldtype": "Small Text",
     "label": "Franchisor Signer IP", "read_only": 1},
    {"fieldname": "contract_franchisor_signer_user_agent", "fieldtype": "Small Text",
     "label": "Franchisor Signer Browser/Device", "read_only": 1},
    {"fieldname": "contract_territory_map", "fieldtype": "Attach Image",
     "label": "Territory Map Image",
     "description": "Shown in Schedule 2 of the Franchise Agreement - upload the area map for this franchisee's postcode territory before generating the sign link."},
    {"fieldname": "contract_trademark_certificate", "fieldtype": "Attach Image",
     "label": "Trade Mark Certificate Image",
     "description": "Shown in Schedule 3 of the Franchise Agreement - upload a scan/screenshot of the UK00004020678 registration certificate."},
]


def execute():
    if not frappe.db.exists("DocType", DOCTYPE):
        return

    existing = {
        cf.fieldname
        for cf in frappe.get_all("Custom Field", filters={"dt": DOCTYPE}, fields=["fieldname"])
    }

    insert_after = "contract_signer_user_agent"
    for field in FIELDS:
        if field["fieldname"] in existing:
            continue

        frappe.get_doc({
            "doctype": "Custom Field",
            "dt": DOCTYPE,
            "insert_after": insert_after,
            **field,
        }).insert(ignore_permissions=True)
        insert_after = field["fieldname"]

    frappe.db.commit()
    frappe.clear_cache(doctype=DOCTYPE)
