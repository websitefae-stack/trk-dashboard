import frappe


def get_pagination_args(default_page_size=25, max_page_size=100):
    page = frappe.form_dict.get("page") or 1
    page_size = frappe.form_dict.get("page_size") or default_page_size
    search = (frappe.form_dict.get("search") or "").strip()

    try:
        page = int(page)
    except Exception:
        page = 1

    try:
        page_size = int(page_size)
    except Exception:
        page_size = default_page_size

    page = max(page, 1)
    page_size = min(max(page_size, 1), max_page_size)

    start = (page - 1) * page_size

    return {
        "page": page,
        "page_size": page_size,
        "start": start,
        "search": search,
    }


def paginated_response(items, total, page, page_size):
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "has_next": page * page_size < total,
        "has_previous": page > 1,
    }
