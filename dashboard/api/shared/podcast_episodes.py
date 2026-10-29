"""
A single place to log a podcast episode (title, status, show notes,
topics, and the Spotify/YouTube/Listeners Lounge links once each exists)
so Ashley and coaches can see the full list of episodes - what's been
covered, what's planned next - without it living only in a Trello board.
This doesn't touch the actual publishing workflow (recording, uploading
to Spotify/YouTube, adding the lesson to the Listeners Lounge course all
still happen exactly as they do today) - it's just the one shared record
of an episode's details, instead of re-typing the same title/description
into four different places.

Read access is open to any logged-in dashboard user (coaches included -
see get_podcast_episodes' own docstring for why planning_notes is
stripped out for them). Managing episodes (add/edit/delete) is
franchisor-only.
"""

import frappe
from frappe import _

from dashboard.api.shared.permissions import ensure_logged_in, ensure_office_user

DOCTYPE = "Podcast Episode"

LIST_FIELDS = [
	"name", "episode_title", "season_number", "episode_number", "guest_name", "status", "air_date",
	"topics", "show_notes", "additional_resources",
	"spotify_url", "youtube_url", "listeners_lounge_url",
]


@frappe.whitelist()
def get_podcast_episodes():
	"""
	planning_notes is deliberately left out of LIST_FIELDS - it's for
	Ashley's own use (research notes, ideas for a follow-up) and isn't
	meant for every coach to read, so it's never fetched here regardless
	of who's calling. get_podcast_episode_for_edit() below is the only
	place it's returned, and that one is franchisor-only.
	"""
	ensure_logged_in()

	return frappe.get_all(
		DOCTYPE,
		fields=LIST_FIELDS,
		order_by="air_date desc, season_number desc, episode_number desc",
		ignore_permissions=True,
	)


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
	additional_resources=None,
	planning_notes=None,
	spotify_url=None,
	youtube_url=None,
	listeners_lounge_url=None,
):
	ensure_office_user()

	episode_title = (episode_title or "").strip()
	if not episode_title:
		frappe.throw(_("Please enter an episode title."))

	values = {
		"episode_title": episode_title,
		"season_number": season_number or None,
		"episode_number": episode_number or None,
		"guest_name": (guest_name or "").strip(),
		"status": status if status in ("Planned", "Recorded", "Published") else "Planned",
		"air_date": air_date or None,
		"topics": (topics or "").strip(),
		"show_notes": show_notes or "",
		"additional_resources": additional_resources or "",
		"planning_notes": planning_notes or "",
		"spotify_url": (spotify_url or "").strip(),
		"youtube_url": (youtube_url or "").strip(),
		"listeners_lounge_url": (listeners_lounge_url or "").strip(),
	}

	name = (name or "").strip()

	if name:
		if not frappe.db.exists(DOCTYPE, name):
			frappe.throw(_("Episode not found."))
		doc = frappe.get_doc(DOCTYPE, name)
		doc.update(values)
		doc.save(ignore_permissions=True)
	else:
		doc = frappe.get_doc({"doctype": DOCTYPE, **values})
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
