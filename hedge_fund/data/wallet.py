"""Pay Financial Datasets per call with x402 instead of an API key.

x402 is an open payment protocol: a request without a key gets a 402 whose
``PAYMENT-REQUIRED`` header names the price in USDC on Base; the client signs
a transfer for that amount and retries with a ``PAYMENT-SIGNATURE`` header.
The ``x402`` package does all of that inside a ``requests`` adapter, so the
rest of the client never sees the 402. See https://docs.financialdatasets.ai/x402

The package is an optional extra (``pip install 'aihf[x402]'``): it pulls in
web3 and eth-account, which API-key users should not have to install.
"""

from __future__ import annotations

import requests

WALLET_KEY_ENV = "X402_WALLET_PRIVATE_KEY"
BASE_MAINNET = "eip155:8453"
INSTALL_HINT = f"{WALLET_KEY_ENV} is set but the x402 package is not installed: pip install 'aihf[x402]'"


class PaymentFailed(requests.RequestException):
    """The x402 adapter could not sign or settle a payment. A RequestException
    on purpose: the client already maps those to FDClientError, so a payment
    failure fails loud through the same path as a network failure."""


def payment_session(private_key: str) -> requests.Session:
    """A requests Session that pays each 402 from the wallet *private_key*.

    Raises ImportError with the install command when the x402 extra is
    missing; the client turns that into its own error.
    """
    try:
        from eth_account import Account
        from x402 import x402ClientSync
        from x402.http.clients.requests import PaymentError, x402HTTPAdapter
        from x402.mechanisms.evm import EthAccountSigner
        from x402.mechanisms.evm.exact import ExactEvmScheme
    except ImportError as exc:
        raise ImportError(INSTALL_HINT) from exc

    class _Adapter(x402HTTPAdapter):
        def send(self, request, **kwargs):
            try:
                return super().send(request, **kwargs)
            except PaymentError as exc:
                raise PaymentFailed(str(exc), request=request) from exc

    client = x402ClientSync()
    client.register(BASE_MAINNET, ExactEvmScheme(EthAccountSigner(Account.from_key(private_key))))
    session = requests.Session()
    session.mount("https://", _Adapter(client))
    return session
