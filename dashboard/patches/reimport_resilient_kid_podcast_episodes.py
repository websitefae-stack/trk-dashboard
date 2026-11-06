"""
Re-run of import_resilient_kid_podcast_episodes.py under a new patch
name, since Ashley couldn't get to Patch Log herself to clear that
one's entry and let it run again. A patch only ever runs once per its
own dotted name (Frappe tracks that in Patch Log) - giving it a new
name is the only way to make it fire again on the next deploy without
anyone touching Patch Log at all.

Exact same logic and same data file (data/resilient_kid_podcast_
import.csv, the 89-episode export) - only ever creates a Podcast
Episode for a title that doesn't already exist yet, never edits or
touches one that's already there. Run this after Ashley deleted the
old manually-entered episodes but the first pass (before she'd
deleted them) ran too early to pick most of them up.
"""

import csv
import os

import frappe

DOCTYPE = "Podcast Episode"
DATA_FILE = os.path.join(os.path.dirname(__file__), "data", "resilient_kid_podcast_import.csv")
VALID_STATUSES = {"Planned", "Recorded", "Published"}


def _to_int(value):
	value = (value or "").strip()
	return int(value) if value.isdigit() else None


def execute():
	if not frappe.db.exists("DocType", DOCTYPE):
		return

	if not os.path.exists(DATA_FILE):
		return

	with open(DATA_FILE, encoding="utf-8", newline="") as f:
		rows = list(csv.DictReader(f))

	imported = 0

	for row in rows:
		title = (row.get("Episode Title") or "").strip()
		if not title:
			continue

		if frappe.db.exists(DOCTYPE, {"episode_title": title}):
			continue

		status = (row.get("Status") or "").strip()
		if status not in VALID_STATUSES:
			status = "Published"

		doc = frappe.new_doc(DOCTYPE)
		doc.episode_title = title
		doc.season_number = _to_int(row.get("Season #"))
		doc.episode_number = _to_int(row.get("Episode #"))
		doc.guest_name = (row.get("Guest (if any)") or "").strip()
		doc.status = status
		doc.air_date = (row.get("Air Date") or "").strip() or None
		doc.topics = (row.get("Topics") or "").strip()
		doc.show_notes = row.get("Show Notes") or ""
		doc.spotify_url = (row.get("Spotify Link") or "").strip()
		doc.youtube_url = (row.get("YouTube Link") or "").strip()
		doc.insert(ignore_permissions=True)
		imported += 1

	frappe.db.commit()
	frappe.logger().info(f"Imported {imported} Resilient Kid podcast episode(s).")
