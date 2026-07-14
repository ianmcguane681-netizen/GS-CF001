---
    name: cfpb-akamai-transport-fingerprinting
    description: CFPB's Akamai edge blocks Python urllib/requests by TLS/HTTP fingerprint even though curl succeeds from the same IP; and format=json&no_aggs=true silently switches the CFPB search API into a full-export mode ignoring size/product filters.
    ---

    ## Symptom
    Requests to `https://www.consumerfinance.gov/data-research/consumer-complaints/search/api/v1/` (or the bulk CSV download at `files.consumerfinance.gov`) from Python's `urllib` or `requests` return HTTP 403 "Access Denied" (Akamai) or hang indefinitely, while an identical `curl` request (same URL, headers, outbound IP) succeeds immediately.

    ## Root cause 1: client fingerprinting, not IP blocking
    Akamai Bot Manager fingerprints the TLS/HTTP client stack (JA3/JA4-style). Python's `ssl`/`http.client` stack produces a signature Akamai flags as bot traffic; `curl`'s does not. This is NOT an IP-range block — proven by `curl` succeeding from the exact same container/IP that Python fails from.

    **How to apply:** if a Python HTTP client gets 403/hangs against an Akamai-fronted site while curl succeeds with identical params, suspect TLS/HTTP fingerprinting before assuming network/IP restrictions. Fix by shelling out to `curl` as the transport (via `subprocess`), not by changing IP, proxy, or headers.

    ## Root cause 2: CFPB search API query params
    Adding `format=json&no_aggs=true` to the CFPB complaint search API silently switches it into a full-database export/attachment mode that ignores `size` and `product` filters (returns a multi-GB flat array instead of a small filtered Elasticsearch-style `{"hits":{"hits":[...]}}` envelope). Omit those params to get the intended filtered, size-limited response.

    **Why:** discovered while restoring live CFPB access for GS-CF001; this cost significant debugging time because the transport fix alone still produced timeouts, masking a second, independent bug in query construction.
    