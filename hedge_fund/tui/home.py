"""The landing screen, the model picker, and the API-key prompt."""

from __future__ import annotations

import os

from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen, Screen
from textual.widgets import Footer, Input, OptionList, Static
from textual.widgets.option_list import Option

from hedge_fund import paths
from hedge_fund.llm import is_supported, load_api_models, provider_for
from hedge_fund.tui.keys import masked, missing_key, PROVIDER_ENV_VARS, save_credential
from hedge_fund.tui.palette import BRIGHT, GREEN, MUTED, TEXT
from hedge_fund.tui.shared import DEFAULT_MODEL_LABEL


class HomeScreen(Screen):
    """The clean landing: wordmark, the two modes, the reasoning-model picker.
    Paper trading runs a fund on real market days; backtesting replays one
    over history. Building a fund lives inside each mode, not up here.
    """

    BINDINGS = [
        Binding("m", "pick_model", "switch model"),
        Binding("k", "set_key", "api key"),
        Binding("escape", "quit_app", "quit"),
    ]

    def compose(self) -> ComposeResult:
        wordmark = "A I   H E D G E   F U N D"
        with Vertical(id="home"):
            yield Static(Text(wordmark, style=f"bold {BRIGHT}"), id="wordmark")
            yield Static(Text("━" * len(wordmark)), id="rule")
            yield OptionList(
                Option(
                    Text.assemble(
                        ("Paper trading\n", "bold"),
                        ("run a fund on real market days", MUTED)),
                    id="paper"),
                None,
                Option(
                    Text.assemble(
                        ("Backtesting\n", "bold"),
                        ("test a fund over history", MUTED)),
                    id="backtest"),
                id="home-menu",
            )
            yield Static("", id="model-line")
        yield Footer()

    def on_mount(self) -> None:
        # Same seam as the CLI picker: HEDGE_FUND_LLM_MODEL steers every agent built
        # downstream. Honor a preset from the shell — even an unlisted one, so
        # a model newer than the registry still works — otherwise pin the
        # default, so what the screen shows is what the agents use.
        models = load_api_models()
        preset = os.environ.get("HEDGE_FUND_LLM_MODEL")
        known = {mid for _, mid, _ in models}
        self._model_id = preset if preset in known else next(
            (mid for label, mid, _ in models if label == DEFAULT_MODEL_LABEL),
            models[0][1],
        )
        os.environ["HEDGE_FUND_LLM_MODEL"] = self._model_id
        self._show_model()
        self.query_one("#home-menu", OptionList).focus()

    def action_pick_model(self) -> None:
        self.app.push_screen(ModelPickerScreen(self._model_id), self._set_model)

    def _set_model(self, model_id: str | None) -> None:
        if model_id is None:
            return
        self._model_id = model_id
        os.environ["HEDGE_FUND_LLM_MODEL"] = model_id
        self._show_model()

    def action_set_key(self) -> None:
        """Set the key for the selected model's provider, before a run needs
        it. Replacing a key that already works is allowed on purpose."""
        provider = provider_for(self._model_id)
        if provider is None:
            self.notify("Model is not in the registry — set its key by hand.",
                        severity="warning")
            return
        env_var = PROVIDER_ENV_VARS.get(provider)
        if env_var is None:
            self.notify(f"No key is needed for {provider}.")
            return
        self.app.push_screen(KeyPromptScreen(provider, env_var),
                             lambda _: self._show_model())

    def action_quit_app(self) -> None:
        self.app.exit()

    def _show_model(self) -> None:
        label = next((name for name, mid, _ in load_api_models()
                      if mid == self._model_id), self._model_id)
        self.query_one("#model-line", Static).update(
            Text.assemble(
                ("agents reason with  ", MUTED),
                (label, f"bold {GREEN}"),
                (f"  {self._model_id}", MUTED),
                ("   ·  m to switch", MUTED),
            )
        )

    @on(OptionList.OptionSelected, "#home-menu")
    def _choose(self, event: OptionList.OptionSelected) -> None:
        # Imported here, not at the top: both screens reach back to this
        # module's key gate, and the home screen is the root of the stack.
        from hedge_fund.tui.funds import FundSelectScreen
        from hedge_fund.tui.paper import PaperScreen
        if event.option.id == "paper":
            self.app.push_screen(PaperScreen())
        elif event.option.id == "backtest":
            self.app.push_screen(FundSelectScreen())


