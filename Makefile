.PHONY: dev console test

# The app under Textual's dev tools: app.tcss reloads live, print/log go to
# `make console`, and any change under hedge_fund/ restarts the app.
# watchfiles stops the app with SIGINT first (Textual restores the terminal
# on Ctrl-C), so no signal flag is needed.
dev:
	poetry run watchfiles \
		"poetry run textual run --dev hedge_fund.tui.app:HedgeFundApp" hedge_fund

# Second terminal: the devtools console the running app logs to.
console:
	poetry run textual console

test:
	poetry run pytest hedge_fund/
