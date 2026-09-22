"""Shared pytest setup for hedge_fund.

Loads a local .env if present so optional live tests can see
FINANCIAL_DATASETS_API_KEY. CI and the offline smoke path run without
keys; tests marked ``live`` skip when the variable is unset.
"""

from dotenv import load_dotenv

load_dotenv()
