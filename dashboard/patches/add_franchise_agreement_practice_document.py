"""
Creates the "Franchise Agreement" Practice Document - the final Stage 1
contract. Full verbatim text of Ashley's real franchise agreement
(supplied as a .docx, 2026-10), with the deal-specific details replaced
by {{ }} merge-field placeholders: agreement_date, franchisee_name,
franchisee_address, commencement_date, expiry_date (always exactly
CONTRACT_TERM_YEARS - 5, per the real agreement's Term (clause 1.1) and
renewal (clause 3.2) - after commencement_date, see leads.get_contract_
sign_url, which computes it rather than asking Ashley to type it in),
territory_description
(the postcode list), permitted_area, franchisee_signature, franchisee_date.

Trade Name ("The Resilient Kid"), the registered Trade Mark number
(UK00004020678) and the Trade Mark image itself (the TRK logo, same for
every franchisee - not deal-specific) are NOT merge fields - they're
fixed constants for this brand in Ashley's real document.

Schedule 2's territory_map_html IS still per-deal, rendered server-side
from the Client Lead's own contract_territory_map Attach Image field
(see add_franchise_agreement_signing_and_uploads.py) - an <img> tag if
the franchisor has uploaded one, otherwise a plain reminder note.
Schedule 4 (Materials) is a static list matching the Franchise Brochure
page's own product list (hoodie/polo, books, journal, etc) - keep the
two in sync by hand if either one changes, there is no shared single
source of truth linking them yet.

franchisor_signature is Ashley's own typed signature, captured the same
way franchisee_signature is captured by sign_contract() - see
get_contract_sign_url, which now requires it before a sign link can even
be generated. No longer a hardcoded "AJC" pre-filled into the template -
see add_franchise_agreement_signing_and_uploads.py.

Idempotent/safe to leave in place if re-run - see
update_franchise_agreement_practice_document_v2.py and
update_franchise_agreement_practice_document_v3.py for the patches that
update an already-existing copy of this Practice Document (this one
only ever creates it, never updates it once it exists).
"""

import frappe

PRACTICE_DOCUMENT_DOCTYPE = "Practice Document"
FRANCHISE_AGREEMENT_TITLE = "Franchise Agreement"

