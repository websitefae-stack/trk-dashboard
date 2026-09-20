"""
Creates the "Franchise Agreement" Practice Document - the final Stage 1
contract, seeded from Ashley's own real franchise agreement wording with
the deal-specific details (franchisee name/address, dates, fees,
permitted name/area) replaced by {{ }} merge-field placeholders, same
convention as the NDA/Intent to Proceed templates.

Deliberately NOT wired to a send-and-sign flow yet (unlike NDA/Intent to
Proceed) - Schedule 2 (Territory) includes a bespoke postcode map image
per franchisee and Schedule 3 (Trade Marks) is specific to whichever
brand (Kid/Teen/People/School) the franchisee is joining, both of which
need a design decision before that can be automated safely. Until then
this is purely an editable reference Ashley can find and update in Desk
- {{ trade_mark_number }}/{{ trade_name }} are left as merge fields too
so the wording is ready to reuse across brands once that flow exists,
but nothing currently renders them.

Idempotent/safe to leave in place if re-run.
"""

import frappe

PRACTICE_DOCUMENT_DOCTYPE = "Practice Document"
FRANCHISE_AGREEMENT_TITLE = "Franchise Agreement"

FRANCHISE_AGREEMENT_TEMPLATE_TEXT = """
<h3>Franchise Agreement</h3>
<p>DATED <strong>{{ agreement_date }}</strong></p>
<p>THE RESILIENT PEOPLE LIMITED and <strong>{{ franchisee_name }}</strong></p>

<p>THIS AGREEMENT is dated <strong>{{ agreement_date }}</strong></p>

<h4>Parties</h4>
<p>(1) THE RESILIENT PEOPLE LIMITED incorporated and registered in England and Wales with
company number 10625898 whose registered office address is at Fox Corner, Chester Road,
Hartford, CW8 1LL (Franchisor);</p>
<p>(2) <strong>{{ franchisee_name }}</strong> of <strong>{{ franchisee_address }}</strong>
(Franchisee).</p>

<h4>Background</h4>
<p>(A) The Franchisor, as a result of practical business experience, has developed a business
of providing a children's wellbeing service (the Services, as further defined below) to both
commercial and non-commercial which is carried on under the name "{{ trade_name }}" (the
Trade Name).</p>
<p>(B) The Franchisor has built up a reputation and goodwill in the Trade Name, which is
associated with high standards of service and it is the registered proprietor of the Trade
Marks under trade mark number {{ trade_mark_number }}.</p>
<p>(C) The Franchisor has developed a system for the establishment, operation and development
of the Business utilising management procedures and methods of marketing and promotion (the
System) which are confidential and which are the exclusive property of the Franchisor.</p>
<p>(D) The Franchisee wishes to acquire from the Franchisor the right and franchise to operate
the Franchisee's Business (as defined below) in the Territory in accordance with the terms of
this Agreement.</p>

<h4>Agreed Terms</h4>

<p><strong>1. Interpretation</strong></p>
<p>1.1 The definitions and rules of interpretation in this clause apply in this Agreement.</p>
<p><strong>Business</strong> - the provision of a children's wellbeing service to both
commercial and non commercial customers;<br>
<strong>Business Day</strong> - a day other than a Saturday, Sunday or public holiday in
England when banks in London are open for business;<br>
<strong>Commencement Date</strong> - <strong>{{ commencement_date }}</strong>;<br>
<strong>Confidential Information</strong> - any information which is disclosed to the
Franchisee by the Franchisor pursuant to, or in connection with, this Agreement (whether
orally or in writing and whether or not such information is expressly stated to be
confidential), or which otherwise comes into the hands of the Franchisee in relation to the
Business, the Franchisee's Business, the System, the Services or the Products other than
information which is already in the public domain (otherwise than as a result of a breach of
any obligation of confidentiality);<br>
<strong>Expiry Date</strong> - <strong>{{ expiry_date }}</strong>;<br>
<strong>Franchisee's Business</strong> - the business operated by the Franchisee within the
Territory in accordance with this Agreement;<br>
<strong>Gross Revenue</strong> - all sums receivable (whether or not actually received or
invoiced) arising directly or indirectly from the conduct of the Franchisee's Business during
each month (and for any period less than a complete month) during the continuance of this
Agreement including all cash and credit transactions of whatever nature and including assumed
gross takings calculated for the purpose of any loss of profits or business interruption
insurance claim, but excluding VAT (if any);<br>
<strong>Initial Fee</strong> - <strong>{{ initial_fee }}</strong>, payable in accordance with
clause 4;<br>
<strong>Intellectual Property</strong> - patents, rights to inventions, copyright and related
rights, trademarks, trade names and domain names, rights in get-up, rights in goodwill or to
sue for passing off, rights in designs, rights in computer software, database rights, rights
in confidential information (including know-how and trade secrets) and any other intellectual
property rights, in each case whether registered or unregistered and including all
applications (or rights to apply) for, and renewals or extensions of, such rights and all
similar or equivalent rights or forms of protection which may, now or in the future, subsist
in any part of the world relating to the Products, Services, Business and the System, owned by
the Franchisor and acquired by the Franchisor from time to time;<br>
<strong>Management Fee</strong> - the amounts set out in Schedule 1, payable in accordance
with clause 4.3;<br>
<strong>Manual</strong> - the Franchisor's standard operating manual detailing the System,
operations and procedures with which the Franchisee will comply in operating the Franchisee's
Business;<br>
<strong>Marketing Fee</strong> - the amount set out in Schedule 1, payable in accordance with
clause 4;<br>
<strong>Materials</strong> - the materials listed in Schedule 4;<br>
<strong>Minimum Performance Criteria</strong> - the minimum performance criteria as described
in clause 4.10 or otherwise set down by the Franchisor in the Manual;<br>
<strong>Products</strong> - the Materials and such other products as shall, from time to time,
be notified in writing by the Franchisor to the Franchisee;<br>
<strong>Services</strong> - the provision of personal children's wellbeing services and any
other services to be used in, or supplied by, the Franchisee's Business as further described
in the Manual;<br>
<strong>Software</strong> - the software listed in the Manual or otherwise notified by the
Franchisor to the Franchisee for use in the Franchisee's Business (for which the Franchisee
shall be obliged to enter into any related contracts for use or licence of the Software and
pay any related fees);<br>
<strong>Stationery</strong> - all letterheads, invoices, order forms, stickers, leaflets,
posters, postcards and other documents approved or provided by the Franchisor from time to
time or as referred to in the Manual to be used by the Franchisee for the purpose of the
Franchisee's Business;<br>
<strong>System</strong> - the business format and method developed and implemented by the
Franchisor in connection with the Business using the Intellectual Property, Confidential
Information, operational procedures, methods, management, marketing and advertising
techniques, part of which are contained in the Manual;<br>
<strong>Term</strong> - three (3) years from the Commencement Date unless extended earlier
determined as provided for by this Agreement;<br>
<strong>Territory</strong> - <strong>{{ territory_description }}</strong>, as set out in
Schedule 2;<br>
<strong>Trade Marks</strong> - the trademarks set out in Schedule 3 and any other trademarks
registered by the Franchisor in relation to the Business from time to time during the Term;
<br>
<strong>Trade Name</strong> - {{ trade_name }};<br>
<strong>VAT</strong> - value added tax chargeable under the Value Added Tax Act 1994 and any
similar replacement or additional tax;<br>
<strong>Website</strong> - the website(s) owned and operated by the Franchisor from time to
time including those with the url www.theresilientacademy.co.uk.</p>
<p>1.2-1.15 Standard interpretation rules apply (headings for convenience only; singular
includes plural; one gender includes the others; references to a party include successors;
references to statute include amendments; "including"/"in particular" are illustrative, not
limiting; an obligation not to do something includes an obligation not to allow it).</p>

<p><strong>2. Rights Granted</strong></p>
<p>2.1 In consideration of the payment of the Initial Fee and the Management Fee by the
Franchisee to the Franchisor in accordance with clause 4, the Franchisor grants to the
Franchisee during the Term, and subject to and in accordance with the provisions of this
Agreement, the right and licence to operate the Franchisee's Business and to provide the
Services in accordance with the System within the Territory.</p>
<p>2.2 Save as otherwise provided for in this Agreement the Franchisor agrees that it will not
itself operate or licence any third party to operate any business involving the provision of
the Services under the Trade Name within the Territory.</p>
<p>2.3 The right and licence granted to the Franchisee to operate the Franchisee's Business
shall extend only to the Territory. The Franchisee agrees that it will not itself use nor will
it permit or authorise any use directly or indirectly of the System or the Brand nor make
available the Services outside the Territory but that if a third party franchisee of the
Franchisor is requested by a potential client to provide the Services under the Name within
the Territory, such third party franchisee may do so provided that they have not marketed
their services within the Territory to such potential client. For the avoidance of doubt, all
other territories (other than the Territory) are expressly reserved to the Franchisor.</p>

<p><strong>3. Term</strong></p>
<p>3.1 This Agreement shall commence on the Commencement Date and shall continue in force for
the Term ending on the Expiry Date (subject to earlier termination in accordance with clause
16) and subject to the Franchisee's right to the grant of the new franchise agreement
contained in clause 3.2.</p>
<p>3.2 The Franchisee may, by notice in writing to the Franchisor given not more than nine (9)
months nor less than six (6) months before the end of the Term, request the grant of a new
agreement (New Agreement) for a further period of five (5) years commencing on the day
following the Expiry Date. The Franchisor shall, by notice in writing to the Franchisee, given
not less than four (4) months before the end of the Term, accept such request if:</p>
<p>3.2.1 at the date of the Franchisor's notice there are no outstanding material breaches by
the Franchisee of this Agreement and there are no grounds on which the Franchisor has a right
to terminate this Agreement under clause 16 and both these conditions are still applicable on
the Expiry Date;</p>
<p>3.2.2 the Franchisee has achieved the Minimum Performance Criteria during the entirety of
the last two (2) years preceding the expiry of the Term;</p>
<p>3.2.3 the Franchisee has at all times performed her obligations under this Agreement to the
reasonable satisfaction of the Franchisor and the Franchisee's Business meets the Franchisor's
requirements;</p>
<p>3.2.4 the Franchisee completes at her own expense such maintenance, replacement and/or
purchase of the Products as the Franchisor considers to be necessary to bring the Franchisee's
Business up to the latest standards required by the Franchisor and to comply with any relevant
statutory or other requirements which apply to the Business and within such period of time as
the Franchisor may reasonably specify;</p>
<p>3.2.5 the Franchisee, and any person employed by or concerned with the Franchisee's
Business, completes such re-training or refresher training at such time and at such place as
the Franchisor may reasonably request at the Franchisee's own expense;</p>
<p>3.2.6 the Franchisee enters into the Franchisor's then current form of franchise agreement
(which may differ substantially from the terms of this Agreement and may contain revised
Minimum Performance Criteria); and</p>
<p>3.2.7 the Franchisee reimburses the Franchisor any reasonable costs incurred by the
Franchisor in granting a new agreement to the Franchisee.</p>
<p>3.3 On the grant of the New Agreement there shall be no obligation on the Franchisee to pay
any sum expressed to be payable by way of initial fee and the Franchisor shall be under no
obligation to perform any of the initial or other obligations contained in the New Agreement
which are appropriate to the establishment of the business of a new franchisee.</p>
<p>3.4 Unless the parties agree otherwise in writing, any renewal under this clause 3 shall be
without prejudice to the rights of the Franchisor outstanding at the end of the Term.</p>
<p>3.5 The Franchisee shall upon the execution of the New Agreement be deemed to have released
and discharged the Franchisor from and against all claims and demands whether or not
contingent which the Franchisee may have against the Franchisor arising from this Agreement or
otherwise in any way out of the relationship between the Franchisor and the Franchisee.</p>
<p>3.6 If the Franchisee continues to carry on the Franchisee's Business after the end of the
Term, but without having entered into a New Agreement with the Franchisor, then she will be
deemed to do so on the terms and conditions of this Agreement, save that either party will be
entitled to terminate this Agreement on giving to the other party one (1) month's written
notice of termination.</p>

<p><strong>4. Fees</strong></p>
<p>4.1 On the date of this Agreement, the Franchisee shall pay the Initial Fee. The Initial Fee
shall cover all the Franchisor's obligations under clause 5.</p>
<p>4.2 The Franchisee shall send to the Franchisor full details of the Gross Revenue in the
preceding month (Gross Revenue Statement) either electronically or by first class mail to be
received by the Franchisor not later than the seventh (7th) day of each month.</p>
<p>4.3 The Franchisee shall pay to the Franchisor the Management Fee by bank transfer so as to
be received by the Franchisor on or before the twentieth (20th) day of the month in respect of
the Gross Revenue in the preceding month together with any and all sums due for the supply of
any Products, together with any underpayments made previously.</p>
<p>4.4 In the event that the Franchisee fails to send the Gross Revenue Statement by the due
date, the Franchisee shall pay to the Franchisor the appropriate Management Fee based on the
Franchisor's best estimate of the Gross Revenue, such estimate to be based on the Gross
Revenue in respect of the previous month. Once the Franchisee has provided to the Franchisor
the Gross Revenue Statement for the month, if there is any discrepancy between the amount of
Management Fee paid (as set out above) and the amount duly payable, then: (a) if the amount of
Management Fee paid is less than the amount due from the Franchisee, the Franchisee shall
immediately on request pay the difference of such amount to the Franchisor; or (b) if the
amount of Management Fee paid is more than the amount due from the Franchisee, the Franchisor
shall be entitled to set off the excess amount against any sums outstanding (or future sums
due) from the Franchisee.</p>
<p>4.5 In the event that any sums due to the Franchisor are not paid on the due date, such sums
shall bear interest calculated at the rate of two per cent (2%) per month or part of a month
for which there is any sum due but not paid before as well as after judgement.</p>
<p>4.6 In the event of any default in payment on the due date the Franchisor may, in addition
to all other remedies available to the Franchisor, suspend the provision of all goods and
services, until payment is made.</p>
<p>4.7 Unless the Franchisor otherwise notifies the Franchisee in writing, the Franchisee shall
make all payments by bank transfer to the Franchisor's nominated bank account.</p>
<p>4.8 All fees due under this Agreement are exclusive of VAT, which shall, where applicable,
be paid by the Franchisee at the prevailing rate on the due date for payment or receipt of the
relevant invoice from the Franchisor (as may be).</p>
<p>4.9 The Franchisee shall be responsible for the prompt and complete payment of all invoices
due to third party suppliers.</p>
<p>4.10 From the first (1st) anniversary of the Commencement Date, the Franchisee shall achieve
a minimum monthly Gross Revenue of £1000 or 60% of the Franchisee's average Gross Revenue for
the previous twelve months (whichever is the higher) (Minimum Performance Criteria). In
subsequent years turnover must increase by 10% per annum. If the Franchisee fails to meet the
Minimum Performance Criteria in three (3) or more successive months after the first (1st)
anniversary of the Commencement Date, the Franchisor shall be entitled to: (a) require the
Franchisee to take such steps as the Franchisor shall in its sole discretion deem necessary to
assist the Franchisee to meet the Minimum Performance Criteria; or (b) adjust the boundaries
of the Territory and/or remove the Franchisee's exclusivity within the Territory; or (c)
terminate this Agreement in accordance with the provisions of clause 16.1.8.</p>
<p>4.11 Notwithstanding the provisions set out in this clause 4 (and not more than once in
every twelve (12) month period) the Franchisee shall be entitled to serve four (4) weeks
written notice on the Franchisor that the Franchisee intends to take up to two (2) weeks
leave and the Franchisor agrees that the Franchisee shall be entitled to deduct from the
Management Fee due in respect of the month such leave was taken (or months if the period of
leave extends over two (2) months) that proportion of the Management Fee representing two (2)
weeks work.</p>

<p><strong>5. Franchisor's Initial Obligations</strong><br>
In order to assist the Franchisee in opening for business, the Franchisor shall provide: a
copy of the Manual (on loan); a webpage relating to the Franchisee's Business on the Website;
an email address for the purposes of the Franchisee's Business; the Materials; the initial
training as set out in clause 8 and Schedule 4; and general advice on how to set up the
Franchisee's Business and initial marketing assistance.</p>

<p><strong>6. Franchisor's Continuing Obligations</strong><br>
The Franchisor shall at all times during the Term: provide the Franchisee with know-how,
advice and guidance relating to the operation of the Franchisee's Business (chargeable where
substantial or continual additional support is required); develop the System and update the
Manual from time to time and inform the Franchisee of all such updates; host, maintain and
update the Website and the Franchisee's Webpage as the Franchisor thinks fit; and assist the
Franchisee in procuring such goods and services as are necessary for the purposes of the
Franchisee's Business.</p>

<p><strong>7. Franchisee's Obligations</strong></p>
<p>7.1 The Franchisee shall undertake the initial training as detailed in clause 8 and shall
begin operating the Franchisee's Business within two (2) weeks following the completion of
initial training, which shall be no later than three (3) months from the date of this
Agreement, unless otherwise agreed with the Franchisor.</p>
<p>7.2 The Franchisee must, at their own expense and prior to the commencement date of this
agreement, apply for and provide satisfactory clearance from the Disclosure and Barring
Service. In addition the Franchisee will sign up to the DBS update service. If, during the
Term of this agreement the Franchisee receives a conviction, caution, reprimand or final
warning from the police this must be disclosed to the Franchisor within forty eight (48)
hours.</p>
<p>7.3 The Franchisee shall at all times during the Term, in relation to the Franchisee's
Business: pay all fees and payments due to the Franchisor in accordance with this Agreement
and the Manual; take delivery of the Materials; purchase and maintain sufficient minimum stock
of the Materials; operate the Franchisee's Business strictly in accordance with the Manual and
not do anything that could damage the reputation of the Business, the Franchisee's Business or
the Intellectual Property; submit the Gross Revenue Statement and other required reports;
comply with all advice and reasonable instructions of the Franchisor; not offer or advertise
promotions affecting other franchisees outside the Territory except in accordance with clause
10; use her best endeavours to promote and extend the Franchisee's Business within the
Territory; maintain and comply with all necessary licences, consents and legislation; use her
best endeavours to protect and promote the goodwill in the Business; display the required
franchise-operated-under-licence wording on stationery, emails and correspondence; trade at
all times under the Permitted Name; adhere to the Manual's branding guidelines; only use the
email address provided by the Franchisor; procure and maintain a suitable computer and
approved Software; comply with the Franchisor's internet/social media policies; keep the
Franchisee's webpage information up to date; only use approved Stationery and marketing
materials; supply the Services only on the Manual's standard terms and conditions; comply with
ordering, invoicing and accounting procedures; maintain adequate working capital; not offer
credit without written consent; pay third party suppliers promptly; not factor or charge the
Franchisee's Business's debts without consent; not licence any other person to operate the
Franchisee's Business under the Trade Name; promptly report improvements, modifications and
business opportunities; supply information the Franchisor requires about the Franchisee's
Business; introduce requested improvements; assist potential franchisees when asked; attach
required notices to stationery/advertising/other items; provide competent, sober, courteous
and professionally presented service; maintain a customer database in line with the Manual and
the Data Protection Act 2018 and allow the Franchisor to access updates to it; notify the
Franchisor of complaints immediately and handle them per the Manual; permit the Franchisor to
inspect books and records and to contact customers; maintain a dedicated business landline
with call divert; and attend meetings/conferences reasonably requested, at her own cost.</p>

<p><strong>8. Training</strong></p>
<p>8.1 The Franchisor shall provide the Franchisee initial training in the operation of the
System and in all aspects of the Business, at the Franchisor's head office or another
specified location, lasting at least three (3) days.</p>
<p>8.2 The initial training shall cover the provision of the Services, basics of running a
business including record keeping, business planning, bookkeeping, use and representation of
the Brand, and such other matters as the Franchisor considers necessary.</p>
<p>8.3 The Franchisee shall not start the Franchisee's Business until she has, in the
Franchisor's reasonable opinion, successfully completed the initial training, and shall not
allow any employee or sub-contractor to run classes without the Franchisor's prior written
consent (who may require completion of an initial training programme at the Franchisee's
cost).</p>
<p>8.4 If on completion of the initial training the Franchisor reasonably believes the
Franchisee does not meet the minimum standards required, the Franchisor may terminate this
Agreement immediately by written notice (with the Initial Fee refunded less reasonable
appointment/training costs).</p>
<p>8.5 The Franchisee (and staff) shall attend further training reasonably required by the
Franchisor, up to a maximum of five (5) days per year.</p>
<p>8.6 Training is provided at the Franchisor's standard rates as referred to in the Manual, or
otherwise at the Franchisee's cost; the Franchisee is responsible for accommodation, travel,
subsistence and staff salaries/training costs incurred in attending.</p>

<p><strong>9. Accounting Records</strong><br>
The Franchisee shall keep complete and accurate accounts and records in a form approved by the
Franchisor (audited by nominated auditors if required); retain records for at least six (6)
years after the relevant accounting year; and supply copies of accounts, records, VAT returns
and other financial/fiscal information reasonably requested during the Term and for six (6)
years after termination.</p>

<p><strong>10. Advertising</strong><br>
The Franchisor shall promote the Trade Name and Business as it thinks fit and provide
promotional literature at its discretion. The Franchisee shall promote and advertise the
Franchisee's Business in the Territory in accordance with the Manual using materials supplied
by the Franchisor, and co-operate with any special promotion or advertising campaign the
Franchisor requires.</p>

<p><strong>11. Insurance</strong><br>
The Franchisee shall take out and maintain an all-risk insurance policy (including employer's
liability) with cover as specified by the Franchisor in the Manual, not breach such policies,
provide the Franchisor with copies of policies and renewals, and promptly pay premiums and
evidence payment. If the Franchisee fails to do so, the Franchisor may take out such policies
and recover the cost from the Franchisee.</p>

<p><strong>12. Intellectual Property</strong><br>
The Franchisor warrants it is not aware of any reason it might not be entitled to license the
Intellectual Property. The Franchisee shall use the Intellectual Property only as prescribed
in this Agreement or the Manual, acknowledges she has no right, title or interest in it beyond
what is set out here, and that any goodwill in the Trade Marks vests in the Franchisor. She
shall immediately report any threatened or actual infringement, not apply to register any of
the Intellectual Property in her own name, comply with the Manual's requirements on use of the
™/©/® symbols, assist with Trade Mark registration, not license the Intellectual Property to
anyone else, not use anything confusingly similar to it, not do anything that may adversely
affect it, and immediately stop using any advertising/promotional material/packaging on the
Franchisor's request. The Manual's Intellectual Property remains the Franchisor's exclusive
property and shall be safely kept and returned or destroyed on termination.</p>

<p><strong>13. Sale of Business</strong><br>
The Franchisee may not assign this Agreement but may sell the Franchisee's Business with the
Franchisor's prior written consent, subject to conditions including: the buyer meeting the
Franchisor's standards; a bona fide arms-length written offer; payment of the Transfer Fee
(Schedule 1) plus the Franchisor's legal costs (capped at £1,750 plus VAT); and the Franchisee
not being in breach at the time of application. The Franchisor has a 28-day option to purchase
the Franchisee's Business itself on the same terms as any proposed buyer; if not exercised and
consent is given, the Franchisee may proceed with the sale within three (3) months on those
same terms, following the Manual's sale procedures.</p>

<p><strong>14. Death or Incapacity</strong><br>
If the Franchisee dies during the Term, her personal representatives shall inform the
Franchisor within seven (7) days; subject to approval, a family member or friend may continue
operating the Franchisee's Business, or it may be sold within three (3) months under clause
13's procedure. If the Franchisee dies or is materially unable to operate the Business for
more than 28 consecutive days (or 90 days in any 6 months), the Franchisor may appoint a
manager, with the Franchisee paying 115% of the manager's cost.</p>

<p><strong>15. Confidentiality</strong><br>
The Franchisee shall not copy, use or disclose any Confidential Information except as
permitted by this Agreement, save where required by law, court order or regulator, and shall
use it only to perform her obligations under this Agreement.</p>

<p><strong>16. Termination</strong><br>
The Franchisor may terminate this Agreement with immediate effect by written notice for a wide
range of reasons including (without limitation): jeopardising the Trade Marks; unauthorised
assignment; false or misleading information; ceasing or suspending the Franchisee's Business;
disclosing the Manual or Confidential Information in breach of this Agreement; incapacity as
defined in clause 14.2; failing initial training; failing the Minimum Performance Criteria;
insolvency-related events; failing to obtain DBS clearance or a conviction other than a road
traffic offence; failing to pay sums due, or to obtain a required consent and remedy that
within 7 days of notice; persistent unresolved valid complaints; any other remediable breach
not remedied within 28 days of notice; or repeated breaches inconsistent with an intention or
ability to perform this Agreement. Breach of clause 7, 12, 13 or 15 is deemed material for
this purpose.</p>

<p><strong>17. Consequences of Termination</strong><br>
Clauses 12, 15, 17, 18, 18.1, 21, 22, 24 and 29 (etc.) survive termination. Termination does
not affect accrued rights/liabilities. On termination the Franchisee shall: pay all sums due
with interest; cease operating the Business/System and trading under the Trade Marks; stop
using the Intellectual Property and co-operate with removing her name from trade mark
registries; pass on enquiries and full customer details to the Franchisor; return or (at the
Franchisor's option) destroy the Manual and any Trade-Marked Products/materials; pay her
business debts; and assign to the Franchisor any domain names and website content used in the
Franchisee's Business. If she fails to do so within a reasonable time, the Franchisor may, at
her expense, enter the premises and take whatever steps it thinks fit to fulfil the outstanding
obligations.</p>

<p><strong>18. Restrictions</strong><br>
During this Agreement and for one (1) year after termination, the Franchisee shall not (other
than as a holder of up to 5% of a publicly quoted company's shares), directly or indirectly:
be engaged, interested or concerned in the Services (or similar services, or a competing
business) within the Territory or within any other franchisee's territory or the Franchisor's
own; without prior written consent, employ or seek to employ anyone who was a franchisee,
senior manager or senior employee of the Franchisor or another franchisee/licensee within the
previous 12 months; solicit or seek to divert former Customers (from the previous 12 months);
or use the customer database for anything other than the Franchisee's Business. These
restrictions are agreed to be reasonable and valid, are severable if found void in part, and
survive termination as to use of trade secrets/confidential information indefinitely.</p>

<p><strong>19. Indemnity</strong><br>
The Franchisee shall indemnify the Franchisor against all liabilities, costs, expenses,
damages and losses arising out of or in connection with the Franchisee's breach or negligent
performance or non-performance of this Agreement.</p>

<p><strong>20. Entire Agreement</strong><br>
This Agreement, the Manual and any documents referred to in it constitute the whole agreement
between the parties, superseding any prior arrangement relating to the same subject matter. If
inconsistent with the Manual, this Agreement prevails. Neither party relies on any
representation not expressly set out here; remedies for any representation are solely for
breach of contract; nothing limits liability for fraud.</p>

<p><strong>21. Further Assurance</strong><br>
The Franchisee shall use reasonable endeavours to procure that any necessary third party
promptly executes documents and performs acts the Franchisor reasonably requires to give full
effect to this Agreement.</p>

<p><strong>22. Data Protection</strong><br>
The Franchisee shall, in relation to personal data processed in connection with this Agreement
(Franchise Data): register data processing activities with the ICO before commencing
operation; process Franchise Data in accordance with all data protection laws including UK
GDPR; process it only so far as necessary to perform her obligations; restrict disclosure to
employees/third parties under equivalent contractual obligations; and assist the Franchisor
with its own obligations, including subject access requests, promptly informing the Franchisor
of any it receives, not responding without the Franchisor's consent, and informing individuals
their data may be retained/transferred to the Franchisor on termination. Where acting as a
data processor, the Franchisee shall maintain appropriate security measures and only process
Franchise Data on the Franchisor's written instructions. The Franchisee shall indemnify the
Franchisor for claims arising from her unauthorised or unlawful processing, and consents to
disclosure of her personal data to the British Franchise Association and other third parties
the Franchisor determines, and shall comply with data protection laws in any territory she
operates in or is based in.</p>

<p><strong>23. Assignment by Franchisor</strong><br>
The Franchisor may assign, transfer, mortgage, charge or otherwise deal with its rights and
obligations under this Agreement at any time; on assignment it shall procure the assignee
covenants directly with the Franchisee to perform the Franchisor's obligations.</p>

<p><strong>24. Third Party Rights</strong><br>
No one who is not a party has rights under the Contracts (Rights of Third Parties) Act 1999
except as expressly granted, without affecting any other right or remedy available apart from
that Act. Termination, rescission, variation, waiver or settlement do not require any
non-party's consent.</p>

<p><strong>25. No Partnership or Agency</strong><br>
Nothing in this Agreement creates a partnership, joint venture or agency relationship between
the parties, except as expressly provided in clause 13.</p>

<p><strong>26. Joint Franchisees</strong><br>
Where the Franchisee is two or more individuals or a partnership, their covenants are joint
and several.</p>

<p><strong>27. Force Majeure</strong><br>
Neither party is responsible for delay or non-performance due to causes beyond its reasonable
control, provided it promptly notifies the other party and takes all reasonable steps to
comply as fully and promptly as possible.</p>

<p><strong>28. Set-Off</strong><br>
All amounts due from the Franchisee shall be paid in full without deduction, set-off or
counterclaim other than as required by law. The Franchisor may set off any liability of the
Franchisee against any liability it owes the Franchisee, present or future, without prejudice
to its other rights or remedies.</p>

<p><strong>29. Severance</strong><br>
If any provision (or part) is found invalid, unenforceable or illegal, it shall be deemed
deleted to the extent required without affecting the rest of this Agreement (unless doing so
would frustrate its purpose), and shall apply with the minimum modification necessary to make
it valid, giving effect as closely as possible to the parties' commercial intention.</p>

<p><strong>30. Variation</strong><br>
No variation of this Agreement is effective unless in writing and signed by the parties (or
their authorised representatives).</p>

<p><strong>31. Waiver</strong><br>
No failure or delay in exercising any right or remedy shall constitute a waiver of it, nor
preclude or restrict its further exercise, nor that of any other right or remedy.</p>

<p><strong>32. Compliance With Legislation</strong><br>
The Franchisor may amend this Agreement as it reasonably deems necessary to remain compatible
with any relevant block exemption or other law affecting its legality or enforceability,
notifying the Franchisee in writing (with reasons, on advice from a qualified solicitor or
barrister) and requesting her agreement; if she does not confirm agreement within 28 days,
the amendment is deemed incorporated regardless.</p>

<p><strong>33. Counterparts</strong><br>
This Agreement may be executed in counterparts, each an original, together constituting the
same agreement.</p>

<p><strong>34. Governing Law and Jurisdiction</strong><br>
This Agreement (and any dispute or claim arising out of or in connection with it, including
non-contractual disputes) is governed by the law of England and Wales, and the courts of
England and Wales have exclusive jurisdiction over any such dispute or claim.</p>

<p>This Agreement has been entered into on the date stated at the beginning of it.</p>

<table style="width:100%;">
<tr>
<td style="width:50%;vertical-align:top;padding-right:20px;">
<p style="font-style:italic;font-size:22px;">{{ franchisee_signature }}</p>
<p>Signature</p>
<p>{{ franchisee_name }}</p>
<p>Name</p>
<p>{{ franchisee_date }}</p>
<p>Date</p>
</td>
<td style="width:50%;vertical-align:top;">
<p style="font-style:italic;font-size:22px;">AJC</p>
<p>Signature</p>
<p>Ashley Costello</p>
<p>Name</p>
<p>{{ agreement_date }}</p>
<p>Date</p>
</td>
</tr>
</table>

<h4>Schedule 1 - Fees</h4>
<p><strong>Initial Fee:</strong> {{ initial_fee }} (less any deposit paid)<br>
<strong>Management Fee:</strong> Up to £1,500 Gross Revenue: 10%. Between £1,500-£2,999: 8%.
£3,000+: 7%.<br>
<strong>Marketing Fee:</strong> 2% of gross monthly revenue.<br>
<strong>Transfer Fee:</strong> as set by the Franchisor from time to time (all fees exclusive
of VAT, which is also charged).<br>
<strong>Commencement Date:</strong> {{ commencement_date }}<br>
<strong>Expiry Date:</strong> {{ expiry_date }}<br>
<strong>Permitted Name:</strong> {{ permitted_name }}<br>
<strong>Permitted Name ("{{ trade_name }} (area)"):</strong> {{ permitted_area }}</p>

<h4>Schedule 2 - The Territory</h4>
<p>{{ territory_description }}</p>
<p class="dashboard-help">The postcode map graphic for this franchisee's Territory is bespoke
per deal - attach/insert it here directly in Desk before sending, it isn't generated
automatically yet.</p>

<h4>Schedule 3 - The Trade Marks</h4>
<p>Trade Mark #{{ trade_mark_number }}<br>
Mark text: {{ trade_name }} (area)<br>
Registered to: The Resilient People Limited, Fox Corner, Chester Road, Hartford, CW8 1LL</p>
<p class="dashboard-help">Adjust the trade mark details above to match whichever brand
(Kid/Teen/People/School) this franchisee is joining before sending.</p>

<h4>Schedule 4 - Materials</h4>
<ul>
<li>Polo shirt or T-shirt</li>
<li>Soft shell jacket or Fleece or Body Warmer</li>
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
<p>The Franchisee acknowledges that she has been advised to seek her own independent legal and
financial advice prior to entering into this Agreement.</p>
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
