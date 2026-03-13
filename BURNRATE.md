```
╔═══════════════════════════════════════════════════════════════════════════════╗
║                                                                               ║
║     ██████╗ ██╗   ██╗██████╗ ███╗   ██╗██████╗  █████╗ ████████╗███████╗       ║
║     ██╔══██╗██║   ██║██╔══██╗████╗  ██║██╔══██╗██╔══██╗╚══██╔══╝██╔════╝       ║
║     ██████╔╝██║   ██║██████╔╝██╔██╗ ██║██████╔╝███████║   ██║   █████╗         ║
║     ██╔══██╗██║   ██║██╔══██╗██║╚██╗██║██╔══██╗██╔══██║   ██║   ██╔══╝         ║
║     ██████╔╝╚██████╔╝██║  ██║██║ ╚████║██║  ██║██║  ██║   ██║   ███████╗       ║
║     ╚═════╝  ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═══╝╚═╝  ╚═╝╚═╝  ╚═╝   ╚═╝   ╚══════╝       ║
║                                                                               ║
║     The benchmark.  No substitute.                                            ║
║                                                                               ║
║     From 2-and-20 to run rate.  Precision.  No noise.  Just the signal.       ║
║                                                                               ║
╚═══════════════════════════════════════════════════════════════════════════════╝
```

# Burn Rate — 2-and-20, the Bench, and What a Real Fund Costs

## TLDR — The Quant Business Plan in One Table

This is a business plan that runs the numbers, not one that tells a story and hopes the math works out later. Every line below is derived from the cost model in this document.

```
╔════════════════════════════════════════════════════════════════════════════════╗
║  REVENUE                                                                        ║
║    AUM at launch                          $21,000,000                            ║
║    Management fee (2%)                       $420,000 / year                     ║
║    Performance fee (20%)                     variable  (not in base model)        ║
║                                                                                  ║
║  BURN (ANNUAL)                             Low        Base       High            ║
║    Legal / ops / admin / audit              $58,000    $85,000    $119,000        ║
║    Salaries                                $210,000   $210,000    $210,000        ║
║    ──────────────────────────────────────────────────────────────              ║
║    Total burn                              $268,000   $295,000    $329,000        ║
║    Monthly burn                             $22,333    $24,583     $27,417        ║
║                                                                                  ║
║  MARGIN (management fee − burn)                                                  ║
║    Annual buffer                           $152,000   $125,000     $91,000        ║
║    Buffer as % of revenue                    36.2%      29.8%       21.7%         ║
║                                                                                  ║
║  SELF-FUNDING VIA WHEEL (Hypersurface, BTC + HYPE puts)                          ║
║    Planning rate (conservative)              50% APR    =          4.17%/mo        ║
║    Proven rate (this week)                  113% APR    =          ~9.5%/mo         ║
║    Collateral to cover base burn ($24.6K)   $590,000   (50% APR)  $295,000         ║
║    ≈ BTC equivalent at $70K spot            8.43 BTC              4.21 BTC         ║
║                                                                                  ║
║  BREAK-EVEN AUM (burn ÷ 0.02)             $13.4M     $14.75M     $16.45M         ║
║                                                                                  ║
║  SIMPLE LLC ALTERNATIVE (no outside investors)                                   ║
║    Ops burn (no fund infra)                  $9,450     $18,500     $32,600       ║
║    + Salaries                               $210,000   $210,000    $210,000       ║
║    Total burn                               $219,450   $228,500    $242,600       ║
║    Monthly burn                              $18,288    $19,042     $20,217       ║
║    Wheel collateral (base, 50% APR)               —       ~$457,000       —          ║
║    Savings vs. fund                             —       $66,500/yr      —          ║
║                                                                                  ║
║  MINIMUM VIABLE (LLC + Fairmint, no salaries)                                    ║
║    Ops-only burn                               $14,450    $27,000     $44,600     ║
║    Monthly                                      $1,204     $2,250      $3,717     ║
║    Wheel collateral (base, 50% APR)                —      ~$54,000         —       ║
║    Wheel collateral (base, 100% APR)               —      ~$27,000         —       ║
║                                                                                  ║
║  VERDICT                                                                         ║
║    Fund: cash-flow positive at $21M AUM from day one.                            ║
║    Simple LLC + salaries: ~$457K (50% APR) or ~$229K (100% APR).                 ║
║    Minimum viable (no salaries): ~$54K at 50% APR covers all ops.                ║
║    Planning at 50% APR gives cushion. 100%+ APR is proven upside.                ║
╚════════════════════════════════════════════════════════════════════════════════╝
```

