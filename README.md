# trk-dashboard

**The Resilient Dashboard** - the operational back office for The Resilient Kid / Teen / People / School, a children's wellbeing coaching franchise business. It's a single [Frappe](https://frappeframework.com/) app providing role-scoped dashboards for the franchise owner (Ashley/HQ), franchised coaches, their session workers, a store manager, and a set of guest-facing (no-login) web pages for leads, prospective franchisees/session workers, prospective schools, and online shoppers.

Underneath the dashboards is a large, shared Python API layer (`dashboard/api/shared/`) that runs the whole business end to end: client intake and bookings, calendar/Google Meet scheduling, invoicing (via ERPNext), a compliance document library, a coach onboarding journey, LMS course access, a franchise/session-worker recruitment pipeline, a school partnership pipeline, an online store, automated nurture emails, and a general-purpose notifications system.

This is one of five related Frappe/web apps in the business's stack, all living as sibling checkouts:

| App | What it is |
|---|---|
| **trk-dashboard** (this repo) | The main backend + the Coach/Franchisor/Session Worker/Store dashboards |
| `coach_calendar_sync` | Syncs coaches' Google Calendar/Meet into the `Event` doctype this app reads |
| `client_portal` | The client-facing login portal |
| `resilient_domains` | The public, unauthenticated marketing/brand websites (coach profiles, public booking, blog) |
| `school_dashboard` | The school-partner portal (reads the Knowledge Vault/organisation data this app manages) |

Only relationships that are actually verifiable in this repo's code are described below - see the **Sibling apps** section.

## Who uses it, and where

Which dashboard a logged-in user lands on is decided purely from their own record (`dashboard/api/shared/permissions.py`, `get_current_user_dashboard_type()`), not a role field anyone sets by hand:

| User | Dashboard type | Route | Resolved by |
|---|---|---|---|
| Ashley / HQ / office | `franchisor` | `/franchisor_db` | user is in the hardcoded `FRANCHISOR_USERS` set (`ashley@`, `office@`, `hq@theresilientkid.co.uk`) |
| A franchised coach | `coach` | `/coach_db` | a `Coach` record links to that user |
| A coach's session worker | `session_worker` | `/session_worker_db` | a `Session Worker` record links to that user |
| The merch store manager (Rachel) | `store` | `/store_db` | an enabled `Store Manager` record links to that user |
| Everyone else / not logged in | `unknown` | blocked | - |

Every dashboard-area `www` page calls `redirect_if_wrong_dashboard(expected)` on load, which bounces a logged-in user to *their own* dashboard if they land on the wrong one, and blocks Guests outright. A franchisor can also reach `/store_db` directly without first visiting `/franchisor_db`.

The three staff dashboards are **not** feature-identical:

- **Shared by all three (Coach/Session Worker/Franchisor)**: calendar, clients, contacts, Practice Documents, notifications, profile, reports (including the "Forms" section).
- **Coach + Franchisor only**: invoices, the Client Lead pipeline, onboarding, link-click tracking (`/l`), session-worker management, supervision booking.
- **Franchisor only**: coach roster, Item Access, statements, the School Pipeline, Recruitment Leads, the Knowledge Vault, School Licenses, and Coach Store stock/pack-compliance reporting.
- **Store (`/store_db`)**: its own, narrower world - product catalog, coupons, orders/fulfilment, shipping settings, stock take. A `Store Manager` can't reach anything outside it.

Outside the four logged-in dashboards, a family of standalone, unauthenticated `www` pages carries the rest of the public-facing business: `/franchisee-nda`, `/franchisee-intent`, `/franchisee-intake`, `/franchisee-contract`, `/recruitment-nda`, `/recruitment-intent`, `/recruitment-intake`, `/recruitment-contract`, `/recruitment-fees-guide`, `/session-worker-fees-guide`, `/transfer_sign` (client-transfer e-signing), and `/l` (the short-link click-tracker used in outgoing emails).

## What this app actually does

### Clients, bookings & calendar
- Client, contact, and appointment management; `calendar.py` (the single largest module in the app) drives the booking calendar, slot computation, and session logic shared by staff booking, public guest booking (`public_booking.py`), and staff-to-staff supervision booking (`supervision_booking.py`).
- `packages.py` maintains each client's Client Package Balance (sessions remaining on a pack) as a background-job port of a former synchronous Server Script, specifically to avoid lock contention on busy booking days.
- `pending_bookings.py` + `booking_confirmations.py` queue bookings that hit a MySQL naming-series lock, retry them, and send confirmation/reminder emails (including a 1-hour-before online-session reminder) on a 5-minute scheduler sweep.
- Real UK postcode-district boundary data (`postcode_boundaries.py`, bundled GeoJSON) powers the Client Locations territory map.

### Google Calendar / Meet integration
This app never calls the Google API itself. `coach_calendar_sync` (sibling repo) owns that integration and writes `custom_google_event_id` / `custom_google_meet_url` fields onto the core `Event` doctype; `calendar.py` simply reads those fields when displaying an appointment's Meet link.

### Leads, recruitment & franchise pipeline
- `leads.py` (the largest module in the app) runs the **Client Lead** pipeline - ordinary enquiries, intake-form sync, and the original franchise-prospect/session-worker recruitment flow (Stage 1 pipeline, NDA/Intent-to-Proceed/Franchise Agreement e-signing, Safer Recruitment Checklist, fees guide, conversion to a real Coach/Session Worker).
- `recruitment_leads.py` is a **phase-1, purely additive migration** of that same recruitment flow onto its own `Recruitment Lead` doctype (separate from ordinary Client Leads), deliberately mirroring `leads.py`'s behaviour function-for-function so the move can happen without touching the original.
- `franchise_brochure.py` and `franchise_info_sheet.py` handle the lightest-touch top of the funnel - brochure requests (gated link + token) and the Franchise Information Sheet, both feeding into the lead pipeline above.
- `webshop_lead_sync.py` bridges a `webshop` "Contact Us" enquiry (a plain core `Lead`) into the Client Lead board.
- `client_transfers.py` runs the three-way sign-off (transferring coach / receiving coach / franchisor) when a client moves between coaches, including a transfer fee invoice.

### School partnership pipeline
`school_pipeline.py` runs franchisor-only outreach to prospective schools: `School` records (deliberately separate from `Client` until a school actually buys something), repeatable `School Sequence` campaigns via per-run `School Sequence Enrollment` records, weekly automated sends (one combined email per step, To the Head contact, Cc everyone else, always from `office@`), and inbound-reply detection via Frappe's own Communication threading. `school_licenses.py` is the franchisor-facing admin for granting a school's `Client` record School Dashboard portal access (by setting fields on the linked `Customer`/"Portal Organisation" that `client_portal` owns).

### Knowledge Vault
`knowledge_vault.py` lets Ashley/office build a library of training videos/PDFs/documents for school staff, scoped per school ("allocated schools") and further narrowed by staff Role/Year Group, with a school's own Primary Contact able to grant or exclude specific staff. `school_dashboard` is the actual consumer of this data for school staff logins.

### Invoicing & payments (ERPNext)
`invoices.py` and `payment_utils.py` build real ERPNext Sales Invoices, Payment Entries and GL Entries - this is a **hard dependency on ERPNext**, not merely a soft integration (`payment_utils.py` imports `erpnext.accounts.doctype.payment_entry.payment_entry.get_payment_entry` directly), even though ERPNext isn't currently declared in `pyproject.toml`'s bench dependencies. `course_unlock_on_payment.py` hooks `Payment Entry.on_submit` to unlock a linked LMS course and grant `client_portal` access the moment an invoice is actually *paid* (not merely raised).

### Compliance - Practice Documents
`practice_documents.py` is the policy/compliance document library: assigning documents to coaches/session workers, tracking requirement status/due dates, brand-based auto-assignment (ticking a document's Brand Access grants it to every coach on that brand, and vice versa when a coach's own brand changes), and sharing documents with clients (`Client Document Share`).

### Coach Onboarding Journey
`onboarding.py` instantiates a master-step template (`Coach Onboarding Master Step`) per coach as `Coach Onboarding Step` rows the moment `start_onboarding` is ticked, with LMS course/chapter/lesson links, dependency locking, and live syncing - editing a master step (even unticking it Active) propagates to every coach already on that journey.

### LMS (Frappe Learning) integration
Course/lesson content lives in the separate Frappe Learning app, but this app controls who can see which `LMS Course`: `lms_access.py` adds `has_permission`/`permission_query_conditions` hooks (Frappe Learning defines neither for `LMS Course` itself) *and* uses `override_whitelisted_methods` to replace Learning's own `get_course_details`/`get_course_outline`/`get_courses`/`get_course_count`/`get_course_categories` whitelisted methods outright - necessary because those call `frappe.get_all()` internally, which always ignores permission hooks. `lms_certificates.py` blocks certificate issuance before a course is actually complete. `store_products.py` keeps a purchasable `Item` in sync with a paid course so it can share a cart with physical store products.

### Online store / webshop
- `webshop_purchase.py` is guest checkout (no login required) for one-off purchases - Stripe-based, deliberately separate from the stock Frappe `webshop` app (whose checkout hard-requires login). Every purchase lands on a real `Client`, not a separate silo.
- `store_products.py`, `store_coupons.py`, `store_orders.py`, `store_shipping.py`, `store_stock.py` are the Store Manager-facing dashboard: product/stock catalog management, discount codes, order fulfilment (Paid → Packed → Shipped), weight-based shipping, and keeping `Item.custom_stock_qty` honest against every Sales Invoice.
- `coach_stock.py` is a *separate* concept - per-coach Kid/Teen Pack stock tracking (a coach's own Coach Store orders feed an add-only ledger) and pack-handover compliance reporting, distinct from the store's single company-warehouse stock count.
- `item_access.py` is the franchisor-only grid controlling which coaches can invoice/sell which `Item`s and which are shown publicly on a coach's profile (on `resilient_domains`).

### Email - templates, nurture sequences & deliverability
- `email_templates.py` wraps Frappe's Email Template doctype so wording for transactional emails (booking confirmations, intake invites, etc.) is editable from the Desk without a code change.
- `email_sequences.py` is a generic nurture/drip engine: a wildcard `after_insert` hook on every doctype (`"*"`) enrols a new document in any active `Email Sequence` whose trigger matches, and a daily scheduler job sends/advances whichever step is next due - a new campaign needs only a Desk record, no code change.
- `mail_throttle.send_email()` is the drop-in `frappe.sendmail()` replacement used everywhere in this app (and imported cross-app by `resilient_domains`/`client_portal`), because the office inbox is capped at 50 emails/hour on its current email plan.
- `mailerlite_sync.py` is a one-directional-for-signups, two-directional-for-unsubscribes sync between Frappe Email Groups and MailerLite, which remains the actual newsletter-sending tool.

### Notifications & search
`notifications.py` implements an in-app messaging/notification system (`Dashboard Conversation` + messages + recipients, layered over Frappe's own `Notification Log`), with reply support (`TRK Notification Reply`) and orphaned-recipient cleanup. `global_search.py` and `directory.py` back the topbar's global search and name-lookup.

### Forms / Reports section
`form_reports.py` auto-discovers every DocType in the site's **"Forms"** module (bespoke Desk-built feedback/survey/consent/assessment forms - wellbeing scales, school questionnaires, CPD booking/feedback, media consent, etc.) from Frappe's own DocType metadata rather than a hardcoded list, and surfaces them as read-only summaries in each dashboard's Reports section, scoped the same way every other list is (coaches see their own, franchisors see everyone's). `Form Visibility Rule` and per-Web-Form "Show in Dashboard Reports"/"Also Show to Coaches" fields control what shows where. Several of these forms (Stirling Wellbeing Scale, care-languages quiz, school experience, staff relationships) have their own scoring logic as `validate` hooks in small, dedicated modules (`wellbeing_forms.py`, `care_language_form.py`, `school_experience_form.py`, `staff_relationships_form.py`).

### Guest/public-facing flows
`public_booking.py` (no-login appointment booking, consumed by `resilient_domains`), `webshop_purchase.py` (guest checkout), and the standalone NDA/intent/intake/contract/fees-guide `www` pages listed above cover everything a non-logged-in prospect, franchisee, session worker or client needs to do before they ever get a dashboard login.

## Sibling apps - verified relationships

Only dependencies this repo's own code demonstrates are listed here:

- **`coach_calendar_sync`** - this app reads (never writes) `custom_google_event_id`/`custom_google_meet_url` custom fields on the core `Event` doctype that `coach_calendar_sync` populates from Google Calendar/Meet (`dashboard/api/shared/calendar.py`).
- **ERPNext** - a hard runtime dependency for invoicing: `payment_utils.py` imports `erpnext.accounts.doctype.payment_entry.payment_entry.get_payment_entry` directly.
- **Frappe Learning (LMS)** - this app adds permission hooks and `override_whitelisted_methods` entries targeting `lms.lms.utils.*` (`lms_access.py`), and a `validate` hook on `LMS Certificate` (`lms_certificates.py`). Course/lesson content itself lives in that app.
- **`webshop`** (the stock Frappe app) - its "Contact Us" Lead doctype is bridged into the Client Lead board (`webshop_lead_sync.py`); its payment doctypes are reused for one-off purchases.
- **`trk_session_worker_dashboard`** - an older, separate predecessor app still imported directly from `dashboard/api/session_worker/change_requests.py` (`from trk_session_worker_dashboard.api.change_requests import ...`) for change-request handling.
- **`client_portal`** - this app never imports its Python code; it reads/writes the same shared doctypes on one site instead (e.g. `Client Contact Link` rows that gate client-portal login, managed here via `portal_access.py`; `Customer`'s "Portal Organisation" fields, managed here via `school_licenses.py`). Several modules' docstrings explicitly note this deliberate one-site-shared-doctypes-not-shared-code boundary.
- **`resilient_domains`** - the public brand sites (coach profiles, public booking widget, blog) consume this app's guest-facing endpoints (`public_booking.py`, `webshop_purchase.py`) and this app's `item_access.py`/`Show on Site` settings decide what those sites display; `mail_throttle.send_email()` is imported cross-app from there.
- **`school_dashboard`** - the school-partner portal; the Knowledge Vault (`knowledge_vault.py`) and School License (`school_licenses.py`) data this app manages is what it ultimately reads, via the same shared-doctype pattern as `client_portal`.
- **Stripe** - a declared Python dependency (`pyproject.toml`), used for guest checkout, the Store, per-coach Stripe Connect settings, and webshop payments generally.
- **MailerLite** - the external newsletter tool kept in sync via `mailerlite_sync.py`.

## Architectural patterns worth knowing

- **`override_whitelisted_methods`** (`hooks.py` + `lms_access.py`): when a dependency's own whitelisted method bypasses Frappe's permission layer (here, Frappe Learning's `get_courses`/`get_course_count` etc. call `frappe.get_all()`, which ignores permission hooks entirely), this app registers a full replacement for that exact dotted method path rather than trying to patch around it.
- **Forms-module auto-discovery** (`form_reports.py`): rather than hardcoding every bespoke feedback/assessment form DocType into the Reports section, it's discovered live from DocType metadata (any DocType in the "Forms" module), so a new Desk-built form just needs to exist in that module to show up - no code change.
- **Wildcard doc-event hooks**: `email_sequences.check_sequence_triggers` is registered on `"*"` in `hooks.py`'s `doc_events`, firing on every new document site-wide, deliberately, so a new nurture sequence is a pure data change (an `Email Sequence` record) rather than a code change.
- **`patches.txt` as a project history**: with ~190 entries, it's a genuinely useful index of everything this app has grown into over time - onboarding-journey restructuring, every bespoke web form added, the School/Recruitment/Knowledge-Vault/Store builds, and a trail of targeted data-backfill patches. Worth skimming when exploring an unfamiliar feature's origin.
- **`after_migrate` vs `patches.txt`**: a few idempotent setup functions (`create_store_manager_for_rachel_v2`, `add_item_gallery_field`, `add_coach_recognition_field`) run from `hooks.py`'s `after_migrate` instead of `patches.txt`, specifically because they depend on a doctype that's only guaranteed to exist after the *same* deploy's schema sync - `patches.txt` entries run before doctype sync.
- **Shared-doctype, not shared-code, app boundary**: this app never imports Python from `client_portal`, `resilient_domains`, or `school_dashboard` (confirmed by `grep`) - every cross-app relationship with those three is through core/custom doctypes they all read/write on the same Frappe site. The one real Python cross-app import going *the other way* is `mail_throttle.send_email()`, pulled in by the other apps.
- **Core-doctype hooks for apps this repo doesn't own**: `LMS Certificate`, `LMS Course`, `LMS Enrollment`, `Blog Post`, `Email Group Member`, `Item`, `Sales Invoice`, `Payment Entry` and `Coach`/`Session Worker` (the last two defined in this app's own fixtures-adjacent setup, not its `doctype/` folder) all get `doc_events` hooks here even though their controllers live elsewhere - Frappe runs every installed app's hooks for a doctype alongside its own.
- **Background jobs over synchronous save-time work**: `packages.py`'s balance recalculation and `calendar.share_event_with_admins` both moved off the request thread specifically to avoid holding Frappe's Event naming-series lock during a busy save.

## Custom DocTypes (`dashboard/dashboard/doctype/`)

- **Client Lead** / **Client Lead Note** - the original Client Lead pipeline (ordinary enquiries + franchise/session-worker recruitment) and its notes
- **Recruitment Lead** - the phase-1 migration target for franchisee/session-worker recruitment, separate from Client Lead
- **Client Transfer Agreement** (+ **Log**) - the three-way sign-off when a client moves between coaches
- **Client Document Share** - a Practice Document shared with a specific client
- **Client Report** - bespoke client progress write-ups, optionally shown on the client portal or emailed
- **Coach Document Requirement** - a Practice Document assigned to a coach/session worker, with status/due-date tracking
- **Coach Onboarding Master Step** / **Coach Onboarding Step** - the onboarding journey template and each coach's per-step instance
- **Coach Recognition** - franchisor-set recognition/achievement entries on a coach
- **Dashboard Conversation** / **Dashboard Conversation Message** / **Dashboard Conversation Recipient** - the notification/messaging system
- **Form Visibility Rule** - controls which "Forms"-module DocTypes are visible where
- **Item Gallery Image** - gallery images on a store/public-facing Item
- **Mileage Log** / **Training And Supervision Log** - coach self-logged entries
- **Online Client** - a guest webshop purchaser, later manually linked to a real Client by email
- **Pending Booking** - fallback queue for appointment bookings that hit MySQL naming-series lock contention
- **Practice Document** (+ **Coach**/**File**/**Item** child tables) - the compliance/policy document library
- **Safer Recruitment Checklist Item** - checklist rows for the recruitment safeguarding process
- **School Pipeline Branding** - branding config for the School Pipeline's automated emails
- **Store Coupon** (+ **Item** child) - store discount codes
- **Store Manager** - the Store dashboard's own user-role doctype
- **TRK Notification Reply** - a reply to a notification
- **Webshop Checkout** (+ **Item** child) - the Store's order record, from cart through Paid/Packed/Shipped
- **Webshop Payment Settings** / **Webshop Shipping Settings** - site-wide Stripe and shipping settings

## `dashboard/api/shared/` - core business logic (~70 modules)

Grouped by area (see each module's own docstring for the full detail - most are extensively commented):

- **Calendar/booking**: `calendar.py`, `appointment_types.py`, `booking_confirmations.py`, `pending_bookings.py`, `coach_availability.py`, `public_booking.py`, `supervision_booking.py`
- **Clients/contacts/leads**: `clients.py`, `client_details.py`, `client_reports.py`, `client_list_report.py`, `client_locations.py`, `client_transfers.py`, `contacts.py`, `contact_details.py`, `leads.py`, `recruitment_leads.py`, `franchise_info_sheet.py`, `franchise_brochure.py`
- **Invoicing/payments**: `invoices.py`, `payment_utils.py`, `packages.py`, `webshop_purchase.py`, `item_access.py`, `course_unlock_on_payment.py`
- **Store**: `store_products.py`, `store_coupons.py`, `store_orders.py`, `store_shipping.py`, `store_stock.py`, `coach_stock.py`
- **Compliance/onboarding**: `practice_documents.py`, `onboarding.py`, `coach_logs.py`
- **LMS**: `lms_access.py`, `lms_certificates.py`
- **Schools**: `school_pipeline.py`, `school_licenses.py`, `knowledge_vault.py`
- **Coaches/session workers/franchisor views**: `coaches.py`, `session_workers.py`, `coach_view_mode.py`, `session_worker_view.py`, `session_worker_view_mode.py`
- **Assessment/feedback form scoring**: `wellbeing_forms.py`, `care_language_form.py`, `school_experience_form.py`, `staff_relationships_form.py`
- **Email**: `email_templates.py`, `email_sequences.py`, `email_groups.py`, `email_queue_fixes.py`, `mail_throttle.py`, `mailerlite_sync.py`, `google_mail_connect.py`
- **Notifications/search**: `notifications.py`, `global_search.py`, `directory.py`, `form_reports.py`
- **Other**: `profile.py` (role-specific profile config + banking/Stripe Connect), `blog.py`, `webshop_lead_sync.py`, `permissions.py`, `postcode_boundaries.py`, `portal_access.py`, `pagination.py`, `utils.py`, `dashboard.py` (the largest single API surface - shared cross-dashboard endpoints)

Plus `dashboard/api/franchisor/accounts.py` (franchisor-only Session Worker/Coach field access) and `dashboard/api/session_worker/change_requests.py` (wraps the legacy `trk_session_worker_dashboard` app's change-request handling).

## `hooks.py` summary

- **`doc_events`** cover: `Event`/`Client Appointment` sharing, package-balance recalculation and delete-cascades; `Email Queue` spoofed-sender fixes; `Intake Doctype` and `Franchise Information Sheet Response` syncing into the lead pipeline; `Franchise Brochure Request` link delivery; a wildcard (`"*"`) trigger for the Email Sequence engine; `Lead`/`Comment` bridging from `webshop`; `Coach Document Requirement`/`Practice Document`/`Item`/`Coach`/`Session Worker` syncing for compliance and item access; `Coach Onboarding Master Step` propagation; `LMS Certificate`/`LMS Course`/`LMS Enrollment` gating, store-item sync and welcome emails; `Web Form` Reports-visibility syncing; `Blog Post` hero-image visibility; `Stirling Wellbeing Response`/`Care Language Response`/`School Experience Response`/`Relationships With Staff Response` scoring; `Communication` reply detection for the School Pipeline; `Sales Invoice`/`Payment Entry` stock and course-unlock hooks; `Email Group Member` MailerLite sync.
- **`scheduler_events`**: every 5 minutes - sweep stuck pending bookings, send pending booking confirmations, Meet-link followups and online-session reminders; daily at 10am - process due School Pipeline and Email Sequence steps; daily - refresh every client's age-derived client type.
- **`after_migrate`**: a small set of idempotent setup functions that need a doctype from the same deploy's schema sync to already exist (see **Architectural patterns**).
- **Permission overrides**: `has_permission`/`permission_query_conditions`/`override_whitelisted_methods` all target `LMS Course` (`lms_access.py`).
- **`jinja.methods`**: exposes `is_franchisor_user()`/`is_current_user_coach()` to templates (used by the shared topbar).
- **`web_include_js`/`web_include_css`**: shared dashboard CSS/JS, loaded site-wide (not just on dashboard pages) so `descript_embed.js` can also reach Frappe Learning's own lesson pages on the same site.

## Patches (`dashboard/patches.txt`, ~190 entries)

A genuinely useful chronological index of everything this app has grown into. Major thematic groups:

- Calendar/Event sync and visibility fixes
- Booking/invoicing income and confirmation-email plumbing
- Coach onboarding journey (restructured several times - template creation, dedup, LMS-linked steps)
- Practice Document / compliance access resync (several rounds)
- Franchise lead/NDA/Intent/Agreement pipeline, franchise brochure, nurture sequence, and franchise termination forms
- LMS course visibility/restriction/brand fields, and course-store-item syncing
- Standalone Forms-module web forms - wellbeing scales, school questionnaires, consent forms, CPD training/equipment/feedback, media consent/release, sessional worker references, twilight meetings, podcast guest booking
- School Pipeline doctypes and fields
- Store build-out - item/store fields, stock, coupons, shipping, personalization, logo choice
- Knowledge Vault doctypes and staff grant/exclusion fields
- Recruitment Lead doctype creation and field sync (the recruitment_leads.py migration)
- Coach Stock Movement and pack-handover tracking
- Notification Log / Dashboard Conversation threading and orphaned-recipient fixes
- Misc data backfills (client type from DOB, franchise client type restoration, coach fields, item access backfills)

## Tests

`dashboard/tests/test_invoice_payment_rounding.py` - covers invoice outstanding-amount rounding and partial-allocation math. No other test modules exist; most correctness here is enforced by extensive in-code docstrings and manual/production verification rather than an automated suite.

<!-- deploy trigger: 2026-10-15a -->
