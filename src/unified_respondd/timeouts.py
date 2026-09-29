"""Default timeout for the HTTP requests of third party controller clients.

pyunifi and the vendored Omada client call requests without a timeout, so a
controller that accepts the connection but never answers would block respondd
forever. requests has no global default and ignores socket.setdefaulttimeout,
so its Session.request gets one.
"""

import functools


def set_default_request_timeout(seconds):
    """Makes requests without an explicit timeout time out after seconds."""
    try:
        import requests
    except ImportError:  # no backend needing requests installed
        return

    request = requests.Session.request
    if getattr(request, "default_timeout", None) is not None:
        request = request.__wrapped__

    @functools.wraps(request)
    def request_with_timeout(self, method, url, *args, **kwargs):
        if not args and kwargs.get("timeout") is None:
            kwargs["timeout"] = seconds
        return request(self, method, url, *args, **kwargs)

    request_with_timeout.default_timeout = seconds
    requests.Session.request = request_with_timeout
