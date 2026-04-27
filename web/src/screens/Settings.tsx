import { useState, useCallback } from "react";
import { Eye, EyeOff, CheckCircle2, XCircle, Loader2 } from "lucide-react";
import { cn } from "../lib/utils";

const PROVIDERS = [
  { key: "anthropic", label: "Anthropic", envVar: "ANTHROPIC_API_KEY" },
  { key: "deepseek", label: "DeepSeek", envVar: "DEEPSEEK_API_KEY" },
  { key: "google", label: "Google", envVar: "GOOGLE_API_KEY" },
  { key: "groq", label: "Groq", envVar: "GROQ_API_KEY" },
  { key: "openai", label: "OpenAI", envVar: "OPENAI_API_KEY" },
  { key: "financial_datasets", label: "Financial Datasets", envVar: "FINANCIAL_DATASETS_API_KEY" },
] as const;

type ProviderStatus = "idle" | "checking" | "ok" | "error";

export function Settings() {
  const [appToken, setAppToken] = useState(
    () => localStorage.getItem("ahf_app_token") ?? "",
  );
  const [providerStatus, setProviderStatus] = useState<
    Record<string, ProviderStatus>
  >({});
  const [showToken, setShowToken] = useState(false);

  const handleTokenSave = useCallback(() => {
    localStorage.setItem("ahf_app_token", appToken);
  }, [appToken]);

  const testProvider = useCallback(async (providerKey: string) => {
    setProviderStatus((prev) => ({ ...prev, [providerKey]: "checking" }));
    try {
      const res = await fetch("/api/healthz");
      if (!res.ok) throw new Error("healthz failed");
      const data = await res.json();
      const configured = data.providers_configured?.[providerKey] ?? false;
      setProviderStatus((prev) => ({
        ...prev,
        [providerKey]: configured ? "ok" : "error",
      }));
    } catch {
      setProviderStatus((prev) => ({ ...prev, [providerKey]: "error" }));
    }
  }, []);

  return (
    <div className="mx-auto max-w-2xl space-y-8">
      <h2 className="text-lg font-semibold">Settings</h2>

      {/* App Token */}
      <section className="rounded-lg border border-border bg-card p-5 space-y-3">
        <h3 className="text-sm font-medium">App Token</h3>
        <p className="text-xs text-muted-foreground">
          Bearer token for authenticating with the server. Leave empty for open
          access (dev mode).
        </p>
        <div className="flex gap-2">
          <div className="relative flex-1">
            <input
              type={showToken ? "text" : "password"}
              value={appToken}
              onChange={(e) => setAppToken(e.target.value)}
              placeholder="Paste token..."
              className="w-full rounded-md border border-input bg-background px-3 py-2 pr-10 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
            />
            <button
              type="button"
              onClick={() => setShowToken(!showToken)}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
            >
              {showToken ? (
                <EyeOff className="h-4 w-4" />
              ) : (
                <Eye className="h-4 w-4" />
              )}
            </button>
          </div>
          <button
            type="button"
            onClick={handleTokenSave}
            className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
          >
            Save
          </button>
        </div>
      </section>

      {/* Providers */}
      <section className="rounded-lg border border-border bg-card p-5 space-y-3">
        <h3 className="text-sm font-medium">Provider Status</h3>
        <p className="text-xs text-muted-foreground">
          Test whether API keys are configured on the server.
        </p>
        <div className="space-y-2">
          {PROVIDERS.map((p) => {
            const status = providerStatus[p.key] ?? "idle";
            return (
              <div
                key={p.key}
                className="flex items-center justify-between rounded-md border border-border px-3 py-2"
              >
                <div>
                  <span className="text-sm font-medium">{p.label}</span>
                  <span className="ml-2 text-xs text-muted-foreground">
                    {p.envVar}
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  {status === "ok" && (
                    <CheckCircle2 className="h-4 w-4 text-green-400" />
                  )}
                  {status === "error" && (
                    <XCircle className="h-4 w-4 text-red-400" />
                  )}
                  {status === "checking" && (
                    <Loader2 className="h-4 w-4 animate-spin text-blue-400" />
                  )}
                  <button
                    type="button"
                    onClick={() => testProvider(p.key)}
                    disabled={status === "checking"}
                    className={cn(
                      "rounded px-2 py-1 text-xs font-medium transition-colors",
                      "border border-border text-muted-foreground hover:bg-accent hover:text-accent-foreground",
                      status === "checking" && "opacity-50 pointer-events-none",
                    )}
                  >
                    Test
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      </section>

      {/* Preferences */}
      <section className="rounded-lg border border-border bg-card p-5 space-y-3">
        <h3 className="text-sm font-medium">Preferences</h3>
        <p className="text-xs text-muted-foreground">
          Default model and analyst preferences are stored in your browser.
        </p>
        <div className="text-xs text-muted-foreground italic">
          Preferences are managed via the Run Configuration and Backtest forms.
        </div>
      </section>
    </div>
  );
}
