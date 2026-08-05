"""Entry point: poetry run python -m hedge_fund.tui"""

from hedge_fund.tui.app import HedgeFundApp


def main() -> None:
    HedgeFundApp().run()


if __name__ == "__main__":
    main()
