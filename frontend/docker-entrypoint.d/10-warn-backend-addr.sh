#!/bin/sh
# Warns about BACKEND_ADDR values that would break API routing.
#
# nginx treats a URI part in proxy_pass (a trailing slash) as a prefix to replace,
# so "http://backend:8000/" forwards a request for /api/books as /books and every
# API call returns 404 while nginx itself starts cleanly.
#
# The value cannot be corrected here. envsubst only substitutes variables verbatim,
# and the image runs each script in /docker-entrypoint.d as a separate process, so an
# export from this script never reaches the later envsubst call. Printing is the only
# thing that works without replacing the image entrypoint or giving up nginx's
# startup-time upstream validation.
#
# The numbered filename makes this run before 20-envsubst-on-templates.sh.

BACKEND_ADDR="${BACKEND_ADDR-}"

case "$BACKEND_ADDR" in
    "")
        echo "librislog: BACKEND_ADDR is empty, so nginx renders an invalid proxy_pass and will not start." >&2
        echo "librislog: set it to an address such as http://backend:8000." >&2
        ;;
    */)
        echo "librislog: BACKEND_ADDR ends with a slash ('$BACKEND_ADDR')." >&2
        echo "librislog: nginx replaces the matched location prefix, so /api/books is forwarded as /books and every API call returns 404." >&2
        echo "librislog: drop the trailing slash." >&2
        ;;
esac

exit 0