The rest of this document shows the work: what 2-and-20 means, why the Bench replaces the research those fees paid for, the Delaware LLC structure, a six-part cost breakdown, the wheel strategy sizing, and a paste-into-Sheets model so you can stress-test every assumption yourself.

---

## 1. What “2-and-20” Means

**2-and-20** (or “two and twenty”) is the standard fee structure many traditional hedge funds charge:

| Component | Meaning |
|-----------|--------|
| **2% management fee** | Every year the fund takes 2% of **assets under management (AUM)**. Paid regardless of performance. |
| **20% performance fee** | The fund keeps 20% of **profits** (often above a hurdle or benchmark). |

**Example:** On $100M AUM, the management fee alone is $2M per year—to the managers—whether the fund is up or down. On top of that, 20% of any gains goes to the manager. So “2-and-20” is shorthand for: high fees, managers get rich, investors pay heavily.

---

## 2. The Punchline: The Bench vs. the Black Box

The line you see in the wild—

> *“Just AI agents doing the kind of research hedge funds charge 2-and-20 for.”*

—refers to systems like the Bench: 18 specialized agents (value, growth, momentum, technicals, etc.) doing the same style of deep, multi-perspective research that funds have long charged 2-and-20 for.

The punchline:

- **No 2% drag.** No $25K minimums. No advisor wrap fees. Run it on a laptop; the “fee” is compute and API cost.
- **The expensive Wall Street black box is being replaced by open AI agents.** The research that used to justify 2-and-20 is now available at marginal cost.

This doc does **not** argue you should or shouldn’t run a fund. It states: if you go from “Bench on a laptop” to “actual fund vehicle with investors,” the following run rate is what you are signing up for.

---

## 3. Why This Document Exists

The Bench is the committee. It holds the bar. It does not hold the fund entity.

If you launch a **real fund**—Delaware LLC, accredited investors, custody, audit, compliance—you face fixed and variable costs that have nothing to do with the quality of the research. This section and the rest of the document quantify that: structure, assumptions, cost breakdown, and a build-your-own model so the burn rate is explicit.

---

## 4. Structure: Delaware LLC + Tokenized Interests

Launching a hedge fund as a **Delaware limited liability company** is a common and legally sound choice, including for crypto-native strategies that want flexible governance and onchain tooling.

With **$21M AUM** at or before launch (e.g. via Reg D private placement to accredited investors), a Delaware LLC gives:

- **Pass-through taxation** (partnership election, Form 1065).
- **Limited liability** for members.
- **Operational simplicity** compared with a traditional LP/GP setup.

The **fund vehicle** holds investor membership interests. A **separate Delaware LLC** acts as the management company.

To streamline **compliance, onboarding, cap-table management, and secondary transfers**, this structure uses **Fairmint** (fairmint.com), an SEC-registered transfer agent built for onchain equity. Fairmint issues **tokenized LLC membership interests** into investors’ wallets via the **Open Cap Table Protocol (OCP)**. That removes paper cap tables, reduces the need for multiple SPVs, automates KYC/KYB/AML and accreditation, and produces **audit-ready, blockchain-verified** transaction history within U.S. securities law. For a fund managed from Switzerland, Fairmint’s borderless transfer capability is useful; it does **not** replace fund administration (NAV, portfolio accounting, custody).

---

## 5. Key Assumptions

| Assumption | Value | Notes |
|------------|--------|--------|
| **Structure** | Delaware LLC fund + separate management LLC | Tokenized interests via Fairmint |
| **Strategy** | Crypto/DeFi (digital assets, DeFi, tokenized securities) | |
| **Manager location** | Switzerland | Cross-border tax and potential FINMA considerations |
| **Investors** | 15–40 accredited at launch | |
| **Fees** | 2% management + 20% performance | |
| **Launch year** | 2026 | Mid-range market estimates for $10–50M AUM band |
| **First year** | 20–40% higher cost | Setup and onboarding front-loaded |

At **$21M AUM**, a **2% management fee** = **$420,000/year** revenue—enough to cover all operating costs with margin left. Performance fees are not included in the cost model below.

---

## 6. Cost Breakdown

