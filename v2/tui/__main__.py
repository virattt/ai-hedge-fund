"""Entry point: poetry run python -m v2.tui"""

from dotenv import load_dotenv

from v2.tui.app import HedgeFundApp


def main() -> None:
    load_dotenv()
    HedgeFundApp().run()


if __name__ == "__main__":
    main()
