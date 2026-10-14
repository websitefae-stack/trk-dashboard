"""
Adds a hidden field to the "Intake Doctype" Web Form submission record so
an intake link can be tied to the specific Client Lead it was sent to,
instead of relying entirely on matching the submission back to a Lead by
email/name after the fact (see leads.py's own
_find_client_lead_for_intake_submission).

That email/name matching deliberately refuses to guess when it finds
more than one candidate (logged as "Intake Submission - Client Lead
Match Failed") - exactly what happened for a family where two different
household members' emails/names each matched a different pre-existing
Client Lead. source_client_lead lets a link generated from a specific
Lead (_intake_url in leads.py) skip that guessing entirely: the Web
Form's own query-param pre-fill (?source_client_lead=<Lead name>, same
mechanism any Frappe Web Form field uses) populates it automatically,
and _find_client_lead_for_intake_submission checks it first.

"Intake Doctype" and its own client-intake Web Form are both built live
in Desk (no JSON for either in this repo - see leads.py's own comments
near INTAKE_DOCTYPE), so create_custom_fields is the only way to add a
field here; the new field still needs to be added to the client-intake
Web Form's own field list in Desk (Hidden, so no guest ever sees or
edits it) before submissions will actually start carrying it - see this
project's own follow-up instructions for that one-off manual step.

Deliberately a Data field holding the Lead's own name/ID, not a Link to
Client Lead - same reasoning as Client Lead's own franchisee_intake_
token field (add_franchisee_intake_fields.py): a plain Data field never
raises a surprise permission question for a route a Guest submits
through, while a Link field's value is still validated as a real row
via frappe.db.exists() in the matching code itself.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

INTAKE_DOCTYPE = "Intake Doctype"


def execute():
    if not frappe.db.exists("DocType", INTAKE_DOCTYPE):
        return

    create_custom_fields({
        INTAKE_DOCTYPE: [
            {
                "fieldname": "source_client_lead",
                "fieldtype": "Data",
                "label": "Source Client Lead",
                "read_only": 1,
                "no_copy": 1,
                "description": "Populated from the ?source_client_lead= query param on the intake link actually sent to this family - see leads.py's own _intake_url()/_find_client_lead_for_intake_submission().",
            },
        ],
    }, ignore_validate=True)
    frappe.db.commit()
