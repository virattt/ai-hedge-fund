## Learned User Preferences

- Do not create git commits unless explicitly requested.
- Use `gh` for GitHub-related tasks (issues, PRs, checks, releases).
- Update README and docs alongside feature work, not only code changes.
- LLM provider resolution should auto-detect OpenRouter when it is the only configured provider; commented-out or empty env vars must not count as configured keys.

## Learned Workspace Facts

- Rust project `open-hedge`; primary binaries include `ai-hedge-fund` and `backtester`.
- Yahoo Finance is the default data provider when `FINANCIAL_DATASETS_API_KEY` is unset or still the `.env.example` placeholder; resolution lives in `src/data/provider.rs`.
- Data provider CLI flag `--data-provider` accepts `yahoo-finance` or `financial-datasets` (underscore variants also work).
- Yahoo integration uses the `yahoo-finance-rs` crate; Yahoo-specific fallbacks and derived metrics are in `src/tools/fallback.rs`.
- LLM provider and model resolution is centralized in `resolve_llm_config` in `src/utils/llm.rs`.
- Growth agent uses tiered scoring: four or more periods for full scoring, two to three for partial, zero to one emits neutral with zero confidence.
- Yahoo fallback derives growth fields (revenue, EPS, FCF) from quarterly statement series when Financial Datasets precomputed growth is unavailable.
- Data provider documentation lives in `docs/data_providers.md` and `docs/yahoo_finance_limitations.md`.
- Web dashboard resolves the data provider from environment keys; there is no provider toggle in the UI yet.
