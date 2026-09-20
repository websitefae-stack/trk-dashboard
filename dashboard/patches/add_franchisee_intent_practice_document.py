"""
Creates the "Deposit and Intent to Proceed Agreement" Practice Document -
same pattern as add_franchisee_nda_practice_document.py: lives in the
Practice Documents library so Ashley can edit the wording directly in
Desk, {{ }} placeholders filled in per-lead at generate/sign time (see
leads.get_intent_sign_url/sign_intent), editing this record only changes
what NEW sign links show.

{{ territory }}, {{ deposit_amount }} and {{ end_date }} are set by
Ashley when she generates the link for a lead (the business terms of
that specific deal); {{ recipient_name }}/{{ recipient_address }}/
{{ franchisee_signature }}/{{ franchisee_date }} are filled in by the
franchisee when they sign, same as the NDA.

Idempotent/safe to leave in place if re-run.
"""

import frappe

PRACTICE_DOCUMENT_DOCTYPE = "Practice Document"
INTENT_TITLE = "Deposit and Intent to Proceed Agreement"

INTENT_TEMPLATE_TEXT = """
<h3>Deposit and Intent to Proceed Agreement</h3>
<p>This agreement is dated <strong>{{ agreement_date }}</strong>.</p>

<h4>Parties</h4>
<ol type="1">
<li>The Resilient People, incorporated and registered in England and Wales with company
number 10625898 whose registered office is at Fox Corner, Chester Road, Hartford, Cheshire
CW8 1LL (Franchisor).</li>
<li><strong>{{ recipient_name }}</strong> of <strong>{{ recipient_address }}</strong> (Potential
Franchisee).</li>
</ol>

<h4>Recitals</h4>
<ol type="A">
<li>The parties are considering entering into a Franchise Agreement (as defined in this
Agreement).</li>
<li>The discussions of entering into a Franchise Agreement will involve the disclosure of
Information (as defined in this Agreement) from the Franchisor to the Potential
Franchisee.</li>
<li>Until such time as the parties enter into a Franchise Agreement, they wish to regulate
the terms on which they will collaborate, in accordance with this Agreement.</li>
</ol>

<h4>It Is Agreed As Follows:</h4>

<p><strong>1. Definitions</strong><br>
In this Agreement unless the context otherwise requires:</p>
<p><strong>Business</strong> refers to the operations carried out by the Franchisor and its
franchisees in line with the established System. This specifically involves providing a
children's wellbeing programme that focuses on resilience-building through engaging
activities, supporting parents and children with children's mental health.</p>
<p><strong>Franchise Agreement</strong> means the Franchisor's standard franchise agreement
offered to prospective franchisees in its then current form.</p>
<p><strong>Information</strong> means: (a) any information relating to the Business or the
System including without prejudice to the generality of the foregoing information concerning
the Franchisor's products, services, customers, accounts, finance or contractual
arrangements or other dealings, transactions or affairs of the Franchisor; (b) any
information relating to the Franchisor's relationship with its prospective franchisees; and
(c) any information provided for the purposes of the Project including any and all works of
authorship and material written or prepared by the Prospective Franchisee, his agents,
employees, officers or sub-contractors in relation to the Project whether individually,
collectively and jointly with the Franchisor or a third party or provided by the Franchisor and
on whatever media.</p>
<p><strong>Project</strong> means the evaluation, by the Prospective Franchisee, of the Business
offered by the Franchisor and the obtaining of finance for the Business.</p>
<p><strong>System</strong>: the distinctive business format and method developed and
implemented by the Franchisor in connection with the operation of the Business using the
Franchisor's intellectual property rights, Information, operational procedures, methods,
management, marketing and advertising techniques.</p>
<p><strong>Territory</strong> means <strong>{{ territory }}</strong>.</p>
<p>Unless the context otherwise requires the terms used in this Agreement shall have the same
meaning as in the Franchise Agreement. A reference to one gender shall include a reference to
the other genders.</p>

<p><strong>2. Deposit Payment</strong><br>
The Prospective Franchisee shall forthwith pay <strong>{{ deposit_amount }}</strong> (Deposit)
to the Franchisor by way of part payment of the Initial Fee payable pursuant to the Franchise
Agreement.</p>

<p><strong>3. Obligations</strong></p>
<p>3.1 Subject to being satisfied that the Franchisee meets the Franchisor's usual recruitment
criteria for franchisees, the Franchisor shall (subject to the terms of this Agreement) enter
into the Franchise Agreement on receiving the Prospective Franchisee's confirmation that he is
willing to execute the Franchise Agreement.</p>
<p>3.2 For a period of 2 weeks from the date of this Agreement, the Franchisor shall not enter
into a franchise agreement with any third party in respect of the Territory.</p>

<p><strong>4. Confidentiality</strong></p>
<p>4.1 The parties hereto recognise that the Information will contain and incorporate
confidential information in which the Franchisor has a proprietary interest and that the
disclosure of it would cause harm to the Franchisor.</p>
<p>4.2 The Prospective Franchisee hereby agrees to maintain as confidential and undertakes not
to use on his own behalf or disclose to any third party any part or the whole of the
Information directly or indirectly disclosed by the Franchisor and agrees not to permit the
use or disclosure of the whole or any part of the Information directly or indirectly disclosed
by the Franchisor for any purpose at any time in any way until or unless such Information
becomes public knowledge through no fault of the Prospective Franchisee, his agents,
sub-contractors or employees or officers.</p>
<p>4.3 The Prospective Franchisee hereby undertakes to return to the Franchisor forthwith upon
demand all material including the Information, which material shall include, but shall not be
limited to, all documents, financial projection specifications, designs, notebooks and any
other records whatever and all copies of them which allude to or contain the Information
whether prepared or written by the Prospective Franchisee, his employees or agents
collectively or jointly with the Franchisor or a third party or provided by the Franchisor and
on whatever media and shall furnish the Franchisor with a certificate signed by a duly
authorised representative certifying that no copies have been made or retained.</p>
<p>4.4 The Prospective Franchisee shall ensure that his employees and agents are aware of and
comply with the confidentiality and non-disclosure provisions contained in this Agreement and
shall only disclose the Information to those employees or agents to whom such disclosure is
reasonably necessary. The Prospective Franchisee shall, before any disclosures are made to his
employees or agents, obtain from those of his employees or agents to whom any such Information
is to be disclosed or who may in any way obtain access to any such information, enforceable
undertakings in terms at least as extensive and binding upon such employees and agents as the
Prospective Franchisee is bound to the Franchisor hereunder.</p>
<p>4.5 The Prospective Franchisee agrees that he will accept full liability and will indemnify
the Franchisor against any loss or damage which the Franchisor may sustain or incur as a
result of any breach of this Agreement including any breach of confidence or wrongful
disclosure or use of the Information by any of his employees or agents irrespective of whether
or not such persons remain employees or agents of the Prospective Franchisee. The Prospective
Franchisee shall promptly notify the Franchisor if he becomes aware of any breach of this
Agreement by an employee or agent of the Prospective Franchisee and shall give the Franchisor
all assistance in connection with any proceedings which the Franchisor may institute against
such a person.</p>
<p>4.6 In the event that the Prospective Franchisee requires the assistance of any other party,
other than employees or agents of the Prospective Franchisee as provided for above to whom
disclosure of any Information is reasonably necessary, the Prospective Franchisee shall first
seek the Franchisor's written approval of such party and thereafter obtain from that party a
duly binding agreement on terms at least as binding and extensive upon that party as the
Prospective Franchisee is bound to the Franchisor hereunder which terms shall be agreed with
the Franchisor.</p>
<p>4.7 The disclosure of the Information pursuant to this Agreement shall not be construed as a
grant of any licence or other rights in respect thereof.</p>
<p>4.8 The undertakings in clauses 4.2, 4.3, 4.4, 4.5 and 4.6 of this Agreement shall continue
without limit.</p>

<p><strong>5. Termination</strong></p>
<p>5.1 This Agreement shall terminate on:</p>
<p>5.1.1 <strong>{{ end_date }}</strong>, or</p>
<p>5.1.2 on execution of the Franchise Agreement and any other documents referred to therein,</p>
<p>whichever shall be the earlier.</p>
<p>5.2 If the Franchise Agreement is not executed by the date specified in clause 5.1.1 of this
Agreement the Deposit will be repaid after deducting the Franchisor's expenses relating to
this Agreement and the Franchise Agreement.</p>

<p>SIGNED by or on behalf of the parties on the date which first appears in this Agreement.</p>

<table style="width:100%;">
<tr>
<td style="width:50%;vertical-align:top;padding-right:20px;">
<p>SIGNED by<br><strong>{{ recipient_name }}</strong></p>
<p style="font-style:italic;font-size:22px;">{{ franchisee_signature }}</p>
<p>[Name of prospective franchisee]</p>
<p>{{ franchisee_date }}<br>Date</p>
</td>
<td style="width:50%;vertical-align:top;">
<p>SIGNED by<br><strong>Ashley Costello, The Resilient People Ltd</strong></p>
<p style="font-style:italic;font-size:22px;">AJC</p>
<p>{{ agreement_date }}<br>Date</p>
</td>
</tr>
</table>
"""


def execute():
    if not frappe.db.exists("DocType", PRACTICE_DOCUMENT_DOCTYPE):
        return

    if frappe.db.exists(PRACTICE_DOCUMENT_DOCTYPE, {"document_title": INTENT_TITLE}):
        return

    try:
        doc = frappe.get_doc({
            "doctype": PRACTICE_DOCUMENT_DOCTYPE,
            "document_title": INTENT_TITLE,
            "document_type": "Agreement",
            "document_purpose": "Internal Compliance",
            "required_action": "Sign",
            "status": "Published",
            "mandatory": 0,
            "document_text": INTENT_TEMPLATE_TEXT,
            "signature_statement": (
                "By typing your name below, you confirm you have read and agree to the terms of "
                "this Deposit and Intent to Proceed Agreement."
            ),
        })
        doc.insert(ignore_permissions=True)
        frappe.db.commit()
    except Exception:
        frappe.log_error(frappe.get_traceback(), "add_franchisee_intent_practice_document failed")
