"""
Creates the "Franchisee Non-Disclosure Agreement" Practice Document -
lives in the Practice Documents library (document_type "Agreement") so
Ashley can find and edit the wording directly in Desk like any other
document, no file upload involved. document_text is the reusable
template: {{ }} placeholders are filled in per-lead at signing time by
leads.render_nda_text() (see nda_sign.py), never edited here - editing
this record only changes what NEW signing links show, past signatures
keep their own frozen snapshot (Client Lead's nda_signed_snapshot).

Idempotent/safe to leave in place if re-run - does nothing if a
Practice Document with this exact title already exists (e.g. Ashley
already created her own copy in Desk before this patch ran).
"""

import frappe

PRACTICE_DOCUMENT_DOCTYPE = "Practice Document"
NDA_TITLE = "Franchisee Non-Disclosure Agreement"

NDA_TEMPLATE_TEXT = """
<h3>Non-Disclosure Agreement</h3>
<p>This Non-Disclosure Agreement (&ldquo;Agreement&rdquo;) is made and entered into on
<strong>{{ agreement_date }}</strong> by and between.</p>
<p>The Resilient People Limited having its principal place of business at Fox Corner, Chester Road,
Hartford, Cheshire, CW8 1LL (&ldquo;Disclosing Party&rdquo;), and <strong>{{ recipient_name }}</strong>
(&ldquo;Recipient&rdquo;), residing at <strong>{{ recipient_address }}</strong>. The Disclosing Party and
the Recipient may be referred to herein collectively as the &ldquo;Parties&rdquo; or individually as a
&ldquo;Party&rdquo;.</p>
<ol>
<li>The Parties desire to engage in discussions and share confidential information for the purpose of
reviewing, delivering, and supporting The Resilient Kid and The Resilient Teen and The Resilient School
programmes, including but not limited to the Resilient Kid framework, trained content, materials,
methodologies, and intellectual property (the &ldquo;Purpose&rdquo;).</li>
<li>The Recipient agrees that such information is provided solely for use within authorised sessions,
training, or agreed programme delivery and must not be used, reproduced, adapted, or applied outside of
these agreed contexts without the prior written consent of the Disclosing Party.</li>
<li><strong>Definition of Confidential Information</strong><br>
For the purpose of this Agreement, &ldquo;Confidential Information&rdquo; means any and all information
disclosed by the Disclosing Party to the Recipient, whether orally, in writing, or in any other form, that
is designated as confidential or that reasonably should be understood to be confidential given the nature
of the information and the circumstances of disclosure. Confidential Information may include, but is not
limited to, business plans, financial information, trade secrets, technical data, customer lists, and any
other information that is not generally known to the public.</li>
<li><strong>Non-Disclosure and Non-Use</strong><br>
Recipient agrees that it will not disclose any Confidential Information to any third party without the
prior written consent of the Disclosing Party. Recipient further agrees that it will not use any
Confidential Information for any purpose other than the Purpose.</li>
<li><strong>Standard of Care</strong><br>
Recipient agrees to exercise the same degree of care to protect the confidentiality of the Confidential
Information as it uses to protect its own confidential information of a similar nature, but in no event
less than a reasonable degree of care.</li>
<li><strong>Exceptions</strong><br>
Recipient's obligations under this Agreement shall not apply to any information that:
<ol type="a">
<li>Was already known to Recipient prior to its disclosure by the Disclosing Party;</li>
<li>Is or becomes publicly available through no fault of the Recipient;</li>
<li>Is rightfully received by Recipient from a third party without a duty of confidentiality;</li>
<li>Is independently developed by Recipient without reference to the Confidential Information; or</li>
<li>Is required to be disclosed by law, regulation, or court order, provided that Recipient provides
prompt notice to the Disclosing Party to allow the Disclosing Party to seek a protective order or other
appropriate remedy.</li>
</ol></li>
<li><strong>Return of Confidential Information</strong><br>
Upon the written request of the Disclosing Party, Recipient shall promptly return or destroy all
Confidential Information and any copies, extracts, or summaries thereof, in any form or medium, and
certify in writing to the Disclosing Party that it has done so, except that Recipient may retain one copy
of such information solely for the purpose of ensuring compliance with this Agreement.</li>
<li><strong>Term</strong><br>
This Agreement shall be effective as of the date first written above and shall continue in effect until
<strong>{{ term_date }}</strong> (3 years from the date signed). Notwithstanding the foregoing, the
obligations of confidentiality set forth herein shall survive any termination of this Agreement for a
period of ten (10) years thereafter.</li>
<li><strong>Governing Law</strong><br>
This Agreement shall be governed by and construed in accordance with the laws of England and Wales,
without regard to its conflict of laws principles.</li>
<li><strong>Entire Agreement</strong><br>
This Agreement constitutes the entire agreement between the Parties concerning the subject matter hereof
and supersedes all prior and contemporaneous agreements and understandings, whether written or oral,
relating to such subject matter.</li>
</ol>
<p>IN WITNESS WHEREOF, the Parties have executed this Agreement as of the date first above written.</p>
<table style="width:100%;">
<tr>
<td style="width:50%;vertical-align:top;padding-right:20px;">
<p><strong>{{ recipient_name }}</strong><br>Franchisee full name (print)</p>
<p style="font-style:italic;font-size:22px;">{{ franchisee_signature }}</p>
<p>Franchisee signature</p>
<p>{{ franchisee_date }}<br>Date</p>
</td>
<td style="width:50%;vertical-align:top;">
<p><strong>Ashley Costello</strong><br>Franchisor name (print)</p>
<p style="font-style:italic;font-size:22px;">AJC</p>
<p>Franchisor signature</p>
<p>{{ agreement_date }}<br>Date</p>
</td>
</tr>
</table>
"""


def execute():
    if not frappe.db.exists("DocType", PRACTICE_DOCUMENT_DOCTYPE):
        return

    if frappe.db.exists(PRACTICE_DOCUMENT_DOCTYPE, {"document_title": NDA_TITLE}):
        return

    try:
        doc = frappe.get_doc({
            "doctype": PRACTICE_DOCUMENT_DOCTYPE,
            "document_title": NDA_TITLE,
            "document_type": "Agreement",
            "document_purpose": "Internal Compliance",
            "required_action": "Sign",
            "status": "Published",
            "mandatory": 0,
            "document_text": NDA_TEMPLATE_TEXT,
            "signature_statement": (
                "By typing your name below, you confirm you have read and agree to the terms of this "
                "Non-Disclosure Agreement."
            ),
        })
        doc.insert(ignore_permissions=True)
        frappe.db.commit()
    except Exception:
        frappe.log_error(frappe.get_traceback(), "add_franchisee_nda_practice_document failed")
