"""Entry point: poetry run python -m hedge_fund.tui"""

from dotenv import load_dotenv

from hedge_fund.tui.app import HedgeFundApp


def main() -> None:
    load_dotenv()
    HedgeFundApp().run()


if __name__ == "__main__":
    main()
