import { useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";

interface PriceRow {
  time: string;
  open: number;
  close: number;
  high: number;
  low: number;
  volume: number;
}

interface NewsItem {
  title: string;
  date: string;
  source: string;
  url: string;
  sentiment: string;
}

interface FinancialMetric {
  period: string;
  market_cap: number | null;
  pe_ratio: number | null;
  pb_ratio: number | null;
  revenue_growth: number | null;
}

async function fetchPrices(symbol: string): Promise<PriceRow[]> {
  const res = await fetch(`/api/tickers/${symbol}/prices`);
  if (!res.ok) return [];
  const data = await res.json();
  return data.prices ?? [];
}

async function fetchNews(symbol: string): Promise<NewsItem[]> {
  const res = await fetch(`/api/tickers/${symbol}/news`);
  if (!res.ok) return [];
  const data = await res.json();
  return data.news ?? [];
}

async function fetchMetrics(symbol: string): Promise<FinancialMetric[]> {
  const res = await fetch(`/api/tickers/${symbol}/financial-metrics`);
  if (!res.ok) return [];
  const data = await res.json();
  return data.financial_metrics ?? [];
}

export function Ticker() {
  const { symbol } = useParams<{ symbol: string }>();
  const upperSymbol = symbol?.toUpperCase() ?? "";

  const prices = useQuery({
    queryKey: ["prices", upperSymbol],
    queryFn: () => fetchPrices(upperSymbol),
    enabled: !!upperSymbol,
  });

  const news = useQuery({
    queryKey: ["news", upperSymbol],
    queryFn: () => fetchNews(upperSymbol),
    enabled: !!upperSymbol,
  });

  const metrics = useQuery({
    queryKey: ["metrics", upperSymbol],
    queryFn: () => fetchMetrics(upperSymbol),
    enabled: !!upperSymbol,
  });

  if (!upperSymbol) {
    return (
      <div className="text-muted-foreground text-center py-12">
        No ticker specified.
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <h2 className="text-lg font-semibold">{upperSymbol}</h2>

      {/* Financial Metrics */}
      <section className="rounded-lg border border-border bg-card p-5">
        <h3 className="mb-3 text-sm font-medium text-muted-foreground">
          Financial Metrics
        </h3>
        {metrics.isLoading ? (
          <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
        ) : metrics.data && metrics.data.length > 0 ? (
          <div className="overflow-auto">
            <table className="w-full text-sm">
              <thead className="border-b border-border text-left text-muted-foreground">
                <tr>
                  <th className="px-3 py-2">Period</th>
                  <th className="px-3 py-2">Market Cap</th>
                  <th className="px-3 py-2">P/E</th>
                  <th className="px-3 py-2">P/B</th>
                  <th className="px-3 py-2">Rev Growth</th>
                </tr>
              </thead>
              <tbody>
                {metrics.data.map((m, i) => (
                  <tr key={i} className="border-b border-border last:border-0">
                    <td className="px-3 py-2">{m.period}</td>
                    <td className="px-3 py-2">
                      {m.market_cap
                        ? `$${(m.market_cap / 1e9).toFixed(1)}B`
                        : "-"}
                    </td>
                    <td className="px-3 py-2">
                      {m.pe_ratio?.toFixed(1) ?? "-"}
                    </td>
                    <td className="px-3 py-2">
                      {m.pb_ratio?.toFixed(1) ?? "-"}
                    </td>
                    <td className="px-3 py-2">
                      {m.revenue_growth != null
                        ? `${(m.revenue_growth * 100).toFixed(1)}%`
                        : "-"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-xs text-muted-foreground">No metrics available.</p>
        )}
      </section>

      {/* Prices */}
      <section className="rounded-lg border border-border bg-card p-5">
        <h3 className="mb-3 text-sm font-medium text-muted-foreground">
          Recent Prices
        </h3>
        {prices.isLoading ? (
          <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
        ) : prices.data && prices.data.length > 0 ? (
          <div className="overflow-auto max-h-64">
            <table className="w-full text-sm">
              <thead className="border-b border-border text-left text-muted-foreground">
                <tr>
                  <th className="px-3 py-2">Date</th>
                  <th className="px-3 py-2">Open</th>
                  <th className="px-3 py-2">Close</th>
                  <th className="px-3 py-2">High</th>
                  <th className="px-3 py-2">Low</th>
                  <th className="px-3 py-2">Volume</th>
                </tr>
              </thead>
              <tbody>
                {prices.data.slice(0, 30).map((p, i) => (
                  <tr key={i} className="border-b border-border last:border-0">
                    <td className="px-3 py-2">{p.time?.split("T")[0]}</td>
                    <td className="px-3 py-2">${p.open?.toFixed(2)}</td>
                    <td className="px-3 py-2">${p.close?.toFixed(2)}</td>
                    <td className="px-3 py-2">${p.high?.toFixed(2)}</td>
                    <td className="px-3 py-2">${p.low?.toFixed(2)}</td>
                    <td className="px-3 py-2">
                      {p.volume?.toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-xs text-muted-foreground">No price data.</p>
        )}
      </section>

      {/* News */}
      <section className="rounded-lg border border-border bg-card p-5">
        <h3 className="mb-3 text-sm font-medium text-muted-foreground">
          News
        </h3>
        {news.isLoading ? (
          <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
        ) : news.data && news.data.length > 0 ? (
          <div className="space-y-3">
            {news.data.slice(0, 20).map((n, i) => (
              <div
                key={i}
                className="border-b border-border pb-2 last:border-0"
              >
                <a
                  href={n.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-sm font-medium text-primary hover:underline"
                >
                  {n.title}
                </a>
                <div className="mt-0.5 text-xs text-muted-foreground">
                  {n.source} - {n.date?.split("T")[0]}
                  {n.sentiment && (
                    <span className="ml-2 italic">{n.sentiment}</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-xs text-muted-foreground">No news available.</p>
        )}
      </section>
    </div>
  );
}