### 6.1 Entity Maintenance and Delaware Compliance — $1,000–$2,000/year

- Annual franchise tax: **$300 per LLC** (due June 1).
- Registered agent: **$150–$300 per entity**.
- **Two entities** (Fund LLC + Management LLC): **$900–$1,800/year**.

Fairmint’s onchain cap table aligns with Delaware filings and reduces manual updates when investors are added or transferred.

---

### 6.2 Legal, Compliance, and Securities Retainer — $15,000–$33,000/year (ongoing); $25,000–$45,000 first year

- **Base retainer** (PPM maintenance, Form D amendments, SEC monitoring): **$8,000–$15,000**.
- **Investor docs and transfer-agent work:** Traditionally **$10,000–$25,000**; with Fairmint’s issuance and compliance automation, **$2,000–$8,000** (e.g. operating-agreement customization or Swiss cross-border opinions).
- **Cross-border / Swiss counsel** (U.S. tax + AIFMD/FINMA): **$5,000–$10,000**.
- **One-time launch** (Fairmint integration + initial tokenized issuance): **$5,000–$12,000**, included in first-year total.

Without Fairmint, ongoing legal would be roughly **$20,000–$50,000**. The platform’s automation cuts about **25–35%** from this line.

---

### 6.3 Fund Administration and Investor Services — $28,000–$57,000/year

**Hybrid model:** Fairmint for the **investor-facing layer** (onchain cap table, transfers, portfolio visibility); a **crypto-specialist administrator** for NAV, books, reconciliation, and performance reporting.

| Component | Range | Notes |
|-----------|--------|--------|
| Traditional admin (NAV, books, reporting, wallet reconciliation) | $18,000–$35,000 | ~0.15–0.20% of $21M or $2.5–3K/month minimums |
| Fairmint (cap table, KYC, transfers, dashboard) | $5,000–$12,000/year | Replaces an estimated $10K–$30K in legacy transfer-agent/admin work |
| Crypto extras (Fireblocks/Anchorage, wallet monitoring, DeFi yield) | $5,000–$10,000 | |

This hybrid yields roughly **20–30%** savings versus a traditional-only admin at this AUM, with tokenized infrastructure suited to institutional scaling.

---

### 6.4 Annual Audit and Tax Preparation — $26,000–$45,000/year

- **Financial audit** (Big 4 or crypto specialist): **$18,000–$32,000** (blockchain tracing, ASC 820, custody confirmations).
- **Tax** (Form 1065 + K-1s, foreign reporting as applicable): **$10,000–$18,000**.
- **Fairmint:** Onchain, audit-ready transaction history can trim audit fees by **$2,000–$5,000** (capital-account and membership tracing).

First-year audit is often **10–15%** higher for initial setup.

---

### 6.5 Insurance, Custody, Software, and Miscellaneous — $20,000–$42,000/year

| Item | Range |
|------|--------|
| D&O / E&O insurance | $8,000–$15,000 |
| Crypto custody / prime (e.g. Coinbase Prime, Fireblocks) | $5,000–$12,000 |
| Accounting + crypto tools (e.g. QuickBooks, Cryptio) | $3,000–$6,000 |
| Blue-sky (minimal under Reg D) | $2,000–$4,000 |
| Banking, data, cybersecurity | $2,000–$5,000 |

---

### 6.6 Switzerland Cross-Border Overlay — $8,000–$15,000/year

- U.S./Swiss tax coordination and FATCA/CRS reporting.
- Swiss wealth-management licensing considerations if marketing to local investors.
- Multi-jurisdictional banking and currency considerations.

Usually handled with U.S. counsel and Swiss input; treated as a predictable annual overlay.

---

## 7. Total Cost Summary

| Scenario | Recurring (Years 2+) | First-Year Total |
|----------|----------------------|-------------------|
| **Low** | $58,000 | $85,000 |
| **Base (most likely)** | ~$85,000 | ~$120,000 |
| **High** | $119,000 | $165,000 |

**As % of $21M AUM:** 0.28% – 0.40% – 0.57%.

**Buffer after 2% management fee ($420,000):** ~$302,000 – $335,000 – $362,000 (recurring).

Approximate allocation:

- Administration + Fairmint: **~35%**
- Audit + Tax: **~30%**
- Legal + Compliance: **~20%**
- Entity + Insurance + Misc: **~15%**

