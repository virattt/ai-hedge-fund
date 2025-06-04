import os

IS_CRYPTO: bool = os.getenv("ASSET_CLASS", "EQUITY").upper() == "CRYPTO"
ALLOW_MARGIN: bool = os.getenv("ALLOW_MARGIN", "0") == "1"

__all__ = ["IS_CRYPTO", "ALLOW_MARGIN"]