class KeyPromptScreen(ModalScreen[bool]):
    """Ask for the one key a provider needs, and offer to remember it.

    Returns True if a key is now in the environment. The input is masked and
    the value is never echoed back — the confirmation shows a masked form.
    """

    BINDINGS = [Binding("escape", "cancel", "cancel")]

    def __init__(self, provider: str, env_var: str) -> None:
        super().__init__()
        self._provider = provider
        self._env_var = env_var

    def compose(self) -> ComposeResult:
        with Vertical(id="keyprompt"):
            yield Static(Text.assemble(
                (f"{self._provider} API key needed", f"bold {BRIGHT}")),
                id="key-q")
            yield Static(Text.assemble(
                ("The fund cannot run without it. Paste it below and it "
                 "is saved to\n", MUTED),
                (str(paths.ENV_PATH), TEXT),
                ("\nwhich is owner-read-only and loaded automatically on "
                 "every start.", MUTED)),
                id="key-blurb")
            yield Input(password=True, placeholder=self._env_var, id="key-input")
            yield Static(Text.assemble(
                ("enter", f"bold {GREEN}"), ("  save and continue   ", MUTED),
                ("esc", f"bold {BRIGHT}"), ("  cancel", MUTED)),
                classes="hint")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#key-input", Input).focus()

    @on(Input.Submitted, "#key-input")
    def _save(self, event: Input.Submitted) -> None:
        key = event.value.strip()
        if not key:
            self.notify("No key entered", severity="warning")
            return
        path = save_credential(self._env_var, key)
        self.notify(f"Saved {self._env_var} ({masked(key)}) to {path}")
        self.dismiss(True)

    def action_cancel(self) -> None:
        self.dismiss(False)


class ModelPickerScreen(ModalScreen[str | None]):
    """Every model in the repo's registry, grouped by provider.

    Providers v2 has no client for are shown but not selectable — listing
    them is honest about what exists, and disabling them stops a run from
    dying halfway through on a model id ChatAnthropic will reject.
    """

    BINDINGS = [Binding("escape", "cancel", "cancel")]

    def __init__(self, current: str) -> None:
        super().__init__()
        self._current = current

    def compose(self) -> ComposeResult:
        with Vertical(id="picker"):
            yield Static(Text("Agents reason with", style=f"bold {BRIGHT}"),
                         id="picker-q")
            yield OptionList(*self._options(), id="picker-list")
            yield Static(Text("enter to pick · esc to cancel", style=MUTED),
                         classes="hint")
        yield Footer()

    def _options(self) -> list[Option | None]:
        options: list[Option | None] = []
        for provider, models in self._by_provider().items():
            reachable = is_supported(provider)
            head = Text(provider.upper(), style=f"bold {BRIGHT}")
            if not reachable:
                head.append("   no client in v2 yet", style=MUTED)
            options.append(Option(head, disabled=True))
            for name, model_id, _ in models:
                row = Text()
                row.append(" ✓ " if model_id == self._current else "   ",
                           style=f"bold {GREEN}")
                row.append(f"{name:<18}", style=None if reachable else MUTED)
                row.append(model_id, style=MUTED)
                options.append(Option(
                    row, id=model_id if reachable else None,
                    disabled=not reachable))
            options.append(None)
        return options[:-1] if options else options

    def _by_provider(self) -> dict[str, list[tuple[str, str, str]]]:
        """Registry order preserved, reachable providers first — what you can
        actually pick should not sit below what you cannot."""
        groups: dict[str, list[tuple[str, str, str]]] = {}
        for entry in load_api_models():
            groups.setdefault(entry[2], []).append(entry)
        return dict(sorted(groups.items(),
                           key=lambda kv: not is_supported(kv[0])))

    def on_mount(self) -> None:
        picker = self.query_one("#picker-list", OptionList)
        picker.highlighted = next(
            (i for i, opt in enumerate(picker._options)
             if opt.id == self._current), 1)
        picker.focus()

    @on(OptionList.OptionSelected, "#picker-list")
    def _pick(self, event: OptionList.OptionSelected) -> None:
        self.dismiss(event.option.id)

    def action_cancel(self) -> None:
        self.dismiss(None)


def demand_run_keys(app, resume) -> bool:
    """True if every key a run needs is in the environment: the data key
    first, then the selected model's LLM key. Otherwise open the prompt for
    the first missing one; each save calls ``resume``, which should re-enter
    this gate so the next missing key is asked for in turn. Ask here, not
    deep inside a worker thread: a run that dies on a missing credential has
    already spent minutes of warming."""
    if not os.environ.get("FINANCIAL_DATASETS_API_KEY"):
        app.push_screen(
            KeyPromptScreen("Financial Datasets",
                            "FINANCIAL_DATASETS_API_KEY"),
            lambda saved: resume() if saved else None)
        return False
    provider = provider_for(os.environ.get("HEDGE_FUND_LLM_MODEL", ""))
    env_var = missing_key(provider) if provider else None
    if env_var is None:
        return True
    app.push_screen(KeyPromptScreen(provider, env_var),
                    lambda saved: resume() if saved else None)
    return False
