#!/usr/bin/env python3
"""打印所有数据源的 API URL，用于浏览器测试"""

def print_urls():
    ticker = "000001"  # 平安银行
    start_date = "2026-03-10"
    end_date = "2026-03-14"

    print("=" * 80)
    print("📋 所有数据源 API URL")
    print("=" * 80)
    print(f"\n测试股票: {ticker} (平安银行)")
    print(f"日期范围: {start_date} 到 {end_date}")

    # Eastmoney - 财务指标
    print("\n" + "=" * 80)
    print("1️⃣  Eastmoney - 财务指标")
    print("=" * 80)
    eastmoney_finance = f"https://push2.eastmoney.com/api/qt/stock/get?secid=0.{ticker}&fields=f43,f116,f117,f162,f167,f173,f187"
    print(f"\nURL: {eastmoney_finance}")
    print("\n预期返回: 市值、PE、PB、ROE 等")
    print("需要 cookies: 是")

    # Eastmoney - K线数据
    print("\n" + "=" * 80)
    print("2️⃣  Eastmoney - K线价格数据")
    print("=" * 80)
    eastmoney_kline = f"https://push2his.eastmoney.com/api/qt/stock/kline/get?secid=0.{ticker}&fields1=f1,f2,f3,f4,f5,f6&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61&klt=101&fqt=1&beg={start_date.replace('-', '')}&end={end_date.replace('-', '')}"
    print(f"\nURL: {eastmoney_kline}")
    print("\n预期返回: 开高低收、成交量等")
    print("需要 cookies: 是")

    # Tushare
    print("\n" + "=" * 80)
    print("3️⃣  Tushare Pro")
    print("=" * 80)
    print("\nAPI 类型: Python SDK (非 HTTP)")
    print("需要: TUSHARE_TOKEN 环境变量")
    print("注册: https://tushare.pro/register")
    print("状态: ❌ 当前无 token")

    # AKShare
    print("\n" + "=" * 80)
    print("4️⃣  AKShare")
    print("=" * 80)
    print("\nAPI 类型: Python 库 (内部使用多个数据源)")
    print("数据来源: 东方财富、新浪财经等")
    print("状态: ⚠️  网络连接不稳定")

    # Sina Finance
    print("\n" + "=" * 80)
    print("5️⃣  Sina Finance")
    print("=" * 80)
    sina_url = f"http://hq.sinajs.cn/list=sz{ticker}"
    print(f"\nURL: {sina_url}")
    print("\n预期返回: 实时行情数据")
    print("需要 cookies: 否")

    # YFinance
    print("\n" + "=" * 80)
    print("6️⃣  YFinance")
    print("=" * 80)
    yfinance_url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}.SZ"
    print(f"\nURL: {yfinance_url}")
    print("\n预期返回: 历史价格数据")
    print("需要 cookies: 否")
    print("状态: ⚠️  限流严重 (429 错误)")

    # 测试命令
    print("\n" + "=" * 80)
    print("🧪 测试命令")
    print("=" * 80)

    print("\n1. Eastmoney 财务指标 (需要 cookies):")
    print(f"curl '{eastmoney_finance}' \\")
    print("  -b 'qgqp_b_id=815f755023542909e5d7e12bb425b596; st_nvi=ScjgG2HuISz39_tWj_aok2a2e; nid18=09eb187f79dc909ec16bdbde4b035e7c; nid18_create_time=1772700178728; gviem=a_KccyxJy-mrAKnziDt975b61; gviem_create_time=1772700178728; mtp=1' \\")
    print("  -H 'User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'")

    print("\n2. Eastmoney K线数据 (需要 cookies):")
    print(f"curl '{eastmoney_kline}' \\")
    print("  -b 'qgqp_b_id=815f755023542909e5d7e12bb425b596; st_nvi=ScjgG2HuISz39_tWj_aok2a2e; nid18=09eb187f79dc909ec16bdbde4b035e7c; nid18_create_time=1772700178728; gviem=a_KccyxJy-mrAKnziDt975b61; gviem_create_time=1772700178728; mtp=1' \\")
    print("  -H 'User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'")

    print("\n3. Sina Finance (无需 cookies):")
    print(f"curl '{sina_url}'")

    print("\n4. YFinance (无需 cookies):")
    print(f"curl '{yfinance_url}'")

    print("\n" + "=" * 80)
    print("📝 浏览器测试")
    print("=" * 80)
    print("\n请在浏览器中访问以下 URL:")
    print(f"\n1. {eastmoney_finance}")
    print(f"\n2. {eastmoney_kline}")
    print(f"\n3. {sina_url}")
    print(f"\n4. {yfinance_url}")

    print("\n" + "=" * 80)
    print("⚠️  注意事项")
    print("=" * 80)
    print("\n1. Eastmoney URL 需要在登录后访问（需要 cookies）")
    print("2. 如果浏览器中无法访问，检查:")
    print("   - 是否已登录东方财富网站")
    print("   - 浏览器是否阻止了跨域请求")
    print("3. Sina 和 YFinance 应该可以直接访问")

if __name__ == "__main__":
    print_urls()