At $21M AUM, all-in operating cost is **0.28%–0.57%** of assets. The 2% management fee covers it with **$300K+** remaining before any performance fee.

---

## 8. Risks and Optimization

| Risk / lever | Comment |
|--------------|--------|
| **Scale threshold** | Below ~$15M AUM, fixed costs bite. $21M is a workable sweet spot where the management fee funds operations with margin. |
| **Crypto volatility** | Audit and custody can rise with complex DeFi or high turnover. Budget **10–15%** contingency on those lines. |
| **Regulatory growth** | Above ~$150M AUM, SEC registration adds on the order of **$5K–$10K** (Form ADV, etc.)—manageable. |
| **Fairmint upside** | Secondary liquidity for tokenized interests could improve stickiness and reduce churn-related admin—not baked into the numbers above. |

---

## 9. Strategy Size to Cover Burn: Wheel (BTC + HYPE on Hypersurface)

One way to **cover the fund's total monthly burn** from trading income is the **wheel strategy**: cash-secured puts on **BTC** (and **HYPE**) on **Hypersurface**, with stablecoin collateral (e.g. USDT0) earning premium and, if assigned, acquiring spot at an effective discount. The math below adds **$210K in annual salaries** to the legal/ops run rate and calculates **how much collateral** the wheel needs to cover the full monthly cost.

### Total Burn Rate (Legal/Ops + Salaries)

The fund doesn't just pay legal and admin. It pays people. Adding **$210,000/year in salaries** ($17,500/month) to the operating costs from §7:

| Component | Low | Base | High |
|-----------|-----|------|------|
| Legal / ops (from §7) | $58,000 | ~$85,000 | $119,000 |
| Salaries | $210,000 | $210,000 | $210,000 |
| **Total annual burn** | **$268,000** | **~$295,000** | **$329,000** |
| **Monthly burn** | **~$22,333** | **~$24,583** | **~$27,417** |

This is the number the wheel needs to cover.

### Wheel Strategy Assumptions (BTC + HYPE, Hypersurface)

The yield rates below are derived from **APR**, not from a fixed dollar example. We plan at **50% APR** (conservative) to give the strategy cushion for weeks with lower premiums, while noting that **100%+ APR is proven** — e.g. the $70,500-strike BTC secured put expiring 3/20/26 printed at **113.86% APR** on Hypersurface this week.

| Rate | APR | Monthly yield | Basis |
|------|-----|---------------|-------|
| **Conservative (planning rate)** | **50%** | **4.17%/mo** | Half the proven rate — cushion for consistency |
| **Proven (this week)** | **113.86%** | **~9.5%/mo** | Actual fill on BTC secured put, $70,500 strike, 3/20/26 exp |

- **If assigned:** You are long BTC (or HYPE) at an effective cost basis **below** spot (premium reduces cost). Not a loss — acquiring a hard asset at a pre-negotiated price with yield on collateral in the meantime.

### Collateral Required to Cover Full Monthly Burn

*(required collateral) = (monthly burn) ÷ (monthly yield rate)*

| Monthly burn | 50% APR (4.17%/mo) | 100% APR (8.33%/mo) |
|--------------|--------------------|-----------------------|
| **Low** (~$22,333) | **~$536,000** | **~$268,000** |
| **Base** (~$24,583) | **~$590,000** | **~$295,000** |
| **High** (~$27,417) | **~$658,000** | **~$329,000** |

Formula: *collateral = monthly burn / monthly yield* (e.g. $24,583 / 0.0417 ≈ $590K).

### What This Means in BTC (at ~$70K spot)

| Monthly burn | 50% APR collateral | ≈ BTC equivalent | 100% APR collateral | ≈ BTC equivalent |
|--------------|--------------------|--------------------|----------------------|--------------------|
| **Low** | ~$536K | **~7.66 BTC** | ~$268K | **~3.83 BTC** |
| **Base** | ~$590K | **~8.43 BTC** | ~$295K | **~4.21 BTC** |
| **High** | ~$658K | **~9.40 BTC** | ~$329K | **~4.70 BTC** |

These are the **notional size** the wheel needs to be writing puts against so that premium income covers the full burn (legal + salaries).

### Takeaway

