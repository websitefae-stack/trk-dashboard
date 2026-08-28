/**
 * Turns a Descript share link into a playable video wherever it appears
 * in a lesson - Frappe LMS has no Descript entry in its own trusted
 * embed list, and editing that app directly isn't safe to do here (see
 * README), so this gets the same result without touching any LMS file:
 * it watches the lesson content for a normal hyperlink pointing at
 * share.descript.com (added with the editor's own Link tool - select
 * some text, click the link icon, paste the Descript URL) and swaps it
 * for a responsive embedded player.
 *
 * Harmless everywhere else on the site: it only ever acts on a link
 * matching share.descript.com, and the #editor lookup below simply
 * never finds anything on a page that isn't a Learning lesson.
 */
(function () {
	"use strict";

	var DESCRIPT_LINK_PATTERN = /^https:\/\/share\.descript\.com\/(?:view|embed)\/([A-Za-z0-9]+)/i;

	function embedUrlFor(shareUrl) {
		var match = (shareUrl || "").match(DESCRIPT_LINK_PATTERN);
		return match ? "https://share.descript.com/embed/" + match[1] : null;
	}

	function replaceLink(anchor) {
		if (anchor.dataset.descriptEmbedded === "1") return;

		var embedUrl = embedUrlFor(anchor.getAttribute("href"));
		if (!embedUrl) return;

		anchor.dataset.descriptEmbedded = "1";

		var wrapper = document.createElement("div");
		wrapper.style.position = "relative";
		wrapper.style.paddingTop = "56.25%";
		wrapper.style.margin = "1rem 0";

		var iframe = document.createElement("iframe");
		iframe.src = embedUrl;
		iframe.style.position = "absolute";
		iframe.style.inset = "0";
		iframe.style.width = "100%";
		iframe.style.height = "100%";
		iframe.setAttribute("frameborder", "0");
		iframe.setAttribute("allow", "autoplay; fullscreen");
		iframe.setAttribute("allowfullscreen", "");

		wrapper.appendChild(iframe);
		anchor.replaceWith(wrapper);
	}

	function scan(root) {
		root.querySelectorAll('a[href*="share.descript.com"]').forEach(replaceLink);
	}

	function watchLessonContent(editorEl) {
		scan(editorEl);

		var observer = new MutationObserver(function () {
			scan(editorEl);
		});
		observer.observe(editorEl, { childList: true, subtree: true });
	}

	// Frappe LMS's lesson page is a Vue SPA - it mounts and fetches the
	// lesson well after this script has already loaded, so #editor
	// doesn't exist yet at page load. Poll briefly until it shows up
	// (20s covers even a slow connection), then switch to watching it
	// directly instead of polling forever.
	var attempts = 0;
	var waitForEditor = window.setInterval(function () {
		attempts += 1;
		var editorEl = document.getElementById("editor");

		if (editorEl) {
			window.clearInterval(waitForEditor);
			watchLessonContent(editorEl);
		} else if (attempts > 40) {
			window.clearInterval(waitForEditor);
		}
	}, 500);
})();
