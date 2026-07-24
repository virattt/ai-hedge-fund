"""GPT-5.5 validation pass — reviews snapshot and analyst signal consistency."""
import json
import os
from typing import List

from colorama import Fore, Style
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from src.llm.models import ModelProvider, get_model


class ValidationReport(BaseModel):
    is_consistent: bool = Field(description="True if data appears internally consistent")
    flags: List[str] = Field(description="Anomalies or contradictions found (empty list if none)")
    summary: str = Field(description="3-5 sentence validation summary")
    data_confidence: int = Field(description="0-100 confidence in data accuracy")


def _wrap(text: str, width: int = 72) -> str:
    words = text.split(); lines = []; cur = ""
    for w in words:
        if len(cur) + len(w) + 1 > width:
            if cur:
                lines.append(cur)
            cur = w
        else:
            cur = (cur + " " + w).strip()
    if cur:
        lines.append(cur)
    return "\n    ".join(lines)


def validate_analysis(
    result: dict,
    snapshots: dict,
    model_name: str = "gpt-5.5",
    model_provider: str = "OpenAI",
) -> None:
    """
    Use GPT-5.5 to validate analysis and snapshot data for internal consistency.
    Prints a validation report. Skips gracefully if OPENAI_API_KEY is not set.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print(f"\n{Fore.YELLOW}[VALIDATOR] Skipped — OPENAI_API_KEY not set.{Style.RESET_ALL}")
        return

    print(f"\n{Fore.MAGENTA}{Style.BRIGHT}{'═' * 70}{Style.RESET_ALL}")
    print(f"{Fore.MAGENTA}{Style.BRIGHT}  GPT-5.5 VALIDATION REPORT  (Opus 4.7 ran it · GPT-5.5 validates it){Style.RESET_ALL}")
    print(f"{Fore.MAGENTA}{Style.BRIGHT}{'═' * 70}{Style.RESET_ALL}")

    try:
        model = get_model(model_name, ModelProvider.OPENAI, api_keys={"OPENAI_API_KEY": api_key})
        structured = model.with_structured_output(ValidationReport, method="json_mode")
    except Exception as e:
        print(f"  {Fore.RED}[VALIDATOR] Could not initialise GPT-5.5 model: {e}{Style.RESET_ALL}")
        return

    analyst_signals = result.get("analyst_signals", {})

    for ticker, snapshot in snapshots.items():
        # Gather all signals for this ticker
        ticker_signals = {}
        for agent, signals in analyst_signals.items():
            if ticker in signals:
                s = signals[ticker]
                ticker_signals[agent] = {
                    "signal": s.get("signal"),
                    "confidence": s.get("confidence"),
                }

        system_msg = (
            "You are a rigorous financial data auditor. Your job:\n"
            "1. Check if technical indicators are internally consistent "
            "(e.g., RSI overbought + Death Cross is unusual but possible — flag if extreme).\n"
            "2. Check if the analyst signal distribution is consistent with the snapshot fundamentals.\n"
            "3. Flag data anomalies (negative prices, absurd ratios, missing key fields).\n"
            "4. Assess overall data quality and reliability.\n"
            "Be clinical and precise. Your role is data integrity, not investment advice.\n"
            'Respond ONLY with valid JSON: {{"is_consistent":bool,"flags":["..."],"summary":"3-5 sentences","data_confidence":0-100}}'
        )
        human_msg = (
            f"Validate data for {ticker}:\n\n"
            f"SNAPSHOT:\n{json.dumps(snapshot, indent=2, default=str)}\n\n"
            f"ANALYST SIGNALS:\n{json.dumps(ticker_signals, indent=2)}"
        )

        template = ChatPromptTemplate.from_messages([("system", system_msg), ("human", "{human}")])
        prompt = template.invoke({"human": human_msg})

        try:
            report: ValidationReport = structured.invoke(prompt)

            status = "PASS" if report.is_consistent else "FLAGS FOUND"
            status_color = Fore.GREEN if report.is_consistent else Fore.RED

            print(f"\n  {Fore.WHITE}{Style.BRIGHT}[{ticker}]{Style.RESET_ALL}  "
                  f"Status: {status_color}{Style.BRIGHT}{status}{Style.RESET_ALL}  "
                  f"Data Confidence: {Fore.WHITE}{report.data_confidence}%{Style.RESET_ALL}")

            if report.flags:
                print(f"  {Fore.YELLOW}Flags:{Style.RESET_ALL}")
                for flag in report.flags:
                    print(f"    {Fore.YELLOW}• {flag}{Style.RESET_ALL}")

            print(f"  {Fore.WHITE}Summary:{Style.RESET_ALL}")
            print(f"    {Fore.WHITE}{_wrap(report.summary)}{Style.RESET_ALL}")

        except Exception as e:
            print(f"  {Fore.RED}[VALIDATOR] Validation failed for {ticker}: {e}{Style.RESET_ALL}")

    print(f"\n{Fore.MAGENTA}{Style.BRIGHT}{'═' * 70}{Style.RESET_ALL}")
