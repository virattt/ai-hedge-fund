"""
blockchain_relayer.py — Bridge between portfolio_manager decisions and Base Sepolia.

Only buy/sell decisions are relayed; hold/short/cover are silently skipped.

Hash construction mirrors AIVault.sol exactly:
    messageHash    = keccak256(abi.encodePacked(ticker, action, quantity, confidence))
    ethSignedHash  = keccak256("\\x19Ethereum Signed Message:\\n32" || messageHash)
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.agents.portfolio_manager import PortfolioDecision

logger = logging.getLogger(__name__)

# ABI lives next to the compiled Foundry artefact
_ABI_PATH = Path(__file__).resolve().parents[2] / "contracts" / "out" / "AIVault.sol" / "AIVault.json"

_RELAY_ACTIONS = {"buy", "sell"}


def _load_abi() -> list[dict]:
    with _ABI_PATH.open() as fh:
        return json.load(fh)["abi"]


def _build_client():
    """Return (web3, contract, account) or raise if env is incomplete."""
    # Lazy imports so the rest of the hedge-fund works without web3 installed
    from eth_abi.packed import encode_packed  # noqa: F401 — imported here for early error
    from eth_account import Account
    from web3 import Web3

    # Ensure .env is loaded regardless of the entry-point (main.py, tests, scripts…)
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass  # python-dotenv not installed — rely on env already being set

    rpc_url = os.environ.get("BASE_SEPOLIA_RPC_URL", "https://sepolia.base.org")
    contract_address = os.environ.get("CONTRACT_ADDRESS", "")
    private_key = os.environ.get("AGENT_PRIVATE_KEY", "")

    if not contract_address or contract_address.startswith("0xYOUR"):
        raise EnvironmentError("CONTRACT_ADDRESS is not configured in .env")
    if not private_key or private_key.startswith("0xYOUR"):
        raise EnvironmentError("AGENT_PRIVATE_KEY is not configured in .env")

    w3 = Web3(Web3.HTTPProvider(rpc_url))
    if not w3.is_connected():
        raise ConnectionError(f"Cannot connect to Base Sepolia RPC: {rpc_url}")

    account = Account.from_key(private_key)
    contract = w3.eth.contract(
        address=Web3.to_checksum_address(contract_address),
        abi=_load_abi(),
    )
    return w3, contract, account


def _sign_trade(
    w3,
    account,
    ticker: str,
    action: str,
    quantity: int,
    confidence: int,
) -> bytes:
    """
    Reproduce the on-chain hashing so recoverSigner() accepts the signature.

    Solidity:
        bytes32 messageHash = keccak256(abi.encodePacked(ticker, action, quantity, confidence));
        bytes32 ethSignedHash = keccak256("\\x19Ethereum Signed Message:\\n32" || messageHash);
    """
    from eth_abi.packed import encode_packed
    from eth_account.messages import encode_defunct
    from web3 import Web3

    packed = encode_packed(
        ["string", "string", "uint256", "uint256"],
        [ticker, action, quantity, confidence],
    )
    message_hash: bytes = Web3.keccak(packed)
    signable = encode_defunct(message_hash)
    signed = account.sign_message(signable)
    return signed.signature


def _send_signal(
    w3,
    contract,
    account,
    ticker: str,
    action: str,
    quantity: int,
    confidence: int,
) -> str:
    """Build, sign, and broadcast one executeTradeSignal transaction. Returns tx hash."""
    signature = _sign_trade(w3, account, ticker, action, quantity, confidence)

    nonce = w3.eth.get_transaction_count(account.address, "pending")
    gas_price = w3.eth.gas_price

    tx = contract.functions.executeTradeSignal(
        ticker,
        action,
        quantity,
        confidence,
        signature,
    ).build_transaction(
        {
            "from": account.address,
            "nonce": nonce,
            "gasPrice": gas_price,
        }
    )

    # Estimate gas and add 20 % buffer
    try:
        estimated = w3.eth.estimate_gas(tx)
        tx["gas"] = int(estimated * 1.2)
    except Exception:
        tx["gas"] = 200_000  # safe fallback for Base Sepolia

    signed_tx = account.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)

    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
    if receipt["status"] != 1:
        raise RuntimeError(f"Transaction reverted: {tx_hash.hex()}")

    return tx_hash.hex()


def relay_decisions(decisions: dict[str, "PortfolioDecision"]) -> None:
    """
    Entry point called by portfolio_management_agent after every LLM run.

    Iterates over *decisions*, skips anything that is not a buy or sell,
    and submits the rest to AIVault.executeTradeSignal on Base Sepolia.

    Errors are logged as warnings so that a blockchain issue never crashes
    the rest of the hedge-fund pipeline.
    """
    actionable = {
        ticker: decision
        for ticker, decision in decisions.items()
        if decision.action in _RELAY_ACTIONS and decision.quantity > 0
    }

    if not actionable:
        logger.debug("relay_decisions: no buy/sell signals to relay")
        return

    try:
        w3, contract, account = _build_client()
    except (EnvironmentError, ConnectionError, ImportError) as exc:
        logger.warning("relay_decisions: skipping relay — %s", exc)
        return

    for ticker, decision in actionable.items():
        try:
            tx_hash = _send_signal(
                w3=w3,
                contract=contract,
                account=account,
                ticker=ticker,
                action=decision.action,
                quantity=decision.quantity,
                confidence=decision.confidence,
            )
            logger.info(
                "relay_decisions: relayed %s %s x%d (conf=%d) → tx %s",
                decision.action.upper(),
                ticker,
                decision.quantity,
                decision.confidence,
                tx_hash,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "relay_decisions: failed to relay %s %s — %s",
                decision.action,
                ticker,
                exc,
            )
