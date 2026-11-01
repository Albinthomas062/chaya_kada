from django.utils.cache import patch_cache_control


class NoCacheMiddleware:
    """Authenticated pages are never served from the HTTP cache without
    revalidation (no-cache + private + must-revalidate, max-age=0).

    We intentionally do NOT send ``no-store``: it disables the browser's
    back/forward cache, which made the Back button reload the page from
    scratch (audio stopped, autoplay blocked, scroll lost). A logged-out
    user going Back is handled client-side (base.html re-checks the session
    on bfcache restore and reloads to the login page).
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.user.is_authenticated:
            patch_cache_control(response, private=True, no_cache=True,
                                must_revalidate=True, max_age=0)
        return response
