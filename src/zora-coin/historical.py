#  Free base URL
# curl -s https://api.developer.coinbase.com/rpc/v1/base/xVQ152Em3ymbtm6XgCqz2EDHdpL3jSGi -H "Content-Type: application/json" -d '{"jsonrpc": "2.0", "id": 1, "method": "eth_blockNumber", "params": []}'

"""
Historical transaction and event querying utility for the Zora‑Coin strategy.

Requires:
    * Ape Framework (https://github.com/ApeWorX/ape) with the Base plugin installed,
      e.g. `pip install eth-ape[base]`
    * A provider endpoint configured for the network alias `base:mainnet`.
      Example (in ~/.ape/config.yaml):

      networks:
        base:
          mainnet:
            alchemy:
              uri: ${ALCHEMY_BASE_MAINNET_RPC}
"""

import pandas as pd
from ape import chain, Contract
from ape import project
from pathlib import Path

CONTRACT_ADDRESS = "0x777777751622c0d3258f214F9DF38E35BF45baF3"


def fetch_decoded_history(
    address: str = CONTRACT_ADDRESS,
    *,
    start_block: int | None = None,
    stop_block: int | None = None,
) -> pd.DataFrame:
    """
    Fetch decoded transaction history for **address** from Base mainnet and return a DataFrame.

    Parameters
    ----------
    address : str
        Contract or EOA address whose history you want.
    start_block, stop_block : int | None
        Optional inclusive block range filters.  Pass ``None`` to get the full history.

    Returns
    -------
    pandas.DataFrame
        A DataFrame where each row is a decoded transaction trace.  Typical columns include:
        ``hash``, ``block_number``, ``timestamp``, ``from``, ``to``, ``method``,
        ``input_arguments``, ``value``, ``gas_used``, ``status``.
    """
    history = chain.history[address]

    # Apply block range filters if given
    if start_block is not None or stop_block is not None:
        history = history.range(start_block=start_block, stop_block=stop_block)

    df = history.query("*")
    return df.reset_index(drop=True)


def main() -> None:
    # Lazily fetch the contract to ensure we have its ABI locally.
    breakpoint()
    contract = Contract(CONTRACT_ADDRESS)
    

    # Example: fetch the last 10 000 blocks worth of transactions involving the contract
    latest_block = chain.blocks[-1].number
    df = fetch_decoded_history(
        start_block=max(0, latest_block - 10_000), stop_block=latest_block
    )

    # Save the data so downstream notebooks can consume it.
    out_path = Path(__file__).with_suffix(".parquet")
    df.to_parquet(out_path, index=False)
    print(
        f"Fetched {len(df):,} decoded transactions for {CONTRACT_ADDRESS}. "
        f"Data saved to {out_path}"
    )


# https://docs.apeworx.io/silverback/stable/userguides/quickstart.html use this for bots


if __name__ == "__main__":
    main()