- At **base burn** (~$24,583/month), you need about **$590K** collateral at the 50% APR planning rate, or about **$295K** if the wheel runs closer to the proven 100%+ APR.
- Planning at **50% APR** means you can underperform the proven rate by half and still cover every bill. Weeks that print 100%+ APR build surplus and accelerate BTC accumulation.
- The wheel is **income to pay the burn** — not a replacement for the 2% management fee. It's how the structure becomes self-sustaining from strategy P&L while the Bench does the research and the fund holds the costs.
- Assignment is not a loss. Premium reduces effective cost basis below spot. The wheel accumulates hard assets at a discount while generating the income stream that funds operations.

---

## 10. Alternative: Simple Trading LLC (No Outside Investors)

What if you skip the hedge fund entirely? A **simple Delaware LLC** that writes covered calls and cash-secured puts for cashflow, holds BTC, and pays its team — but takes **no outside investor capital** — is a fundamentally different structure. Most of the fund-grade costs disappear because there are no investors to report to, no securities to register, and no auditor to satisfy.

### What Goes Away

| Fund cost (from §6) | Why it disappears |
|----------------------|-------------------|
| Fund administration ($28K–$57K) | No NAV, no investor reporting, no capital calls |
| Fairmint / transfer agent ($5K–$12K) | No tokenized membership interests, no cap table |
| PPM, Form D, securities compliance ($8K–$15K) | No securities offering — no investors |
| Investor K-1s (bulk of tax prep) | Single- or few-member LLC — one return, no K-1 distribution |
| Financial audit ($18K–$32K) | No institutional investors demanding audited statements |
| Swiss cross-border investor overlay ($8K–$15K) | No marketing to investors — just managing your own capital |
| D&O/E&O insurance ($8K–$15K) | Optional at much lower premium — no fiduciary duty to LPs |

### What Remains

| Line item | Low | Base | High | Notes |
|-----------|-----|------|------|-------|
| Entity maintenance (1 LLC) | $450 | $500 | $600 | Franchise tax + registered agent |
| Legal (operating agreement, tax counsel) | $3,000 | $5,000 | $8,000 | Annual review, no PPM or Form D |
| Tax preparation (Form 1065 or Sched C) | $2,000 | $3,000 | $5,000 | No investor K-1s |
| Crypto custody (Coinbase Prime, etc.) | $2,000 | $4,000 | $8,000 | AUM-tiered; smaller at prop scale |
| Accounting / bookkeeping software | $1,000 | $2,000 | $3,000 | QuickBooks + crypto tracker |
| Insurance (optional) | $0 | $2,000 | $5,000 | E&O optional without LPs |
| Banking / misc | $1,000 | $2,000 | $3,000 | |
| **Subtotal ops** | **$9,450** | **$18,500** | **$32,600** | |
| Salaries | $210,000 | $210,000 | $210,000 | Same team |
| **Total annual burn** | **$219,450** | **$228,500** | **$242,600** | |
| **Monthly burn** | **~$18,288** | **~$19,042** | **~$20,217** | |

### Side-by-Side: Fund vs. Simple LLC

| | Hedge Fund (§9) | Simple Trading LLC |
|---|---|---|
| Annual ops (base) | ~$85,000 | ~$18,500 |
| + Salaries | $210,000 | $210,000 |
| **Total burn (base)** | **~$295,000** | **~$228,500** |
| **Monthly burn** | **~$24,583** | **~$19,042** |
| Savings vs. fund | — | **~$66,500/year (~$5,542/month)** |

The simple LLC cuts **~$66K/year** in overhead — almost entirely by removing investor-facing infrastructure.

### Wheel Collateral to Cover Simple-LLC Burn

Same APR-based yield assumptions (50% APR = 4.17%/mo, 100% APR = 8.33%/mo):

| Monthly burn | 50% APR (4.17%/mo) | 100% APR (8.33%/mo) |
|--------------|--------------------|-----------------------|
| **Low** (~$18,288) | **~$439,000** | **~$219,000** |
| **Base** (~$19,042) | **~$457,000** | **~$229,000** |
| **High** (~$20,217) | **~$485,000** | **~$243,000** |

### What This Means (with salaries)

- At **base burn** (~$19K/month), the wheel needs **~$457K** at the 50% APR planning rate, or **~$229K** if it runs closer to the proven 100%+ APR.
- The gap between "fund" and "simple LLC" is **~$5,500/month**. That's the price of investor infrastructure. If the plan is to trade your own capital and pay a team, the simple LLC is the correct vehicle until outside capital becomes worth the compliance overhead.
- **When to upgrade:** If you want to take outside money, the fund structure from §4–§8 kicks in. Until then, the simple LLC lets you run the same wheel strategy, hold BTC, and pay salaries with a burn rate that's **23% lower** than the fund.

