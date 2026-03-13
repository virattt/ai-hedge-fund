.PHONY: hl-pipeline hl-pipeline-with-fills hl-pipeline-execute

# Default example values (override at invocation time).
RUN_RESULT ?= second_opinion_runs/second_opinion_run_result_15.json
PORTFOLIO_DRAFT ?= portfolio_draft_hyperliquid_full.json
SYMBOL_MAP ?= configs/agent_cli_symbol_map.example.json
REFERENCE_PRICES ?= configs/agent_cli_reference_prices.example.json
CURRENT_POSITIONS ?= configs/agent_cli_current_positions.example.json
FILLS ?= configs/agent_cli_fills.example.json
MAX_GROSS ?= 120000
MAX_NET ?= 70000
APPEND_FLAGS ?= --mock

hl-pipeline:
	poetry run python scripts/agent_cli_pipeline.py \
		--run-result "$(RUN_RESULT)" \
		--portfolio-draft "$(PORTFOLIO_DRAFT)" \
		--symbol-map "$(SYMBOL_MAP)" \
		--strict-symbol-map \
		--reference-prices "$(REFERENCE_PRICES)" \
		--current-positions "$(CURRENT_POSITIONS)" \
		--max-gross-notional-usd "$(MAX_GROSS)" \
		--max-net-notional-usd "$(MAX_NET)" \
		--append-flags="$(APPEND_FLAGS)"

hl-pipeline-with-fills:
	poetry run python scripts/agent_cli_pipeline.py \
		--run-result "$(RUN_RESULT)" \
		--portfolio-draft "$(PORTFOLIO_DRAFT)" \
		--symbol-map "$(SYMBOL_MAP)" \
		--strict-symbol-map \
		--reference-prices "$(REFERENCE_PRICES)" \
		--current-positions "$(CURRENT_POSITIONS)" \
		--max-gross-notional-usd "$(MAX_GROSS)" \
		--max-net-notional-usd "$(MAX_NET)" \
		--append-flags="$(APPEND_FLAGS)" \
		--fills "$(FILLS)"

# Intentionally requires explicit live-risk acknowledgment in the called script
# when APPEND_FLAGS does not include --mock.
hl-pipeline-execute:
	poetry run python scripts/agent_cli_pipeline.py \
		--run-result "$(RUN_RESULT)" \
		--portfolio-draft "$(PORTFOLIO_DRAFT)" \
		--symbol-map "$(SYMBOL_MAP)" \
		--strict-symbol-map \
		--reference-prices "$(REFERENCE_PRICES)" \
		--current-positions "$(CURRENT_POSITIONS)" \
		--max-gross-notional-usd "$(MAX_GROSS)" \
		--max-net-notional-usd "$(MAX_NET)" \
		--append-flags="$(APPEND_FLAGS)" \
		--execute-plan \
		--i-understand-live-risk
