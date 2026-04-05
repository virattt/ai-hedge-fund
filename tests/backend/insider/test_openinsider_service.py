"""OpenInsider service tests — split into focused modules.

Tests have been reorganised into two files for maintainability:

- test_openinsider_url.py  — URL construction, API-to-OI key translation,
                             HTML table parsing, and Cloudflare detection
- test_openinsider_fetch.py — synchronous fetch worker and async cache entry point
"""
