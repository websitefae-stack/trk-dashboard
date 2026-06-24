import math
import frappe


def get_page_args(default_page_size=25, max_page_size=100):
    try:
        page = int(frappe.form_dict.get("page") or 1)
    except Exception:
        page = 1

    try:
        page_size = int(frappe.form_dict.get("page_size") or default_page_size)
    except Exception:
        page_size = default_page_size

    page = max(page, 1)
    page_size = min(max(page_size, 1), max_page_size)

    return {
        "page": page,
        "page_size": page_size,
        "start": (page - 1) * page_size,
        "search": (frappe.form_dict.get("search") or "").strip(),
    }


def make_pagination(total, page, page_size):
    total_pages = max(1, math.ceil((total or 0) / page_size))

    return {
        "total": total or 0,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
        "has_previous": page > 1,
        "has_next": page < total_pages,
        "previous_page": page - 1 if page > 1 else 1,
        "next_page": page + 1 if page < total_pages else total_pages,
    }
