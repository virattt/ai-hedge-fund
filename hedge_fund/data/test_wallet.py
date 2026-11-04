"""The x402 paying session: built from the optional extra, or a clear error."""

import builtins
import sys

import pytest
import requests

from hedge_fund.data.wallet import payment_session, PaymentFailed

# A throwaway key (the number 1): valid shape, no funds, never used anywhere.
PRIVATE_KEY = "0x" + "0" * 63 + "1"


def test_missing_package_names_the_install_command(monkeypatch):
    real_import = builtins.__import__

    def without_x402(name, *args, **kwargs):
        if name == "x402" or name.startswith("x402."):
            raise ImportError(f"No module named '{name}'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", without_x402)
    for module in [m for m in sys.modules if m == "x402" or m.startswith("x402.")]:
        monkeypatch.delitem(sys.modules, module)
    with pytest.raises(ImportError, match=r"X402_WALLET_PRIVATE_KEY is set.*pip install 'aihf\[x402\]'"):
        payment_session(PRIVATE_KEY)


def test_payment_failure_is_a_request_exception():
    """So the client's one except clause maps it to FDClientError."""
    assert issubclass(PaymentFailed, requests.RequestException)


def test_session_pays_from_the_wallet_on_base():
    pytest.importorskip("x402")  # the optional extra
    from x402.http.clients.requests import x402HTTPAdapter

    session = payment_session(PRIVATE_KEY)
    adapter = session.get_adapter("https://api.financialdatasets.ai/prices")
    assert isinstance(adapter, x402HTTPAdapter)
    assert "X-API-Key" not in session.headers
