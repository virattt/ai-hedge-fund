"""13F-HR institutional holdings worker functions.

This module will be fully rewritten in Phase 2.1 with three new worker
functions: _fetch_thirteenf_filings(), _fetch_compare_holdings(), and
_fetch_holding_history(), plus a shared _load_thirteenf_report() helper.

The old _fetch_thirteenf() function has been removed as part of the
schema redesign in Phase 1.2. The __init__.py entry point
get_thirteenf_holdings() is likewise removed in Phase 2.2.
"""
import logging

logger = logging.getLogger(__name__)
