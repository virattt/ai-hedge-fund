import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _add_argument_calls(path: str):
    tree = ast.parse((ROOT / path).read_text())
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "add_argument"
    ]


def _string_args(call: ast.Call) -> set[str]:
    return {arg.value for arg in call.args if isinstance(arg, ast.Constant) and isinstance(arg.value, str)}


def _keyword_value(call: ast.Call, name: str) -> str | None:
    for keyword in call.keywords:
        if keyword.arg == name and isinstance(keyword.value, ast.Constant):
            return keyword.value.value
    return None


def test_shared_cli_accepts_documented_ticker_alias() -> None:
    ticker_calls = [
        call
        for call in _add_argument_calls("src/cli/input.py")
        if {"--tickers", "--ticker"}.issubset(_string_args(call))
    ]

    assert ticker_calls
    assert _keyword_value(ticker_calls[0], "dest") == "tickers"


def test_backtesting_cli_accepts_documented_ticker_alias() -> None:
    ticker_calls = [
        call
        for call in _add_argument_calls("src/backtesting/cli.py")
        if {"--tickers", "--ticker"}.issubset(_string_args(call))
    ]

    assert ticker_calls
    assert _keyword_value(ticker_calls[0], "dest") == "tickers"