---

### Minimum Viable Capital: LLC + Fairmint, No Salaries

Strip it to the bone. No team salary — just the entity, Fairmint for onchain cap-table readiness, and the minimum legal/ops to keep the LLC compliant and trading. This is the floor: **how much wheel capital does the strategy itself need to be self-sustaining?**

| Line item | Low | Base | High |
|-----------|-----|------|------|
| Entity maintenance (1 LLC) | $450 | $500 | $600 |
| Legal (operating agreement, tax counsel) | $3,000 | $5,000 | $8,000 |
| Tax preparation | $2,000 | $3,000 | $5,000 |
| Crypto custody | $2,000 | $4,000 | $8,000 |
| Accounting / bookkeeping | $1,000 | $2,000 | $3,000 |
| Fairmint (cap table, KYC, transfers) | $5,000 | $8,500 | $12,000 |
| Insurance (optional) | $0 | $2,000 | $5,000 |
| Banking / misc | $1,000 | $2,000 | $3,000 |
| **Total annual ops** | **$14,450** | **$27,000** | **$44,600** |
| **Monthly ops** | **~$1,204** | **~$2,250** | **~$3,717** |

#### Wheel Collateral to Cover Ops-Only Burn

| Monthly ops | 50% APR (4.17%/mo) | 100% APR (8.33%/mo) |
|-------------|--------------------|-----------------------|
| **Low** (~$1,204) | **~$28,900** | **~$14,400** |
| **Base** (~$2,250) | **~$54,000** | **~$27,000** |
| **High** (~$3,717) | **~$89,200** | **~$44,600** |

#### The Punchline

- At **base ops** ($27K/year, $2,250/month), the wheel needs **~$54K** at 50% APR or **~$27K** at the proven 100% APR to pay every bill the LLC generates.
- That's **~0.39 BTC** (100% APR) to **~0.77 BTC** (50% APR) at $70K spot — less than 1 BTC worth of collateral to keep the entire structure running.
- Planning at 50% APR means you can underperform the proven rate by half and still cover ops. Weeks that print 100%+ APR (like the 113.86% BTC put this week) build surplus for BTC accumulation or future salary capacity.
- Fairmint adds **$5K–$12K/year** to the bare LLC but keeps the cap table onchain and investor-ready from day one. When you do bring in outside capital, the infrastructure is already live — no retrofit, no paper migration.

This is the minimum viable fund infrastructure: a Delaware LLC, Fairmint, and **~$54K** in wheel collateral at 50% APR. Everything above that is margin.

---

## 11. Google Sheets Cost Model — Build Guide

The tables below paste into **Google Sheets** for a formula-driven model.

**Setup:** New spreadsheet → name e.g. *“21M Crypto Hedge Fund LLC Cost Model 2026 – Fairmint”* → four sheets: **Assumptions**, **Cost Breakdown**, **Summary Dashboard**, **Sensitivity Analysis**. Paste each table into the matching sheet starting at **A1**. Format: bold headers, currency for $ columns, % for percent, freeze rows 1–3.

---

### Tab 1: Assumptions

| A | B |
|---|---|
| **KEY ASSUMPTIONS** | |
| Target AUM at Launch | $21,000,000 |
| Management Fee | 2% |
| Performance Fee | 20% |
| Number of Investors | 25 |
| Strategy | Crypto/DeFi |
| Manager Location | Switzerland |
| Structure | Delaware LLC Fund + Management LLC + Fairmint |
| Launch Year | 2026 |
| First-Year Multiplier | 1.3 |

---

### Tab 2: Cost Breakdown

