"""Middleware of the web panel."""

# Pages load nothing but the panel's own stylesheet and typeface and the logos
# of alliances and corporations from EVE's image server, and post forms only
# to the panel.
CONTENT_SECURITY_POLICY = (
    "default-src 'none'; style-src 'self'; font-src 'self'; "
    "img-src https://images.evetech.net; form-action 'self'; "
    "base-uri 'none'; frame-ancestors 'none'"
)


class ContentSecurityPolicyMiddleware:
    """Send the content security policy with every answer."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response.headers.setdefault("Content-Security-Policy", CONTENT_SECURITY_POLICY)
        return response
