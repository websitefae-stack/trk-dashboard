# trk-dashboard

**The Resilient Dashboard** - the operational back-office for The Resilient Kid/Hub coaching franchise, built on Frappe. One app, three role-scoped dashboards, shared underneath by a common API layer and a large family of custom DocTypes covering clients, bookings, invoicing, compliance documents, coach onboarding, and a set of bespoke feedback/assessment forms.

## Dashboards

- Session Worker → `/session_worker_db`
- Coach → `/coach_db`
- Franchisor → `/franchisor_db`

Access is gated in `dashboard/api/shared/permissions.py` (`redirect_if_wrong_dashboard`) - a logged-in user is redirected to whichever dashboard matches their actual role; Guests/unknown users are blocked.

The three dashboards are **not** feature-identical:

- **Shared by all three**: calendar, clients, contacts, documents (Practice Document library), notifications, profile, reports.
- **Coach + Franchisor only**: invoices, leads (Client Lead pipeline), onboarding, links, session worker management.
- **Franchisor only**: coach roster (`coaches`/`coach_details`), item access (granting coaches the right to sell/publish specific Items), statements.
- There's also a standalone `/franchisee-nda` page outside the three dashboards, for the franchisee NDA signing flow.

## What this app actually does

- Client, appointment/calendar, lead (including franchise-prospect leads) and invoicing management
- "Practice Documents" - a compliance/policy document library with per-coach/session-worker requirement tracking, assignment, and sharing
- Coach Onboarding Journey - a master-step template instantiated per coach, with LMS course/chapter/lesson links and dependency locking
- A large family of bespoke, self-contained feedback/assessment/booking web forms built as their own DocTypes (see Patches below) - wellbeing scales, school questionnaires, consent forms, CPD booking/feedback forms
- Guest checkout for one-off online purchases (Stripe) and per-coach Stripe Connect payment settings
- Global topbar search, a Dashboard Conversation-based notification/messaging system, and franchisor "view as coach"/"view as session worker" modes

## Tech Stack / Integrations

This app doesn't stand alone - it's one of several Frappe apps sharing a site, and depends directly on some of them:

- **Frappe Framework**
- **ERPNext** - a real, hard dependency of invoicing, not optional: `payment_utils.py` imports `erpnext.accounts.doctype.payment_entry.payment_entry.get_payment_entry` directly, and the invoicing flow is built on ERPNext's Sales Invoice/Payment Entry/GL Entry. (Not currently declared in `pyproject.toml`'s bench dependencies, worth fixing separately.)
- **Frappe LMS ("Learning")** - this app adds its own `has_permission`/`permission_query_conditions` and whitelisted-method overrides for LMS Course visibility/restriction (`api/shared/lms_access.py`), and gates certificate issuance on course completion (`lms_certificates.py`). Course/lesson data itself lives in the LMS app.
- **`coach_calendar_sync`** (sibling repo) - reads/writes custom fields on the core `Event` doctype to push/pull Google Calendar and create Google Meet links.
- **`resilient_domains`** (sibling repo) - the public, unauthenticated brand websites (coach profiles, public booking widget, blog) that consume this app's guest-facing endpoints (`public_booking.py`, `webshop_purchase.py`) and link back into these dashboards.
- **`client_portal`** (sibling repo) - client-facing login; this app manages the `Client Contact Link` rows it reads.
- **`webshop`** - its "Contact Us" enquiry flow is bridged into the Client Lead board; its payment-gateway/Stripe doctypes are reused for one-off purchases.
- **`trk_session_worker_dashboard`** - an older, separate predecessor app still called into from `api/session_worker/change_requests.py` for change-request handling.
- **Stripe** - a declared Python dependency, used for per-coach Connect payment settings and site-wide webshop payment settings.

## Custom DocTypes (`dashboard/dashboard/doctype/`)

- **Client Lead** / **Client Lead Note** - the Client Lead pipeline (regular and franchise-prospect leads) and its notes
- **Client Document Share** - a Practice Document shared with a specific client
- **Client Report** - bespoke client progress write-ups, optionally shown on the client portal or emailed
- **Coach Document Requirement** - a Practice Document assigned to a coach/session worker, with status/due date tracking
- **Coach Onboarding Master Step** / **Coach Onboarding Step** - the onboarding journey template and each coach's per-step instance
- **Dashboard Conversation** / **Dashboard Conversation Message** / **Dashboard Conversation Recipient** - the notification/messaging system
- **Form Visibility Rule** - controls which "Forms"-module DocTypes are visible where
- **Mileage Log** / **Training And Supervision Log** - coach self-logged entries
- **Online Client** - a guest webshop purchaser, later manually linked to a real Client by email
- **Pending Booking** - fallback queue for appointment bookings that hit MySQL naming-series lock contention
- **Practice Document** (+ **Practice Document Coach**/**File**/**Item** child tables) - the compliance/policy document library
- **TRK Notification Reply** - a reply to a notification
- **Webshop Payment Settings** - single/site-wide Stripe settings