| Category / Line Item | Low | Base | High |
|----------------------|-----|------|------|
| **1. Entity Maintenance** | | | |
| Franchise Tax (2 LLCs) | $900 | $1,200 | $1,800 |
| Registered Agent (2 entities) | $300 | $400 | $600 |
| *Subtotal Entity* | =SUM(B3:B4) | =SUM(C3:C4) | =SUM(D3:D4) |
| **2. Legal / Compliance** | | | |
| Base retainer + Form D | $8,000 | $11,500 | $15,000 |
| Fairmint integration + docs | $2,000 | $5,000 | $8,000 |
| Swiss cross-border counsel | $5,000 | $7,500 | $10,000 |
| *Subtotal Legal* | =SUM(B8:B10) | =SUM(C8:C10) | =SUM(D8:D10) |
| **3. Administration + Fairmint** | | | |
| Crypto admin (NAV, books, reporting) | $18,000 | $26,500 | $35,000 |
| Fairmint (cap table, KYC, transfers) | $5,000 | $8,500 | $12,000 |
| Crypto custody + wallet monitoring | $5,000 | $8,000 | $10,000 |
| *Subtotal Admin* | =SUM(B14:B16) | =SUM(C14:C16) | =SUM(D14:D16) |
| **4. Audit + Tax** | | | |
| Financial audit (crypto specialist) | $18,000 | $25,000 | $32,000 |
| Tax prep (1065 + K-1s) | $10,000 | $14,000 | $18,000 |
| *Subtotal Audit/Tax* | =SUM(B20:B21) | =SUM(C20:C21) | =SUM(D20:D21) |
| **5. Insurance + Misc** | | | |
| D&O/E&O Insurance | $8,000 | $11,500 | $15,000 |
| Crypto prime brokerage | $5,000 | $8,500 | $12,000 |
| Software + blue-sky | $5,000 | $7,000 | $9,000 |
| *Subtotal Insurance/Misc* | =SUM(B26:B28) | =SUM(C26:C28) | =SUM(D26:D28) |
| **6. Switzerland Overlay** | $8,000 | $11,500 | $15,000 |
| **GRAND TOTAL (Recurring)** | =SUM(B6,B11,B17,B22,B29,B31) | =SUM(C6,C11,C17,C22,C29,C31) | =SUM(D6,D11,D17,D22,D29,D31) |
| **First-Year Total (×1.3)** | =B33*1.3 | =C33*1.3 | =D33*1.3 |
| **As % of AUM** | =B33/21000000 | =C33/21000000 | =D33/21000000 |
| **Buffer vs. Management Fee** | =420000−B33 | =420000−C33 | =420000−D33 |

Row numbers (6, 11, 17, 22, 29, 31) assume each Subtotal row is in that position; adjust to match your sheet.

---

### Tab 3: Summary Dashboard

Reference the Cost Breakdown sheet (e.g. `='Cost Breakdown'!C33`).

| A | B |
|---|---|
| Recurring Annual Cost (Base) | ='Cost Breakdown'!C33 |
| First-Year Total | ='Cost Breakdown'!C34 |
| % of AUM (Base) | ='Cost Breakdown'!C35 |
| Management Fee Revenue | $420,000 |
| Buffer After Costs | =420000−'Cost Breakdown'!C33 |
| Break-Even AUM | ='Cost Breakdown'!C33/0.02 |

Add a column chart: Low/Base/High annual totals from Cost Breakdown row 33.

---

### Tab 4: Sensitivity Analysis

| A | B ($10M) | C ($21M) | D ($50M) |
|---|----------|----------|----------|
| AUM Scenario | $10,000,000 | $21,000,000 | $50,000,000 |
| Total Cost (Base) | ='Cost Breakdown'!C33×0.85 | ='Cost Breakdown'!C33 | ='Cost Breakdown'!C33×1.25 |
| % of AUM | =B3/B2 | =C3/C2 | =D3/D2 |

Shows how cost scales with AUM; many items are semi-fixed until ~$50M, so $21M is an efficient point.

---

## 12. Conclusion

╭─────────────────────────────────────────────────────────────────────────────────╮
║  The only measure that matters is beating the bar.                              ║
║  The Bench does the research.  The fund vehicle pays the burn rate.              ║
╰─────────────────────────────────────────────────────────────────────────────────╯

A Delaware LLC crypto fund at **$21M AUM** with **Fairmint**-based tokenized membership is cost-efficient and built for compliance and scale. Recurring costs sit in the **$58K–$119K** band (**0.28%–0.57%** of AUM), leaving **$300K+** from the management fee before performance fees.

Fairmint’s onchain setup (no SPVs, automated compliance, instant transfers, audit trail) cuts cost versus legacy structures and positions the fund for secondary liquidity and institutional adoption.

**Recommended next steps:**

1. Build the Google Sheets model above (~10 minutes).
2. Share with Delaware counsel and a crypto fund administrator for review.
3. Contact Fairmint (fairmint.com → Contact) for pricing for your AUM and investor count.