FRANCHISE_AGREEMENT_TEMPLATE_TEXT = """
<div style="text-align:center; margin-bottom:24px;">
<img src="https://theresilienthub.co.uk/files/TRK%20Full%20Logo.png" style="height:56px;">
</div>
<p style="text-align:center;"><strong>DATED</strong></p>
<p style="text-align:center;"><strong>{{ agreement_date }}</strong></p>
<p style="text-align:center;"><strong>THE RESILIENT PEOPLE LIMITED</strong></p>
<p style="text-align:center;">and</p>
<p style="text-align:center;"><strong>{{ franchisee_name }}</strong></p>
<h2 style="text-align:center;">FRANCHISE AGREEMENT</h2>
<p>THIS AGREEMENT is dated <strong>{{ agreement_date }}</strong></p>
<h3>PARTIES</h3>
<p>(1)THE RESILIENT PEOPLE LIMITED incorporated and registered in England and Wales with company number 10625898 whose registered office address is at Fox Corner, Chester Road, Hartford, CW8 1LL(Franchisor);</p>
<p>(2) <strong>{{ franchisee_name }}</strong> of <strong>{{ franchisee_address }}</strong> (Franchisee).</p>
<h3>BACKGROUND</h3>
<p>(A)The Franchisor, as a result of practical business experience, has developed a business of providing a children’s wellbeing service (the Services, as further defined below) to both commercial and non-commercial which is carried on under the name “THE RESILIENT KID” (the Trade Name).</p>
<p>(B)The Franchisor has built up a reputation and goodwill in the Trade Name, which is associated with high standards of service and it is the registered proprietor of the Trade Marks under trade mark number UK00004020678,</p>
<p>(C)The Franchisor has developed a system for the establishment, operation and development of the Business utilising management procedures and methods of marketing and promotion (the System) which are confidential and which are the exclusive property of the Franchisor.</p>
<p>(D)The Franchisee wishes to acquire from the Franchisor the right and franchise to operate the Franchisee's Business (as defined below) in the Territory in accordance with the terms of this Agreement.</p>
<h3>AGREED TERMS</h3>
<h4>1. INTERPRETATION</h4>
<p>1.1. The definitions and rules of interpretation in this clause apply in this Agreement.</p>
<p>Business - the provision of a children’s wellbeing service to both commercial and non commercial customers;</p>
<p>Business Day - a day other than a Saturday, Sunday or public holiday in England when banks in London are open for business;</p>
<p>Commencement Date - the date set out in Schedule 1;</p>
<p>Confidential Information - any information which is disclosed to the Franchisee by the Franchisor pursuant to, or in connection with, this Agreement (whether orally or in writing and whether or not such information is expressly stated to be confidential), or which otherwise comes into the hands of the Franchisee in relation to the Business, the Franchisee's Business, the System, the Services or the Products other than information which is already in the public domain (otherwise than as a result of a breach of any obligation of confidentiality);</p>
<p>Expiry Date - the date set out in Schedule 1;</p>
<p>Franchisee's Business - the business operated by the Franchisee within the Territory in accordance with this Agreement;</p>
<p>Gross Revenue - all sums receivable (whether or not actually received or invoiced) arising directly or indirectly from the conduct of the Franchisee’s Business during each month (and for any period less than a complete month) during the continuance of this Agreement including all cash and credit transactions of whatever nature and including assumed gross takings calculated for the purpose of any loss of profits or business interruption insurance claim, but excluding VAT (if any);</p>
<p>Initial Fee - the amount set out in Schedule 1, payable in accordance with clause 4;</p>
<p>Intellectual Property - patents, rights to inventions, copyright and related rights, trademarks, trade names and domain names, rights in get-up, rights in goodwill or to sue for passing off, rights in designs, rights in computer software, database rights, rights in confidential information (including know-how and trade secrets) and any other intellectual property rights, in each case  whether registered or unregistered and including all applications (or rights to apply) for, and renewals or extensions of, such rights and all similar or equivalent rights or forms of protection which may, now or in the future, subsist in any part of the world relating to the Products, Services, Business and the System, owned by the Franchisor and acquired by the Franchisor from time to time;</p>
<p>Management Fee - the amounts set out In Schedule 1, payable in accordance with clause 4.3;</p>
<p>Manual - the Franchisor’s standard operating manual detailing the System, operations and procedures with which the Franchisee will comply in operating the Franchisee’s Business;</p>
<p>Marketing Fee - the amount set out in Schedule 1, payable in accordance with clause 4;</p>
<p>Materials - the materials listed in Schedule 4;</p>
<p>Minimum Performance Criteria - the minimum performance criteria as described in clause 4.10 or otherwise set down by the Franchisor in the Manual</p>
<p>Products - the Materials and such other products as shall, from time to time, be notified in writing by the Franchisor to the Franchisee;</p>
<p>Services - the provision of personal children’s wellbeing services and any other services to be used in, or supplied by, the Franchisee's Business as further described in the Manual;</p>
<p>Software - the software listed in the Manual or otherwise notified by the Franchisor to the Franchisee for use in the Franchisee’s Business (for which the Franchisee shall be obliged to enter into any related contracts for use or licence of the Software and pay any related fees);</p>
<p>Stationery - all letterheads, invoices, order forms, stickers, leaflets, posters, postcards and other documents approved or provided by the Franchisor from time to time or as referred to in the Manual to be used by the Franchisee for the purpose of the Franchisee's Business</p>
<p>System - the business format and method developed and implemented by the Franchisor in connection with the Business using the Intellectual Property, Confidential Information, operational procedures, methods, management, marketing and advertising techniques, part of which are contained in the Manual;</p>
<p>Term - five (5) years from the Commencement Date unless extended earlier determined as provided for by this Agreement;</p>
<p>Territory - the area referred to in Schedule 2;</p>
<p>Trade Marks - the trademarks set out Schedule 3 and any other trademarks registered by the Franchisor in relation to the Business from time to time during the Term;</p>
<p>Trade Name - The Resilient Kid;</p>
<p>VAT - value added tax chargeable under the Value Added Tax Act 1994 and any similar replacement or additional tax;</p>
<p>Website - the website(s) owned and operated by the Franchisor from time to time including those with the url www.theresilientacadamy.co.uk;</p>
<p>1.2. Clause, schedule and paragraph headings shall not affect the interpretation of this Agreement.</p>
<p>1.3. A person includes a natural person, corporate or unincorporated body (whether or not having separate legal personality) and that person's personal representatives, successors or permitted assigns.</p>
<p>1.4. The Schedules form part of this Agreement and shall have effect as if set out in full in the body of this Agreement. Any reference to this Agreement includes the Schedules.</p>
<p>1.5. A reference to a company shall include any company, corporation or other body corporate, wherever and however incorporated or established.</p>
<p>1.6. Words in the singular shall include the plural and vice versa.</p>
<p>1.7. A reference to one gender shall include a reference to the other genders.</p>
<p>1.8. A reference to any party shall include that party's personal representatives, successors or permitted assigns.</p>
<p>1.9. A reference to a statute or statutory provision is a reference to it as amended, extended or re-enacted from time to time.</p>
<p>1.10. A reference to a statute or statutory provision shall include any subordinate legislation made from time to time under that statute or statutory provision.</p>
<p>1.11. A reference to writing or written includes e-mail.</p>
<p>1.12. A reference to “this Agreement” or to any other agreement or a document referred to in this Agreement is a reference to this Agreement or such other document or agreement as varied or novated (in each case, other than in breach of the provisions of this Agreement) from time to time.</p>
<p>1.13. References to clauses and Schedules are to the clauses and Schedules of this Agreement and references to paragraphs are to paragraphs of the relevant Schedule.</p>
<p>1.14. Any phrase introduced by the terms including, include, in particular or any similar expression shall be construed as illustrative and shall not limit the sense of the words preceding those terms.</p>
<p>1.15. Any obligation in this Agreement not to do something includes an obligation not to agree or allow that thing to be done.</p>
<h4>2. RIGHTS GRANTED</h4>
<p>2.1. In consideration of the payment of the Initial Fee and the Management Fee by the Franchisee to the Franchisor in accordance with clause 4, the Franchisor grants to the Franchisee during the Term, and subject to and in accordance with the provisions of this Agreement, the right and licence to operate the Franchisee's Business and to provide the Services in accordance with the System within the Territory.</p>
<p>2.2. Save as otherwise provided for in this Agreement the Franchisor agrees that it will not itself operate or licence any third party to operate any business involving the provision of the Services under the Trade Name within the Territory.</p>
<p>2.3. The right and licence granted to the Franchisee to operate the Franchisee’s Business shall extend only to the Territory. The Franchisee agrees that it will not itself use nor will it permit or authorise any use directly or indirectly of the System or the Brand nor make available the Services outside the Territory but that if a third party franchisee of the Franchisor is requested by a potential client to provide the Services under the Name within the Territory, such third party franchisee may do so provided that they have not marketed their services within the Territory to such potential client.  For the avoidance of doubt, all other territories (other than the Territory) are expressly reserved to the Franchisor.</p>
<h4>3. TERM</h4>
<p>3.1. This Agreement shall commence on the Commencement Date and shall continue in force for the Term ending on the Expiry Date (subject to earlier termination in accordance with clause 16) and subject to the Franchisee’s right to the grant of the new franchise agreement contained clause 3.2.</p>
<p>3.2. The Franchisee may, by notice in writing to the Franchisor given not more than nine (9) months nor less than six (6) months before the end of the Term, request the grant of  a  new  agreement  (New  Agreement)  for  a  further  period  of  five  (5)  years commencing on the day following the Expiry Date. The Franchisor shall, by notice in writing to the Franchisee, given not less than four (4) months before the end of the Term, accept such request if:</p>
<p>3.2.1. at the date of the Franchisor’s notice there are no outstanding material breaches by the Franchisee of this Agreement and there are no grounds on which the Franchisor has a right to terminate this Agreement under clause 16 and both these conditions are still applicable on the Expiry Date;</p>
<p>3.2.2. the Franchisee has achieved the Minimum Performance Criteria during the entirety of the last two (2) years preceding the expiry of the Term;</p>
<p>3.2.3. the Franchisee has at all times performed her obligations under this Agreement to the reasonable satisfaction of the Franchisor and  the Franchisee's Business meets the Franchisor's requirements;</p>
<p>3.2.4. the Franchisee completes at her own expense such maintenance, replacement and/or purchase of the Products as the Franchisor considers to be necessary to bring the Franchisee’s Business up to the latest standards required by the Franchisor and to comply with any relevant statutory or other requirements which apply to the Business and within such period of time as the Franchisor may reasonably specify;</p>
<p>3.2.5. the Franchisee, and any person employed by or concerned with the Franchisee’s Business, completes such re-training or refresher training at such time and at such place as the Franchisor may reasonably request at the Franchisee’s own expense;</p>
<p>3.2.6. the Franchisee enters into the Franchisor’s then current form of franchise agreement (which may differ substantially from the terms of this Agreement and may contain revised Minimum Performance Criteria); and</p>
<p>3.2.7. the Franchisee reimburses the Franchisor any reasonable costs incurred by the Franchisor in granting a new agreement to the Franchisee.</p>
<p>3.3. On the grant of the New Agreement there shall be no obligation on the Franchisee to pay any sum expressed to be payable by way of initial fee and the Franchisor shall be under no obligation to perform any of the initial or other obligations contained in the New Agreement which are appropriate to the establishment of the business of a new franchisee.</p>
<p>3.4. Unless the parties agree otherwise in writing, any renewal under this clause 3 shall be without prejudice to the rights of the Franchisor outstanding at the end of the Term.</p>
<p>3.5. The Franchisee shall upon the execution of the New Agreement be deemed to have released and discharged the Franchisor from and against all claims and demands whether or not contingent which the Franchisee may have against the Franchisor arising from this Agreement or otherwise in any way out of the relationship between the Franchisor and the Franchisee</p>
<p>3.6. If the Franchisee continues to carry on the Franchisee's Business after the end of the Term, but without having entered into a New Agreement with the Franchisor, then she will be deemed to do so on the terms and conditions of this Agreement, save that either party will be entitled to terminate this Agreement on giving to the other party one (1) month’s written notice of termination.</p>
<h4>4. FEES</h4>
<p>4.1. On the date of this Agreement, the Franchisee shall pay the Initial Fee. The Initial Fee shall cover all the Franchisor's obligations under clause 5.</p>
<p>4.2. The Franchisee shall send to the Franchisor full details of the Gross Revenue in the preceding month (Gross Revenue Statement) either electronically or by first class mail to be received by the Franchisor not later than the seventh (7th) day of each month.</p>
<p>4.3. The Franchisee shall pay to the Franchisor the Management Fee by bank transfer so as to be received by the Franchisor on or before the twentieth (20th) day of the month in respect of the Gross Revenue in the preceding month together with any and all sums due for the supply of any Products, together with any underpayments made previously.</p>
<p>4.4. In the event that the Franchisee fails to send the Gross Revenue Statement by the due date, the Franchisee shall pay to the Franchisor the appropriate Management Fee based on the Franchisor’s best estimate of the Gross Revenue, such estimate to be based on the Gross Revenue in respect of the previous month.  Once the Franchisee has provided to the Franchisor the Gross Revenue Statement for the month, if there is any discrepancy between the amount of Management Fee paid (as set out above) and the amount duly payable, then:</p>
<p>4.4.1. if the amount of Management Fee paid is less than the amount due from the Franchisee, the Franchisee shall immediately on request pay the difference of such amount to the Franchisor; or</p>
<p>4.4.2. if the amount of Management Fee paid is more than the amount due from the Franchisee, the Franchisor shall be entitled to set off the excess amount against any sums outstanding (or future sums due) from the Franchisee.</p>
<p>4.5. In the event that any sums due to the Franchisor are not paid on the due date, such sums shall bear interest calculated at the rate of two per cent (2%) per month or part of a month for which there is any sum due but not paid before as well as after judgement.</p>
<p>4.6. In the event of any default in payment on the due date the Franchisor may, in addition to all other remedies available to the Franchisor, suspend the provision of all goods and services, until payment is made.</p>
<p>4.7. Unless the Franchisor otherwise notifies the Franchisee in writing, the Franchisee shall make all payments by bank transfer to the following bank account:</p>
<p>Bank: Starling Bank</p>
<p>Address: Operations Team, 5th Floor, Brunel House, 2 Fitzalan Road, Cardiff, CF24 0FG</p>
<p>Account name: The Resilient People Limited</p>
<p>Sort code:  64558141</p>
<p>Account number: 60-83-71</p>
<p>4.8. All fees due under this Agreement (including the Initial Fee, the Management Fee and the Marketing Fee) are exclusive of VAT, which shall, where applicable, be paid by the Franchisee at the prevailing rate on the due date for payment or receipt of the relevant invoice from the Franchisor (as may be). The Franchisor confirms that it is not currently registered for VAT. Should the Franchisor become VAT registered at any time during the Term, VAT shall from that date be added, at the prevailing rate, to the Initial Fee, the Management Fee, the Marketing Fee and any other fees due under this Agreement, in addition to the amounts set out in Schedule 1, and the Franchisor shall notify the Franchisee of this in writing.</p>
<p>4.9. The Franchisee shall be responsible for the prompt and complete payment of all invoices due to third party suppliers.</p>
<p>4.10. From the first (1st) anniversary of the Commencement Date, the Franchisee shall achieve a minimum monthly Gross Revenue of £1000 or 60% of the Franchisee’s average Gross Revenue for the previous twelve months (whichever is the higher) (Minimum Performance Criteria).  In subsequent years turnover must increase by 10% per annum. If the Franchisee fails to meet the Minimum Performance Criteria in three (3) or more successive months after the first (1st) anniversary of the Commencement Date, the Franchisor shall be entitled to:</p>
<p>4.10.1. require the Franchisee to take such steps as the Franchisor shall in its sole discretion deem necessary to assist the Franchisee to meet the Minimum Performance Criteria; or</p>
<p>4.10.2. adjust the boundaries of the Territory and/or remove the Franchisee’s  exclusivity within the Territory; or</p>
<p>4.10.3. terminate this Agreement in accordance with the provisions of clause 16.1.8.</p>
<p>4.11. Notwithstanding the provisions set out in this clause 4 (and not more than once in every twelve (12) month period) the Franchisee shall be entitled to serve four (4) weeks written notice on the Franchisor that the Franchisee intends to take up to two (2) weeks leave and the Franchisor agrees that the Franchisee shall be entitled to deduct from the Management Fee due in respect of the month such leave was taken (or months if the period of leave extends over two (2) months) that proportion of the Management Fee representing two (2) weeks work.</p>
<h4>5. FRANCHISOR'S INITIAL OBLIGATIONS</h4>
<p>5.1. In order to assist the Franchisee in opening for business, the Franchisor shall provide to the Franchisee the following:</p>
<p>5.1.1. a copy of the Manual (on loan);</p>
<p>5.1.2. a webpage (the “Franchisee’s Webpage”) relating to the Franchisee’s  Business on the Website;</p>
<p>5.1.3. an email address ending “@resilientkid.co.uk” and any password or other arrangements necessary for the Franchisee to use this email address for the purposes of the Franchisee’s Business;</p>
<p>5.1.4. the Materials;</p>
<p>5.1.5. the initial training as set out in clause 8 and Schedule 4;</p>
<p>5.1.6. general advice on how to set up the Franchisee's Business and initial marketing assistance.</p>
<h4>6. FRANCHISOR'S CONTINUING OBLIGATIONS</h4>
<p>The Franchisor shall at all times during the Term:</p>
<p>6.1. provide the Franchisee with know-how, advice and guidance relating to the operation of the Franchisee’s Business. Where additional support is required by the Franchisee in relation to substantial or continual operational business or customer service problems in the Franchisee’s Business then the Franchisee shall reimburse the Franchisor’s expenses incurred in providing such support immediately on demand and the Franchisor shall be entitled to charge a reasonable fee for its management time in accordance with the Manual ;</p>
<p>6.2. develop the System and update the Manual from time to time and inform the Franchisee of all such updates;</p>
<p>6.3. host, maintain and update the Website and the Franchisee’s Webpage as the Franchisor thinks fit; and</p>
<p>6.4. assist the Franchisee in procuring such goods and services as are necessary for the purposes of the Franchisee's Business.</p>
<h4>7. FRANCHISEE'S OBLIGATIONS</h4>
<p>7.1. The Franchisee shall undertake the initial training as detailed in clause 8 and shall begin operating the Franchisee’s Business within two (2) weeks following the completion of initial training, which shall be no later than three (3) months from the date of this Agreement, unless otherwise agreed with the Franchisor.</p>
<p>7.2. The Franchisee must, at their own expense and prior to the commence date of this agreement, apply for and provide satisfactory clearance from the Disclosure and Barring Services.  In addition the Franchisee will sign up to the DBS update service.  If, during the Term of this agreement The Franchisee receives a conviction, caution, reprimand or final warning from the police this must be disclosed to the Franchisor with forty eight (48) hours.</p>
<p>7.3. The Franchisee shall at all times during the Term, in relation to the Franchisee's Business:</p>
<p>7.3.1. pay to the Franchisor all fees and payments due to the Franchisor in accordance with the terms of this Agreement and the Manual;</p>
<p>7.3.2. take delivery of the Materials;</p>
<p>7.3.3. purchase  and  maintain  such  minimum  stock  of  the  Materials  as  is sufficient to meet the demands of customers;</p>
<p>7.3.4. operate the Franchisee's Business strictly in accordance with the Manual (including the content guidelines) and not do anything that could, in the Franchisor's reasonable opinion, damage the reputation of the Business, the Franchisee’s Business or the Intellectual Property;</p>
<p>7.3.5. submit to the Franchisor the Gross Revenue Statement and such other reports and accounting information as is required by the Franchisor;</p>
<p>7.3.6. comply with all advice and reasonable instructions of the Franchisor with regard to the operation of the System and the provision of the Services;</p>
<p>7.3.7. not offer or advertise any promotions which affect other franchisees of the Franchisor outside the Territory except in accordance with Clause 10;</p>
<p>7.3.8. use  her  best  endeavours  to  promote  and  extend  the  Franchisee’s Business within the Territory;</p>
<p>7.3.9. maintain and comply with all necessary licences and consents and comply with all relevant legislation in relation to the Franchisee's Business;</p>
<p>7.3.10. use her best endeavours to protect and promote the goodwill in the Business;</p>
<p>7.3.11. display on all stationery, emails and other correspondence “The Resilient Kid franchise operated under licence and independently owned by” followed by the Franchisee’s name;</p>
<p>7.3.12. trade at all times under the Permitted Name;</p>
<p>7.3.13. adhere at all times to the branding guidelines set out in the Manual;</p>
<p>7.3.14. only use the email address provided by the Franchisor for the provision of the Services;</p>
<p>7.3.15. procure and use in the Franchisee’s Business a suitable computer (with appropriate antivirus software) and the Software as shall be specified or approved by the Franchisor and proactively maintain and update such hardware and software in line with the Franchisor's instructions;</p>
<p>7.3.16. adhere to and comply with any internet use, social media and social networking policies set out by the Franchisor and contained in the Manual;</p>
<p>7.3.17. provide to the Franchisor all the information required by the Franchisor to keep the Franchisee’s webpage up-to-date and promptly inform the Franchisor of any changes to this information;</p>
<p>7.3.18. only use Stationery that has been approved in writing by the Franchisor;</p>
<p>7.3.19. use only the Software that the Franchisor has provided or approved and  comply with the terms of any applicable software licence;</p>
<p>7.3.20. supply  the  Services  to  end  users  only  on  the  standard  terms  and conditions of sale set out in the Manual and not on any other terms and conditions;</p>
<p>7.3.21. comply with ordering, invoicing and accounting procedures as required by  the Franchisor or as set out in the Manual;</p>
<p>7.3.22. ensure that adequate working capital and other financial resources are available for the Franchisee’s Business to ensure that the Franchisee is capable of fulfilling all obligations under this Agreement;</p>
<p>7.3.23. not offer credit to customers without the prior written consent of the  Franchisor;</p>
<p>7.3.24. pay all third party suppliers promptly in accordance with the terms of supply agreed with them and otherwise to adhere to terms agreed with third party suppliers (including venues);</p>
<p>7.3.25. not enter into any arrangement or agreement to factor, charge or otherwise deal with the debts of the Franchisee's Business without the prior written consent of the Franchisor;</p>
<p>7.3.26. not licence any other person to operate the Franchisee’s Business under the Trade Name;</p>
<p>7.3.27. without delay, inform the Franchisor of any improvement or modification to the Business or System or business opportunity which comes to her attention (and the Franchisee acknowledges that the Franchisor shall not be obliged to pay the Franchisee for any such improvement or modification);</p>
<p>7.3.27.1. promptly give the Franchisor any information that the Franchisee may obtain in relation to potential services outside the Territory or any matter that could affect services favourably or unfavourably inside or outside the Territory;</p>
<p>7.3.27.2. supply the Franchisor with such information relating to the Franchisee's Business in such form and at such times as the Franchisor may from time to time require;</p>
<p>7.3.27.3. introduce any improvements or modifications into the  Franchisee's Business when requested by the Franchisor;</p>
<p>7.3.27.4. at the request of the Franchisor, provide potential franchisees with information as reasonably requested;</p>
<p>7.3.27.5. attach any notices that the Franchisor requires to stationery, advertising or any other items used in the Franchisee’s Business;</p>
<p>7.3.27.6. use only stationery and marketing materials in connection with the Franchisee's Business as have been approved by the Franchisor; and</p>
<p>7.3.27.7. provide competent, sober and courteous service to every customer and present a neat and professional appearance;</p>
<p>7.3.27.8. maintain details of all customers on a database in accordance with the provisions contained in the Manual and  provide the Franchisor with, and/or allow the Franchisor to access remotely, all updates to such lists as and when they are made, subject always to the provisions of the Data Protection Act 2018;</p>
<p>7.3.27.9. notify the Franchisor of any complaints immediately after such complaint is made and handle any such complaints in accordance with the Franchisor’s instructions and the procedure set out in the Manual;</p>
<p>7.3.27.10. permit the Franchisor and any of its representatives at reasonable times during normal business hours without notice, to inspect the books and records of the Franchisee’s Business on request for the purposes of ascertaining whether the provisions of this Agreement are being complied with;</p>
<p>7.3.27.11. permit the Franchisor to contact any customer of the Franchisee’s Business to ensure that customer needs are being efficiently and courteously met by the Franchisee;</p>
<p>7.3.27.12. maintain a dedicated business landline or dedicated business mobile number, and call divert facility; and</p>
<p>7.3.27.13. attend all meetings and conferences as the Franchisor shall reasonably request, at the cost of the Franchisee.</p>
<h4>8. TRAINING</h4>
<p>8.1. The Franchisor shall provide to the Franchisee the initial training in the operation of the System and in all aspects of the Business.  The initial training shall take place at the Franchisor’s head office, or such other location as the Franchisor shall specify, and shall last for at least three (3) days.</p>
<p>8.2. The initial training shall cover the provision of the Services, basics of running a business including record keeping, business planning, bookkeeping, training on use and representation of the Brand, and such other matters as the Franchisor shall consider necessary for running the Franchisee’s Business.</p>
<p>8.3. The Franchisee shall:</p>
<p>8.3.1. not start the Franchisee's Business until the Franchisee has, in the reasonable opinion of the Franchisor, successfully completed the initial training; and</p>
<p>8.3.2. not allow any employee or sub-contractor to run classes without the prior written consent of the Franchisor who may require such employee or subcontractor successfully to complete at the Franchisee’s cost an initial training programme;</p>
<p>8.4. If on completion of the initial training the Franchisor reasonably believes that the Franchisee does not meet the minimum standards required the Franchisor has the right to terminate this Agreement immediately by giving notice in writing (in which event the Initial Fee will be refunded less an amount to compensate the Franchisor for the reasonable costs incurred in relation to the Franchisee’s appointment and training).</p>
<p>8.5. If in the Franchisor’s reasonable opinion the Franchisee or any staff require further training at any time during the term of this Agreement, the Franchisee shall ensure that such persons attend such training provided that the Franchisor shall not require the Franchisee or staff to attend more than five (5) days of training per year.</p>
<p>8.6. All training will be provided at the Franchisor’s standard rates as referred to in the Manual or otherwise at the Franchisee’s cost and in all cases the Franchisee shall be responsible for payment for the cost of accommodation, travel and subsistence incurred in attending any training together with the salaries of any staff and any training costs of the Franchisor.</p>
<h4>9. ACCOUNTING RECORDS</h4>
<p>The Franchisee shall:</p>
<p>9.1. keep and maintain complete and accurate accounts and records relating to the Franchisee's Business in a form approved by the Franchisor. All such records shall be full, accurate and up to date. If required by the Franchisor, the Franchisee shall have them audited by qualified auditors nominated by the Franchisor;</p>
<p>9.2. retain accounting and financial records for at least six (6) years after the end of any accounting year to which those records relate; and</p>
<p>9.3. supply to the Franchisor copies of the Franchisee’s accounts, records VAT returns and any other financial and fiscal information which the Franchisor may reasonably request during the Term and for a period of six (6) years after the termination of this Agreement.</p>
<h4>10. ADVERTISING</h4>
<p>10.1. The Franchisor shall:</p>
<p>10.1.1. promote the Trade Name and Business in such manner and at such times as it shall in its absolute discretion think fit;</p>
<p>10.1.2. provide the Franchisee with such promotional literature as it, in its absolute discretion, thinks fit.</p>
<p>10.2. The Franchisee shall promote and advertise the Franchisee's Business in the Territory in accordance with the Manual using any materials supplied by the Franchisor and co-operate with the Franchisor in relation to any special promotion or advertising campaign as the Franchisor shall require.</p>
<h4>11. INSURANCE</h4>
<p>11.1. The Franchisee shall take out and maintain an all-risk insurance policy with a reputable insurance company (or companies) with such amount of cover as the Franchisor may, in its absolute discretion, specify in the Manual and shall ensure that such policy covers the actions of her employees and any employee liability.</p>
<p>11.2. The Franchisee shall not breach, or allow any breach of, such policies.</p>
<p>11.3. The Franchisee shall provide the Franchisor with copies of all such policies and renewals.</p>
<p>11.4. The Franchisee shall promptly pay all premiums for such policies and immediately provide the Franchisor with evidence of payment of premiums.</p>
<p>11.5. If the Franchisee fails to take out and maintain such policies, the Franchisor may do so and the Franchisee shall reimburse the Franchisor for all costs and expenses incurred in doing so.</p>
<h4>12. INTELLECTUAL PROPERTY</h4>
<p>12.1. The Franchisor warrants that it is not aware of any reason why it might not be entitled to license the Intellectual Property and why the use of the Intellectual Property by the Franchisee in accordance with the terms of this Agreement would constitute an infringement of any third party's intellectual property.</p>
<p>12.2. The Franchisee shall use the Intellectual Property in the manner prescribed in this Agreement or in the Manual.  The Franchisor may at its discretion update, amend or add to the Intellectual Property used in connection with the Business and may require the Franchisee to implement and use such revised intellectual property at the Franchisee’s expense.</p>
<p>12.3. The Franchisee acknowledges that:</p>
<p>12.3.1. it does not have any right, title or interest in the Intellectual Property or any updates or improvements to it, save as specifically set out in this Agreement or the Manual; and</p>
<p>12.3.2. any goodwill (and any other rights) in the Trade Marks which result from the use by the Franchisee of the Trade Marks shall vest in the Franchisor.</p>
<p>12.4. If the Franchisee learns of any threatened or actual infringement of the Intellectual Property, or of any circumstance which suggests that the use of the Intellectual Property may infringe the intellectual property of a third party, it shall immediately inform the Franchisor, giving all such details as the Franchisor requests.</p>
<p>12.5. The Franchisor shall have conduct of any proceedings relating to the Intellectual Property and may take whatever action it, in its sole discretion, decides in respect of any infringement or alleged infringement of it, or arising from its use. Any rights that the Franchisee has under section 30 of the Trade Marks Act 1994 are expressly excluded. The Franchisee shall co-operate with the Franchisor in taking such action and the Franchisor shall meet any reasonable expenses of the Franchisee in doing so.</p>
<p>12.6. The Franchisee shall:</p>
<p>12.6.1. not apply for registration of any of the Intellectual Property (or any intellectual property that is confusingly similar to the Intellectual Property) in her own name, in any part of the world;</p>
<p>12.6.2. comply with the Manual and all requests by the Franchisor as to the use of the Intellectual Property and the ™, © and ® symbols in relation to the Intellectual Property;</p>
<p>12.6.3. give assistance to enable the Franchisor to register the Trade Marks;</p>
<p>12.6.4. not license (or purport to license) any other person to use any of the Intellectual Property;</p>
<p>12.6.5. not use the Intellectual Property other than as specifically permitted by this Agreement and the Manual;</p>
<p>12.6.6. not use any intellectual property that is confusingly similar to the Intellectual Property;</p>
<p>12.6.7. not do anything that may adversely affect the Intellectual Property or the Franchisor's right or title to it; and</p>
<p>12.6.8. immediately stop using any advertising or promotional material or packaging on receipt of a request by the Franchisor to do so.</p>
<p>12.7. The Franchisee acknowledges and agrees that all Intellectual Property in the Manual is and shall remain the exclusive property of the Franchisor. The Franchisee shall hold the Manual in safe custody at its own risk and maintained and kept in good condition by the Franchisee until returned to the Franchisor or destroyed at the option of the Franchisor in accordance with clause 17.3.</p>
<h4>13. SALE OF BUSINESS</h4>
<p>13.1. The Franchisee shall not have the right to assign this Agreement but it shall have the right to sell the Franchisee’s Business with the prior written consent of the Franchisor and subject to the conditions listed in clause 13.3.</p>
<p>13.2. Subject to clause 13.3, the Franchisor hereby undertakes to grant to a buyer of the Franchisee’s Business a franchise for a five (5) year term and upon similar terms and conditions to those contained in the Franchisor’s then current standard franchise agreement excluding the payment of any sum expressed therein to be payable by way of the initial fee.</p>
<p>13.3. The conditions with which the Franchisee must comply are as follows:</p>
<p>13.3.1. any proposed buyer must meet the Franchisor’s standards with regard to business experience, financial status, character and ability;</p>
<p>13.3.2. the proposed buyer shall submit a detailed offer in writing which shall be a bona fide arms-length offer and which shall provide for the Products and Stationery (if any) to be included in the sale together with the goodwill (i.e. the value of the customers) at valuation and the Franchisee shall provide a copy of such offer to the Franchisor;</p>
<p>13.3.3. the Franchisee shall pay to the Franchisor the Transfer Fee (as detailed in Schedule 1) plus the full amount of its legal costs in connection with the transfer (which shall not exceed £1,750 plus VAT); and</p>
<p>13.3.4. the Franchisee must not at the time of the application for consent be in breach of any of its obligations under this Agreement.</p>
<p>13.4. In the event that the Franchisee wishes to exercise the right to sell the Franchisee’s Business it shall as soon as possible submit to the Franchisor:</p>
<p>13.4.1. a copy of the written offer of purchase which the Franchisee proposes to accept together with details of any other terms agreed between the Franchisee and the proposed buyer;</p>
<p>13.4.2. payment to the Franchisor of the buyer check part of the Transfer fee for reviewing the proposed sale application whether or not it proceeds to completion and an undertaking by the Franchisee to pay the Franchisor’s reasonable costs whether legal or otherwise incurred in the event that the proposed transfer of the Franchisee’s Business should not proceed otherwise than by the Franchisor exercising the option to purchase as set out in clause 13.5 below; and</p>
<p>13.4.3. a completed franchise application form issued to it by the Franchisor which shall include a financial statement of affairs relating to the proposed buyer together with his business history and qualifications where applicable.</p>
<p>13.5. Upon receipt of written notice by the Franchisee of its intention to sell the Franchisee’s Business together with the documents and other details as set out in 13.4 above:</p>
<p>13.5.1. the Franchisor shall have in addition to its other rights hereunder an option to purchase the Franchisee’s Business from the Franchisee for the same price and upon the same terms as the proposed buyer shall have offered to the Franchisee;</p>
<p>13.5.2. the Franchisor shall enjoy the benefit of such option for a period of twenty eight (28) days after receipt of the Franchisee’s notice to sell; and</p>
<p>13.5.3. if the Franchisor serves notice exercising its option the sale and purchase of the Business shall be completed within twenty (20) days following the service of the Franchisor’s notice.</p>
<p>13.6. If the Franchisor shall not have exercised its option referred to in clause 13.5 above within such period of twenty eight (28) days and if the Franchisor shall have given its written consent to the proposed sale of the Franchisee’s Business then:</p>
<p>13.6.1. the Franchisee shall be entitled within the period of three (3) months from the date of the Franchisee’s notice or varied notice (if any) thereafter to proceed with its application to sell the Franchisee’s Business to the proposed buyer upon the same terms or on terms no more favourable to a buyer than those notified to the Franchisor in accordance with the provisions of this clause 13;</p>
<p>13.6.2. the Franchisee shall comply with all procedures set out in the Manual as regards the sale including making payment (to the Franchisor’s solicitors) of the Franchisor’s standard fee for the use of its draft franchised business sale and purchase agreement to be adapted as required by the Franchisee its buyer and their solicitors but approved by the Franchisor’s solicitors before execution and upon the completion of any contract between the Franchisee and the proposed buyer deposit with the Franchisor the Transfer Fee from the consideration for the said sale;</p>
<p>13.6.3. upon completion of the transaction the purchase price or the balance thereof shall be deposited with the Franchisor’s solicitors as agent for the Franchisee; and</p>
<p>13.6.4. the Franchisor shall deduct from the said purchase price the sum of any amount owing to it by the Franchisee up to and including the proposed date of the sale of the Franchisee’s Business and any outstanding balance of the purchase price shall then be remitted by the Franchisor to the Franchisee within fourteen (14) days of the date of the receipt by the Franchisor of the full purchase price</p>
<p>13.7. Upon entry by the buyer into the new franchise agreement the rights and obligations of the Franchisee in respect of this Agreement shall terminate save as otherwise provided.</p>
<h4>14. DEATH OR INCAPACITY</h4>
<p>14.1. If the Franchisee dies during the Term, her personal representatives shall, within seven (7) days, inform the Franchisor of her death, and subject to the Franchisor’s prior approval an immediate family member or friend may operate the Franchisee’s Business. Upon the Franchisor being satisfied that such family member or friend would be acceptable as a principal by the criteria set out in clause 13.3 above, the Franchisor shall consent to a transfer of the Franchisee’s Business pursuant to the provisions of clause 13.  If the personal representatives of the Franchisee shall wish to sell the Franchisee’s Business to any other party then they shall seek a purchaser for the Franchisee’s Business with all possible speed and the Franchisee’s Business may be sold within a period of three (3) months from the date of the death of the Franchisee. In such circumstances, the terms of clause 13 shall apply as if references in them to the Franchisee were to the Franchisee's personal representatives and the third party purchaser were either the beneficiary or beneficiaries of the Franchisee’s Business in the Franchisee’s will, or under the rules on intestacy, or, if such beneficiaries do not wish operate the Franchisee’s Business, any other third party specified in the notice by the personal representatives.</p>
<p>14.2. In the event of the death of the Franchisee or if the Franchisee is, in the reasonable opinion of the Franchisor, unable to a material degree to operate the Franchisee's Business to the standard required by the Manual for a period in excess of twenty eight (28) consecutive days or a total of ninety (90) days in any six (6) month period, the Franchisor may appoint a manager of the Franchisee's Business who shall have full powers to operate the Franchisee's Business and to take all steps to ensure that the Franchisee complies with the terms of this Agreement. The Franchisee shall pay to the Franchisor one hundred and fifteen per cent (115%) of the costs incurred by the Franchisor in engaging such a manager to reimburse the Franchisor for the cost of the manager and the Franchisor’s own time in appointing such manager.</p>
<h4>15. CONFIDENTIALITY</h4>
<p>15.1. The Franchisee undertakes that she shall not at any time copy, use or disclose to any person any Confidential Information, except as permitted by this Agreement.</p>
<p>15.2. The Franchisee may disclose Confidential Information as may be required by law, court order or any governmental or regulatory authority.</p>
<p>15.3. The Franchisee shall not use the Confidential Information for any purpose other than to perform her obligations under this Agreement.</p>
<h4>16. TERMINATION</h4>
<p>16.1. The Franchisor may terminate this Agreement with immediate effect without prejudice to any of its rights or remedies, by giving written notice to the Franchisee if:</p>
<p>16.1.1. the Franchisee, in the opinion of the Franchisor, does, or permits to be done, any act which might jeopardise or invalidate the registration of the Trade Marks (or any of them) or does any act which might assist, or give rise to, an application to remove the Trade Marks, or which might prejudice the right or title of the Franchisor to the Trade Marks; or</p>
<p>16.1.2. the Franchisee purports to assign any of the rights or licences granted under this Agreement other than in accordance with the terms of this Agreement; or</p>
<p>16.1.3. the Franchisee gives to the Franchisor any false or misleading information, or makes any misrepresentation in connection with obtaining this Agreement or during the Term, in connection with the Franchisee's Business; or</p>
<p>16.1.4. the Franchisee suspends or ceases, or threatens to suspend or cease, to carry on all or a substantial part of the Franchisee's Business; or</p>
<p>16.1.5. the Franchisee discloses or permits or suffers the disclosure of any part of the Manual or other Confidential Information contrary to the terms hereof; or</p>
<p>16.1.6. the Franchisee becomes incapacitated as specified in clause 14.2 above or becomes a patient as defined by the Mental Health Act 1983</p>
<p>16.1.7. the Franchisee fails to successfully complete the initial training referred to in clause 8; or</p>
<p>16.1.8. the Franchisee fails to achieve the Minimum Performance Criteria in accordance with clause 4.10; or</p>
<p>16.1.9. the Franchisee suspends, or threatens to suspend, payment of her debts or is, or is deemed to be bankrupt, unable to pay her debts as they fall due for payment; or</p>
<p>16.1.10. the Franchisee commences negotiations with all or any class of its or their creditors with a view to rescheduling any of her debts, or enters into any composition or arrangement with her creditors generally; or</p>
<p>16.1.11. the Franchisee does not provide clearance from the Disclosure Barring Service or is convicted of a criminal offence other than a road traffic offence; or</p>
<p>16.1.12. the Franchisee shall at any time:</p>
<p>16.1.12.1. fail to pay on the due date for payment any amounts due and payable to the Franchisor hereunder; or</p>
<p>16.1.12.2. fail to obtain any written approval or consent of the Franchisor as expressly required by this Agreement and within seven (7) days of its receipt of written notice of default from the Franchisor, shall fail to remedy such breach of its obligations hereunder to the Franchisor; or</p>
<p>16.1.13. persistent, valid complaints are received by the Franchisor about the quality of the services provided by the Franchisee and the Franchisee, having received notice of such complaints, fails to improve such service to the reasonable satisfaction of the Franchisor within the Franchisor’s stipulated timeframes; or</p>
<p>16.1.14. the Franchisee commits a breach of any other term of this Agreement and, if such breach is remediable, fails to remedy that breach within a period of twenty eight (28) days after being notified in writing to do so; or</p>
<p>16.1.15. the Franchisee repeatedly breaches any of the terms of this Agreement in such a manner as to reasonably justify the opinion that her conduct is inconsistent with having the intention or ability to give effect to the terms of this Agreement.</p>
<p>16.2. The parties acknowledge and agree that any breach of clause 7, clause 12, clause 13 and clause 15 shall constitute a material breach for the purposes of this clause.</p>
<h4>17. CONSEQUENCES OF TERMINATION</h4>
<p>17.1. On termination or expiry of this Agreement for any reason clause 12, clause 15, clause 17, clause 18, clause 18.1, clause 21, clause 22, clause 24, clause 29, clause 29 and clause 34 shall continue in force.</p>
<p>17.2. Any termination or expiry of this Agreement shall not affect any rights or liabilities that have accrued prior to such termination.</p>
<p>17.3. On termination or expiry of this Agreement for any reason, the Franchisee shall:</p>
<p>17.3.1. immediately pay the Franchisor the full amount of all sums due from the Franchisee to the Franchisor together with any interest payable in accordance with clause 4.4;</p>
<p>17.3.2. cease to operate the Franchisee's Business and System and to trade under any of the Trade Marks, and not hold herself out as a franchisee of the Franchisor or do anything that may indicate any relationship between her and the Franchisor;</p>
<p>17.3.3. immediately stop using the Intellectual Property, including the Trade Marks and take all steps as the Franchisor may reasonably require to remove the name of the Franchisee as licensee at the UK Trade Marks Registry and  all  other  applicable  trade  mark  registries  in other jurisdictions;</p>
<p>17.3.4. pass all enquiries, and full details of potential customers, to the Franchisor;</p>
<p>17.3.5. give all customer lists and full details of contracts with customers to the Franchisor;</p>
<p>17.3.6. return or at the option of the Franchisor, destroy, all copies of the Manual, and any Products or materials bearing the Trade Marks;</p>
<p>17.3.7. pay all debts owing to creditors of the Franchisee's Business; and</p>
<p>17.3.8. assign to the Franchisor all domain name registrations and rights in web site content owned or used by the Franchisee in the Franchisee’s Business.</p>
<p>17.4. If the Franchisee fails to fulfil her obligations under this clause 17 within a reasonable time, the Franchisor may, at the expense of the Franchisee, immediately and without notice, enter onto the Franchisee's premises and take such steps as it thinks fit to fulfil any outstanding obligations.</p>
<h4>18. RESTRICTIONS</h4>
<p>18.1. The Franchisee hereby covenants and agrees that during the continuance of this Agreement for a period of one (1) year after the termination (for any reason) whether by itself or together with any person firm or company in any capacity whatsoever save as authorised hereunder directly or indirectly:</p>
<p>18.1.1. not within the Territory (except as a holder of not more than five percent (5%) of the issued shares of a publicly quoted company) to be engaged or interested or concerned in the provision of the Services or of any like services or in any business operating in competition with the Business and/or with any of the or other franchisees or licensees of the Franchisor</p>
<p>18.1.2. not within the Territory of any other franchisees or licensees of the Franchisor or the Franchisor (except as a holder of not more than five percent (5%) of the issued shares of a publicly quoted company) to be engaged or interested or concerned in the provision of the Services or any like services or in any business which is similar to or in conflict with the Business and/or with the business of any of the other franchisees or licensees of the Franchisor</p>
<p>18.1.3. not without the prior written consent of the Franchisor to employ or seek to employ any person who is at that time or has at any time in the previous twelve (12) months been a franchisee or been employed or engaged in a senior management or other senior position by the Franchisor or by any other franchisee or licensee of the Franchisor in any business carried on under the Brand using the System</p>
<p>18.1.4. not to solicit Customers or former Customers (who were Customers in the previous twelve (12) months) of the Franchisee’s Business nor divert or seek to divert any custom from the Franchisor or any other franchisee or licensee of the Franchisor</p>
<p>18.1.5. use the customer database for any other business activity than the operation of the Franchisee’s Business</p>
<p>18.2. The Franchisee hereby agrees that all the restrictions in this clause are reasonable and valid in the circumstances of this Agreement</p>
<p>18.3. At any time after the termination or expiry of this Agreement the Franchisee shall not reveal or use for the benefit of the Franchisee or any third party any trade secret or confidential information of the Franchisor or any confidential information acquired from the Franchisor in connection with the Business</p>
<p>18.4. If any provision of this clause is determined to be void or unenforceable in whole or in part it shall not be deemed to affect or impair the validity of any other provision of this clause or any other part thereof all of which provisions shall remain in full force and effect and where such provision would be valid and enforceable if part of the wording thereof was deleted or the period reduced or the range of services or the area was reduced in scope the said restriction shall apply with such modifications as may be necessary to make it valid and effective</p>
<h4>19. INDEMNITY</h4>
<p>The Franchisee shall indemnify the Franchisor against all liabilities, costs, expenses, damages and losses (including any direct, indirect or consequential losses, loss of profit, loss of reputation and all interest, penalties and legal and other professional costs and expenses) suffered or incurred by the Franchisor arising out of or in connection with the Franchisee's breach or negligent performance or non- performance of this Agreement.</p>
<h4>20. ENTIRE AGREEMENT</h4>
<p>20.1. This Agreement, the Manual, and any documents referred to in it constitute the whole agreement between the parties and supersede any previous arrangement, understanding or agreement between them relating to the subject matter of this Agreement.</p>
<p>20.2. If there is an inconsistency between the terms of this Agreement and the Manual, or any other documents referred to in it, the terms of this Agreement shall prevail.</p>
<p>20.3. Each party warrants to the other parties that, in entering into this Agreement and the documents referred to in it, it does not rely on any statement, representation, assurance or warranty (Representation) of any person (whether a party to this Agreement or not) other than as expressly set out in this Agreement or those documents.</p>
<p>20.4. Each party agrees and undertakes to the other parties that the only rights and remedies available to it arising out of, or in connection with, a Representation shall be solely for breach of contract, in accordance with the provisions of this Agreement.</p>
<p>20.5. Nothing in this clause shall limit or exclude any liability for fraud.</p>
<h4>21. FURTHER ASSURANCE</h4>
<p>The Franchisee shall and shall use all reasonable endeavours to procure that any necessary third party shall (at their own expense) promptly execute and deliver all such documents, and perform such acts, as the Franchisor may, from time to time, reasonably require for the purpose of giving full effect to this Agreement.</p>
<h4>22. DATA PROTECTION</h4>
<p>22.1. The Franchisee agrees that it shall, in relation to personal data processed  in connection with this Agreement (Franchise Data):</p>
<p>22.1.1. prior to commencing operation of the Franchisee’s Business, register all data processing activities with the Information Commissioner’s Office;</p>
<p>22.1.2. process the Franchise Data in accordance with all data protection laws, including the General Data Protection Regulation (GDPR) and any legislation that subsequently adds to or amends the GDPR.;</p>
<p>22.1.3. process the Franchise Data only so far as is necessary for the purpose of performing its obligations under this Agreement;</p>
<p>22.1.4. not disclose Franchise Data to or allow access to it other than by employees or third parties engaged by the Franchisee to perform the obligation imposed on the Franchisee by this Agreement, and ensure that such employees or third parties are subject to written contractual obligations concerning the Franchise Data which are no less onerous than those imposed on the Franchisee by this Agreement; and</p>
<p>22.1.5. assist the Franchisor to comply with such obligations as are imposed on the Franchisor by the GDPR 2018. This includes the obligation to:</p>
<p>22.1.5.1. provide the Franchisor with reasonable assistance in complying with any subject access request served on the Franchisor under article 15 of the 2018 Act.</p>
<p>22.1.5.2. promptly inform the Franchisor about  the  receipt  of  any subject access request received by the Franchisee;</p>
<p>22.1.5.3. not disclose or release any Franchise Data in response to a subject access request without first consulting with and obtaining the consent of the Franchisor; and</p>
<p>22.1.5.4. inform any individual whose personal data may be processed under this Agreement (including prospective customers as well as those with whom the Franchisee enters into contracts) of such processing. This includes informing such individuals that, on the termination of this Agreement, personal data relating to them (including personal data contained in any customer list) shall be retained by or, as the case may be, transferred to the Franchisor. In addition, the Franchisee shall obtain any necessary consents for such processing under the 2018 Act. To ensure that the Franchisor's obligations under the 2018 Act are complied with, the Franchisee agrees to allow the Franchisor to approve and, if the Franchisor deems necessary, amend any such notice.</p>
<p>22.2. Where the Franchisee acts as data processor on behalf of the Franchisor in relation to the Franchise Data, the Franchisee shall:</p>
<p>22.2.1. maintain technical  and  organisational  security  measures  sufficient  to comply at least with the obligations imposed on the Franchisor by the seventh data protection principle set out in the 2018 Act; and</p>
<p>22.2.2. only process Franchise Data for and on behalf of the Franchisor for the purpose of performing her obligations under, and in accordance with, this Agreement and only on written instructions from the Franchisor to ensure compliance with the 2018 Act.</p>
<p>22.3. The Franchisee shall indemnify the Franchisor against all claims and proceedings and all liability, loss, costs and expenses incurred by the Franchisor as a result of any claim made or brought by an individual or other legal person in respect of any loss, damage or distress caused to them as a result of the Franchisee's unauthorised processing, unlawful processing, destruction of and/or damage to any Franchise Data processed by the Franchisee, its employees or agents.</p>
<p>22.4. In this clause data controller, data processor, personal data and processing shall have the same meanings as set out in the 2018 Act, and process shall be construed accordingly.</p>
<p>22.5. The Franchisee hereby consents and agrees to the disclosure of its personal data by the Franchisor to the British Franchise Association and such other third parties as the Franchisor shall at its discretion determine.</p>
<p>22.6. The Franchisee will comply with all data protection laws within the Territories in which the Franchisee operates and where the Franchisee is based.</p>
<h4>23. ASSIGNMENT BY FRANCHISOR</h4>
<p>23.1. The Franchisor may, at any time, assign (absolutely or by way of security and in whole or in part), transfer, mortgage, charge or deal in any other manner with the benefit of any or all of any other party's obligations or any benefit arising under this Agreement. In the case of the Franchisor assigning this Agreement, the Franchisor shall procure that the assignee enter into a direct covenant with the Franchisee thereafter to observe and perform all the Franchisor’s obligations herein contained.</p>
<h4>24. THIRD PARTY RIGHTS</h4>
<p>24.1. A person who is not a party to this Agreement shall not have any rights under the Contracts (Rights of Third Parties) Act 1999 to enforce any term of this Agreement except where such rights are expressly granted by clause 23, but this does not affect any right or remedy of a third party which exists, or is available, apart from that Act.</p>
<p>24.2. The rights of the parties to terminate, rescind or agree any variation, waiver or settlement under this Agreement is not subject to the consent of any person that is not a party to this Agreement.</p>
<h4>25. NO PARTNERSHIP OR AGENCY</h4>
<p>Nothing in this Agreement is intended to, or shall be deemed to, establish any partnership or joint venture between any of the parties, nor constitute any party the agent of another party, nor authorise any party to make or enter into any commitments for or on behalf of any other party except as expressly provided in clause 13.</p>
<h4>26. JOINT FRANCHISEES</h4>
<p>26.1. Where the Franchisee is two or more individuals, or a partnership, then all covenants and agreements on the part of the Franchisee herein contained shall be deemed to be joint and several covenants on their part.</p>
<h4>27. FORCE MAJEURE</h4>
<p>27.1. Neither of the parties to this Agreement shall be responsible to the other for any delay in performance or non-performance due to any causes beyond the reasonable control of the parties hereto and the effected party shall promptly upon the occurrence of any such cause so inform the other party in writing stating that the cause has delayed or prevented its performance hereunder and thereafter such party shall take all actions within its power to comply with the terms of this Agreement as fully and promptly as possible.</p>
<h4>28. SET-OFF</h4>
<p>28.1. All amounts due under this Agreement from the Franchisee to the Franchisor shall be paid in full without any deduction or withholding other than as required by law. The Franchisee shall not be entitled to assert any credit, set-off or counterclaim against the Franchisor in order to justify withholding payment of any such amount in whole or in part.</p>
<p>28.2. The Franchisor may, at any time or times, without notice to the Franchisee, set off any liability of the Franchisee to the Franchisor against any liability of the Franchisor to the Franchisee, in either case, whether under this Agreement or otherwise and whether any such liability is present or future, liquidated or unliquidated. Any exercise by the Franchisor of its rights under this clause shall be without prejudice to any other rights or remedies available to it under this Agreement or otherwise.</p>
<h4>29. SEVERANCE</h4>
<p>29.1. If any court or competent authority finds that any provision of this Agreement (or part of any provision) is invalid, unenforceable or illegal, that provision or part-provision shall, to the extent required, be deemed to be deleted, and the validity and enforceability of the other provisions of this Agreement shall not be affected unless, in the reasonable opinion of the Franchisor, the purpose of this Agreement is frustrated as a result.</p>
<p>29.2. If any invalid, unenforceable or illegal provision would be valid, enforceable and legal if some part of it were deleted, the provision shall apply with the minimum modification necessary in the reasonable opinion of the Franchisor to make it legal, valid and enforceable and, to the greatest extent possible, to give effect to the commercial intention of the parties.</p>
<h4>30. VARIATION</h4>
<p>No variation of this Agreement or of any document referred to in it shall be effective unless it is in writing and signed by the parties (or their authorised representatives).</p>
<h4>31. WAIVER</h4>
<p>No failure or delay by a party to exercise any right or remedy provided under this Agreement or by law shall constitute a waiver of that (or any other) right or remedy, nor shall it preclude or restrict the further exercise of that or any other right of remedy. No single or partial exercise of such right or remedy shall preclude or restrict the further exercise of that (or any other) right or remedy.</p>
<h4>32. COMPLIANCE WITH LEGISLATION</h4>
<p>32.1. The Franchisor has the right, at any time, to make such amendments to this Agreement as it (in its sole discretion) deems necessary to ensure that the same is compatible with:</p>
<p>32.1.1. any block exemption from time to time in force which may (in whole or in part) replace Commission Regulation No. 330/2010 (or any amendment or re-enactment of it) and/or any UK successor legislation and/or</p>
<p>32.1.2. any other law, statute, ordinance, decree, treaty, regulation, directive, order, notice or official published plan or policy with legal or actual force in any geographical area which could affect the legality or enforceability of this Agreement (or part of it) and to ensure that all the provisions of this Agreement are binding upon the parties and enforceable against them under any relevant legislation.</p>
<p>32.2. The Franchisor will notify the Franchisee in writing of any amendments it considers to be necessary at any time upon advice received in writing by it from a solicitor or barrister experienced in franchising and the reasons therefor and request the Franchisee’s approval thereto.  Upon receipt of the Franchisee’s written agreement to the same such amendments shall be incorporated in and form part of this Agreement. If however after a period of twenty eight (28) days following written notice from the Franchisor to the Franchisee the Franchisee shall not have confirmed its agreement thereto such amendments shall be deemed to be incorporated into this Agreement as if the same had been expressly agreed between the parties hereto.</p>
<h4>33. COUNTERPARTS</h4>
<p>This Agreement may be executed in any number of counterparts, each of which, when executed and delivered, shall constitute an original of this Agreement, but all the counterparts shall together constitute the same agreement.</p>
<h4>34. GOVERNING LAW AND JURISDICTION</h4>
<p>34.1. This Agreement, and any dispute or claim arising out of or in connection with it or its subject matter or formation (including non-contractual disputes or claims), shall be governed by and construed in accordance with the law of England and Wales.</p>
<p>34.2. The parties irrevocably agree that the courts of England and Wales shall have exclusive jurisdiction to settle any dispute or claim that arises out of, or in connection with, this Agreement or its subject matter or formation (including non-contractual disputes or claims).</p>
<p>This Agreement has been entered into on the date stated at the beginning of it.</p>
<h3>Addendum to Franchise Agreement</h3>
<p>This Addendum is made on <strong>{{ agreement_date }}</strong> between:</p>
<p>The Resilient People Limited (the Franchisor); and</p>
<p><strong>{{ franchisee_name }}</strong> (the Franchisee).</p>
<h3>BACKGROUND:</h3>
<p>The Franchisee has entered into a Franchise Agreement dated {{ agreement_date }} to operate “The Resilient Kid” business. The parties now agree to extend the scope of the Franchisee’s Business to include The Resilient Teen.</p>
<h4>Agreed Terms:</h4>
<p>The definition of “Business” in the Franchise Agreement shall be deemed amended to include The Resilient Teen.</p>
<p>The Franchisee shall pay to the Franchisor an additional initial fee of £4000</p>
<p>The Franchisee shall complete any additional training as reasonably required by the Franchisor.</p>
<p>All other terms of the Franchise Agreement remain in full force and effect.</p>
<p>Signed: <span style="font-style:italic;">{{ franchisor_signature }}</span> (Franchisor)</p>
<p>Signed: <span style="font-style:italic;">{{ franchisee_signature }}</span> (Franchisee)</p>
<h3>SCHEDULE 1</h3>
<h3>FEES:</h3>
<p><strong>Initial Fee:</strong> £5,999 (less any deposit paid)</p>
<p>Management Fee:shall be calculated as follows:</p>
<table style="width:100%; border-collapse:collapse;" border="1" cellpadding="6">
<tr>
<th>Gross Revenue achieved</th>
<th>Percentage of Gross Revenue payable as Management Fee</th>
</tr>
<tr>
<td>Up to £1,500</td>
<td>Ten percent (10%)</td>
</tr>
<tr>
<td>Between £1,500 - £2,999</td>
<td>Eight percent (8%)</td>
</tr>
<tr>
<td>£3,000 +</td>
<td>Seven percent (7%)</td>
</tr>
</table>
<p>1. All fees stated in this Schedule are correct as at the date of this Agreement.</p>
<p>2. The Franchisor reserves the right to review and increase the Management Fee, Marketing Fee and/or other fees set out in this Schedule from time to time, on reasonable written notice to the Franchisee.</p>
<p>Marketing Fee:2% of gross monthly revenue</p>
<p>Transfer Fee: All fees are expressed exclusive of VAT which shall also be charged. The Franchisor is not currently VAT registered - see clause 4.8 for what happens if that changes.</p>
<p><strong>Commencement Date:</strong> {{ commencement_date }}</p>
<p><strong>Expiry Date:</strong> {{ expiry_date }} <span class="dashboard-help">(five years from the Commencement Date)</span></p>
<p><strong>Permitted Name:</strong> The Resilient Kid ({{ permitted_area }})</p>
<h3>SCHEDULE 2</h3>
<h3>THE TERRITORY</h3>
<p><strong>All of the area within the postcode areas:</strong></p>
<p>{{ territory_description }}</p>
<p>as shaded grey on the map below:</p>
{{ territory_map_html }}
<p><strong>Commencement Date:</strong> {{ commencement_date }} &nbsp;&nbsp; <strong>Expiry Date:</strong> {{ expiry_date }}</p>
<h3>SCHEDULE 3</h3>
<h3>THE TRADE MARKS</h3>
<p>Trade Mark # UK00004020678</p>
<p><strong>Mark text:</strong><br>The Resilient Kid ({{ permitted_area }})</p>
<p>Classes:</p>
<p>41, 44</p>
<p>Registered to:</p>
<p>The Resilient People Limited</p>
<p>Fox Corner, Chester Road, Hartford, CW8 1LL</p>
<p><img src="https://theresilienthub.co.uk/files/TRK%20Full%20Logo.png" style="max-width:280px;"></p>
<h3>SCHEDULE 4</h3>
<h3>MATERIALS</h3>
<ul>
<li>Polo shirt or T-shirt</li>
<li>Hoodie or Sweatshirt</li>
<li>10 x A parent's guide to raising a resilient kid</li>
<li>10 x Resilient kid journal</li>
<li>1 x Tote bag</li>
<li>10 x Branded pens</li>
<li>10 x Kids pencils</li>
<li>1 x Brave jar</li>
<li>10 x Book 1 - Framework</li>
<li>5 x Worries workbook</li>
<li>5 x Anger workbook</li>
<li>5 x Confidence workbook</li>
<li>5 x Emotions workbook</li>
<li>10 x Toolbox and stickers</li>
</ul>
<p>The Franchisee acknowledges that she has been advised to seek her own  independent legal and financial advice prior to entering into this Agreement.</p>
<h4>Execution</h4>
<p><strong>DATED</strong> {{ agreement_date }}</p>
<p><strong>{{ franchisee_name }}</strong></p>
<table style="width:100%;">
<tr><td style="width:50%;vertical-align:top;padding-right:20px;">
<p>SIGNED by <strong>ASHLEY COSTELLO</strong><br>for and on behalf of<br><strong>THE RESILIENT PEOPLE LIMITED</strong></p>
<p style="font-style:italic;font-size:22px;">{{ franchisor_signature }}</p>
</td><td style="width:50%;vertical-align:top;">
<p>SIGNED by<br><strong>{{ franchisee_name }}</strong></p>
<p style="font-style:italic;font-size:22px;">{{ franchisee_signature }}</p>
<p>{{ franchisee_date }}</p>
</td></tr></table>
"""


def execute():
    if not frappe.db.exists("DocType", PRACTICE_DOCUMENT_DOCTYPE):
        return

    if frappe.db.exists(PRACTICE_DOCUMENT_DOCTYPE, {"document_title": FRANCHISE_AGREEMENT_TITLE}):
        return

    try:
        doc = frappe.get_doc({
            "doctype": PRACTICE_DOCUMENT_DOCTYPE,
            "document_title": FRANCHISE_AGREEMENT_TITLE,
            "document_type": "Agreement",
            "document_purpose": "Internal Compliance",
            "required_action": "Sign",
            "status": "Draft",
            "mandatory": 0,
            "document_text": FRANCHISE_AGREEMENT_TEMPLATE_TEXT,
            "signature_statement": (
                "By signing below, you confirm you have read, understood and agree to be bound "
                "by this Franchise Agreement."
            ),
        })
        doc.insert(ignore_permissions=True)
        frappe.db.commit()
    except Exception:
        frappe.log_error(frappe.get_traceback(), "add_franchise_agreement_practice_document failed")
