# Coach Calendar Sync

A Frappe app that syncs Coach and Session Worker calendars with Google Calendar using OAuth 2.0.

## Features

- Per-Coach / per-Session Worker Google Calendar authorisation (no shared credentials)
- Automatic OAuth flow with offline refresh tokens
- Auto-discovers each person's primary Calendar ID
- Creates, updates, cancels and deletes Google Calendar events in response to Frappe Event changes
- Automatically attaches Google Meet links for online/therapy sessions
- Background job every 5 minutes: push pending, pull Google changes, retry failures
- Bulk Calendar Sync page for importing historical appointments
- Calendar Sync Dashboard showing connection health and sync statistics
- Calendar Sync Log for full audit trail
- All fields added as Custom Fields — no core Frappe files modified

## Requirements

- Frappe >= 15
- Python >= 3.10
- `google-auth`, `google-auth-oauthlib`, `google-api-python-client`

## Installation

### 1. Get the app

```bash
cd /path/to/frappe-bench
bench get-app https://github.com/your-org/coach_calendar_sync
# or, if cloned locally:
bench get-app coach_calendar_sync /path/to/coach_calendar_sync
```

### 2. Install into your site

```bash
bench --site your-site.local install-app coach_calendar_sync
bench migrate
bench build --app coach_calendar_sync
```

### 3. Configure Google OAuth

In the [Google Cloud Console](https://console.cloud.google.com/):

1. Create (or select) a project.
2. Enable the **Google Calendar API**.
3. Go to **APIs & Services → Credentials → Create Credentials → OAuth 2.0 Client ID**.
4. Application type: **Web application**.
5. Add an Authorised redirect URI:
   `https://<your-domain>/coach-calendar-sync/oauth/callback`
6. Copy the **Client ID** and **Client Secret**.

### 4. Configure Calendar Sync Settings

In Frappe, go to **Calendar Sync Settings** and fill in:

- Google Client ID
- Google Client Secret
- Redirect URI (must match step 3 exactly)

### 5. Connect a Coach or Session Worker

1. Open the Coach or Session Worker form.
2. Enable **Google Sync Enabled**.
3. Click **Connect Google Calendar**.
4. A Google authorisation window opens — complete the sign-in.
5. The **Connected** checkbox is ticked automatically and the **Google Calendar ID** is populated.

## Architecture

```
coach_calendar_sync/
├── hooks.py                    # Frappe app hooks (doc_events, scheduler, OAuth route)
├── install.py                  # Runs on bench install-app
├── patches/
│   └── install_custom_fields.py # Custom Fields for Coach, Session Worker, Event
├── utils/
│   ├── google_auth.py          # OAuth credential management
│   └── google_calendar.py      # Google Calendar API wrapper
├── sync/
│   ├── event_hooks.py          # Frappe doc_events → enqueue background jobs
│   ├── worker.py               # Background job handlers (push/cancel/delete)
│   ├── puller.py               # Pull events from Google → Frappe
│   ├── scheduler.py            # 5-minute scheduled task
│   └── logger.py               # Calendar Sync Log writer
├── api/
│   ├── oauth.py                # OAuth endpoints (whitelist + callback route)
│   └── bulk_sync.py            # Bulk Sync and Dashboard API
├── doctype/
│   ├── calendar_sync_settings/ # Singleton settings DocType
│   └── calendar_sync_log/      # Audit log DocType
└── page/
    ├── bulk_calendar_sync/     # Bulk import/resync page
    └── calendar_sync_dashboard/ # Health/stats dashboard
```

## Google Meet Logic

A Meet link is automatically created when:

- The Event's Session Type is **Therapy Session**, **Parent Check-In**, or **Initial Consultation**
- OR the Location contains the words **Google Meet**, **Online**, or **Virtual**

The Meet URL is written back to `custom_google_meet_url` on the Event.

## Sync Status

Every Event has three custom fields:

| Field | Purpose |
|---|---|
| `custom_sync_status` | Pending / Synced / Failed |
| `custom_google_event_id` | The Google Calendar event ID |
| `custom_last_sync_error` | Last error message for easy triage |

## Background Jobs

The 5-minute scheduler (`*/5 * * * *`) does three things in order:

1. Re-enqueues all `Pending` Events
2. Re-enqueues up to 50 `Failed` Events
3. Pulls new/changed events from every connected person's Google Calendar

## Frappe Cloud Deployment Notes

- The `redirect_uri` in **Calendar Sync Settings** must be publicly reachable — use your Frappe Cloud domain.
- Background workers must be enabled (they are on Frappe Cloud by default).
- The `google-*` Python packages are declared as app dependencies in `pyproject.toml` and are installed automatically by `bench get-app`.
