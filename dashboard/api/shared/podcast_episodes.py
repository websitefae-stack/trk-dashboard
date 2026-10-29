"""
A single place to log a podcast episode (title, status, show notes,
topics, downloadable resources, and the Spotify/YouTube links once each
exists) so Ashley and coaches can see the full list of episodes - what's
been covered, what's planned next - without it living only in a Trello
board. This doesn't touch the actual publishing workflow (recording,
uploading to Spotify/YouTube all still happen exactly as they do today)
- it's just the one shared record of an episode's details, instead of
re-typing the same title/description into other places.

Read access is open to any logged-in dashboard user (coaches included -
see get_podcast_episodes' own docstring for why planning_notes is
stripped out for them, and for the future-air-date visibility rule).
Managing episodes (add/edit/delete) is franchisor-only.
"""

import frappe
from frappe import _
from frappe.utils import getdate, nowdate

from dashboard.api.shared.permissions import ensure_logged_in, ensure_office_user

DOCTYPE = "Podcast Episode"
RESOURCE_DOCTYPE = "Podcast Episode Resource"

# An episode air-dated in the future is Ashley's own preview of what's
# coming - same login FRANCHISOR_USERS (permissions.py) already treats
# as Ashley's own. Deliberately not "any office login" - she's asked for
# this to be hers alone until it airs, office/HQ included.
ASHLEY_EMAIL = "ashley@theresilientkid.co.uk"

LIST_FIELDS = [
	"name", "episode_title", "season_number", "episode_number", "guest_name", "status", "air_date",
	"topics", "show_notes",
	"spotify_url", "youtube_url",
]


def _attach_resources(rows):
	if not rows:
		return rows

	resource_rows = frappe.get_all(
		RESOURCE_DOCTYPE,
		filters={"parent": ["in", [row.name for row in rows]], "parenttype": DOCTYPE},
		fields=["parent", "label", "file"],
		order_by="parent asc, idx asc",
		ignore_permissions=True,
	)

	by_parent = {}
	for resource in resource_rows:
		by_parent.setdefault(resource.parent, []).append({"label": resource.label or "", "file": resource.file})

	for row in rows:
		row["resources"] = by_parent.get(row.name, [])

	return rows


@frappe.whitelist()
def get_podcast_episodes():
	"""
	planning_notes is deliberately left out of LIST_FIELDS - it's for
	Ashley's own use (research notes, ideas for a follow-up) and isn't
	meant for every coach to read, so it's never fetched here regardless
	of who's calling. get_podcast_episode_for_edit() below is the only
	place it's returned, and that one is franchisor-only.

	An episode air-dated in the future is filtered out of this list for
	everyone except Ashley herself (ASHLEY_EMAIL) - including other
	office/HQ logins - so it stays her own preview until it actually
	airs. A blank air_date (nothing scheduled yet) is never treated as
	"future" - it's shown to everyone, same as always.
	"""
	ensure_logged_in()

	rows = frappe.get_all(
		DOCTYPE,
		fields=LIST_FIELDS,
		order_by="air_date desc, season_number desc, episode_number desc",
		ignore_permissions=True,
	)

	if frappe.session.user != ASHLEY_EMAIL:
		today = getdate(nowdate())
		rows = [row for row in rows if not (row.air_date and getdate(row.air_date) > today)]

	return _attach_resources(rows)


@frappe.whitelist()
def get_podcast_episode_for_edit(name=None):
	ensure_office_user()

	name = (name or "").strip()
	if not name or not frappe.db.exists(DOCTYPE, name):
		frappe.throw(_("Episode not found."))

	return frappe.get_doc(DOCTYPE, name).as_dict()


@frappe.whitelist()
def save_podcast_episode(
	name=None,
	episode_title=None,
	season_number=None,
	episode_number=None,
	guest_name=None,
	status=None,
	air_date=None,
	topics=None,
	show_notes=None,
	resources=None,
	planning_notes=None,
	spotify_url=None,
	youtube_url=None,
):
	ensure_office_user()

	episode_title = (episode_title or "").strip()
	if not episode_title:
		frappe.throw(_("Please enter an episode title."))

	if isinstance(resources, str):
		resources = frappe.parse_json(resources) if resources else []
	resources = [
		{"label": (row.get("label") or "").strip(), "file": (row.get("file") or "").strip()}
		for row in (resources or [])
		if isinstance(row, dict) and (row.get("file") or "").strip()
	]

	values = {
		"episode_title": episode_title,
		"season_number": season_number or None,
		"episode_number": episode_number or None,
		"guest_name": (guest_name or "").strip(),
		"status": status if status in ("Planned", "Recorded", "Published") else "Published",
		"air_date": air_date or None,
		"topics": (topics or "").strip(),
		"show_notes": show_notes or "",
		"planning_notes": planning_notes or "",
		"spotify_url": (spotify_url or "").strip(),
		"youtube_url": (youtube_url or "").strip(),
	}

	name = (name or "").strip()

	if name:
		if not frappe.db.exists(DOCTYPE, name):
			frappe.throw(_("Episode not found."))
		doc = frappe.get_doc(DOCTYPE, name)
		doc.update(values)
	else:
		doc = frappe.get_doc({"doctype": DOCTYPE, **values})

	doc.set("resources", [])
	for row in resources:
		doc.append("resources", row)

	if name:
		doc.save(ignore_permissions=True)
	else:
		doc.insert(ignore_permissions=True)

	return {"name": doc.name}


@frappe.whitelist()
def delete_podcast_episode(name=None):
	ensure_office_user()

	name = (name or "").strip()
	if not name or not frappe.db.exists(DOCTYPE, name):
		frappe.throw(_("Episode not found."))

	frappe.delete_doc(DOCTYPE, name, ignore_permissions=True)

	return {"ok": 1}