## Patches (`dashboard/patches.txt`, ~100 entries)

Major thematic groups, each covering several individual patches:

- Calendar/Event sync and visibility fixes
- Booking/invoicing income and confirmation-email plumbing
- Invoice/income tracking fixes
- Coach onboarding journey (the largest group - template creation, restructuring, dedup, LMS-linked steps)
- Practice Document / compliance access resync
- Franchise lead/NDA pipeline, franchise brochure and termination forms
- LMS course visibility/restriction fields
- Standalone web forms for schools - bookings, consent, feedback, assessment (Stirling Wellbeing Scale, care-languages quiz, school experience, staff relationships, CPD training/equipment/feedback, media consent/release)
- Podcast/marketing standalone forms
- Standalone-form UI cleanup (section breaks, titles, CSS)
- File/image public-visibility fixes
- Reports-section and web-form brand/visibility control
- Notification Log / conversation threading fixes
- Misc data backfills (client type from DOB, franchise client type restoration, coach fields)

## `dashboard/api/shared/` - core business logic (49 modules)

Grouped by area (not exhaustive - see the module docstrings for detail):

- **Calendar/booking**: `calendar.py`, `appointment_types.py`, `booking_confirmations.py`, `pending_bookings.py`, `coach_availability.py`, `public_booking.py`
- **Clients/contacts/leads**: `clients.py`, `client_details.py`, `client_reports.py`, `client_locations.py`, `contacts.py`, `contact_details.py`, `leads.py`, `franchise_info_sheet.py`
- **Invoicing/payments**: `invoices.py`, `payment_utils.py`, `packages.py`, `webshop_purchase.py`, `item_access.py`
- **Compliance/onboarding**: `practice_documents.py`, `onboarding.py`, `coach_logs.py`
- **LMS**: `lms_access.py`, `lms_certificates.py`
- **Coaches/session workers/franchisor views**: `coaches.py`, `session_workers.py`, `coach_view_mode.py`, `session_worker_view.py`, `session_worker_view_mode.py`
- **Assessment/feedback form scoring**: `wellbeing_forms.py`, `care_language_form.py`, `school_experience_form.py`, `staff_relationships_form.py`
- **Notifications/search**: `notifications.py`, `global_search.py`, `directory.py`
- **Other**: `profile.py` (role-specific profile config + banking/Stripe Connect), `email_templates.py`, `form_reports.py`, `blog.py`, `google_mail_connect.py`, `webshop_lead_sync.py`, `permissions.py`, `postcode_boundaries.py`, `portal_access.py`, `pagination.py`, `utils.py`

Plus `dashboard/api/franchisor/accounts.py` (franchisor-only Session Worker/Coach field access) and `dashboard/api/session_worker/change_requests.py` (wraps the legacy `trk_session_worker_dashboard` app's change-request handling).

## hooks.py summary

- **doc_events** cover: appointment/Event sharing and package-balance recalculation, Client Lead sync from intake forms and the Franchise Information Sheet, webshop lead bridging, Practice Document requirement notifications and brand-based resync, Coach Onboarding step syncing, LMS Certificate gating, Web Form report-visibility syncing, Blog Post hero-image visibility, and scoring hooks for the custom assessment forms.
- **scheduler_events**: every 5 minutes - sweep stuck pending bookings, send pending booking confirmations and Meet-link followups; daily - refresh every client's age-derived client type.
- **Permission overrides**: `has_permission`/`permission_query_conditions`/`override_whitelisted_methods` all target `LMS Course` (`lms_access.py`), needed because Frappe LMS's own `get_courses`/`get_course_count` use `frappe.get_all()`, which ignores permission hooks entirely.

## Tests

`dashboard/tests/test_invoice_payment_rounding.py` - covers invoice outstanding-amount rounding and partial-allocation math. No other test modules exist.

<!-- deploy trigger: 2026-09-11a -->
