__version__ = "0.0.1"

# Runs once per worker process at app import - see this function's own
# docstring for why (stops the Blog app's built-in has_permission hook
# crashing on every anonymous request with a "NoneType is not iterable"
# error, logged as "Failed to call has_permission hook
# (blog.check_app_permission) for blog").
try:
    from dashboard.api.shared.startup_patches import patch_get_modules_from_app_none_safety

    patch_get_modules_from_app_none_safety()
except Exception:
    pass
