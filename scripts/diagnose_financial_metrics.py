#!/usr/bin/env python3
"""
财务指标数据诊断工具

用于诊断和修复财务指标表中的null值问题

使用方法:
    poetry run python scripts/diagnose_financial_metrics.py
"""
import json
import sys
from pathlib import Path
from decimal import Decimal

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.database.connection import SessionLocal
from src.data.mysql_models import FinancialMetric


def analyze_null_values():
    """分析财务指标表中的null值"""
    print("="*80)
    print("财务指标数据诊断报告")
    print("="*80)

    db = SessionLocal()
    try:
        # 1. 统计总体情况
        from sqlalchemy import func

        total = db.query(func.count(FinancialMetric.id)).scalar()
        print(f"\n📊 总记录数: {total}")

        if total == 0:
            print("⚠️  数据表为空，请先运行系统生成一些数据")
            return

        # 2. 统计null值情况
        print("\n🔍 Null值统计:")

        fields = ['ps_ratio', 'revenue', 'net_income', 'market_cap', 'pe_ratio', 'pb_ratio']
        null_stats = {}

        for field in fields:
            null_count = db.query(func.count(FinancialMetric.id)).filter(
                getattr(FinancialMetric, field) == None
            ).scalar()
            null_stats[field] = null_count
            percentage = (null_count / total * 100) if total > 0 else 0
            status = "❌" if null_count > 0 else "✅"
            print(f"  {status} {field:20} null数: {null_count:4} ({percentage:.1f}%)")

        # 3. 检查metrics_json
        null_metrics_json = db.query(func.count(FinancialMetric.id)).filter(
            FinancialMetric.metrics_json == None
        ).scalar()
        print(f"\n  {'✅' if null_metrics_json == 0 else '❌'} metrics_json        null数: {null_metrics_json:4}")

        # 4. 分析原因
        print("\n🔎 原因分析:")

        # 查询所有记录
        records = db.query(FinancialMetric).all()

        for record in records:
            print(f"\n记录 #{record.id}: {record.ticker}")
            print(f"  数据源: {record.data_source}")
            print(f"  报告期: {record.report_period}")

            # 检查数据库字段
            print(f"\n  数据库字段值:")
            print(f"    pe_ratio:   {record.pe_ratio}")
            print(f"    pb_ratio:   {record.pb_ratio}")
            print(f"    ps_ratio:   {record.ps_ratio}")
            print(f"    revenue:    {record.revenue}")
            print(f"    net_income: {record.net_income}")
            print(f"    market_cap: {record.market_cap}")

            # 检查metrics_json中的值
            if record.metrics_json:
                print(f"\n  metrics_json中的值:")
                json_data = record.metrics_json

                # 检查关键字段
                key_fields = {
                    'price_to_sales_ratio': 'ps_ratio',
                    'revenue': 'revenue',
                    'net_income': 'net_income',
                    'market_cap': 'market_cap',
                    'price_to_earnings_ratio': 'pe_ratio',
                    'price_to_book_ratio': 'pb_ratio'
                }

                for json_key, db_field in key_fields.items():
                    json_value = json_data.get(json_key)
                    db_value = getattr(record, db_field)

                    # 检查是否存在不一致
                    if json_value is not None and db_value is None:
                        print(f"    ⚠️  {json_key}: {json_value} (未同步到 {db_field})")
                    elif json_value is None and db_value is not None:
                        print(f"    ✅ {json_key}: None (但 {db_field} 有值: {db_value})")
                    elif json_value is not None and db_value is not None:
                        print(f"    ✅ {json_key}: {json_value} (已同步)")
                    else:
                        print(f"    ❌ {json_key}: None (两者都为空)")

        # 5. 问题总结
        print("\n" + "="*80)
        print("🎯 问题总结:")
        print("="*80)

        has_issues = False

        # 检查是否有null值但metrics_json中有数据
        for record in records:
            if record.metrics_json:
                json_data = record.metrics_json

                # 检查ps_ratio
                if record.ps_ratio is None and json_data.get('price_to_sales_ratio') is not None:
                    if not has_issues:
                        print("\n发现问题：")
                        has_issues = True
                    print(f"\n❌ 记录 #{record.id} ({record.ticker}):")
                    print(f"   - ps_ratio在数据库中为null")
                    print(f"   - 但metrics_json中有值: {json_data.get('price_to_sales_ratio')}")
                    print(f"   ⚠️  原因：缓存写入时未提取该字段")

                # 检查revenue
                if record.revenue is None and json_data.get('revenue') is not None:
                    if not has_issues:
                        print("\n发现问题：")
                        has_issues = True
                    print(f"\n❌ 记录 #{record.id} ({record.ticker}):")
                    print(f"   - revenue在数据库中为null")
                    print(f"   - 但metrics_json中有值: {json_data.get('revenue')}")
                    print(f"   ⚠️  原因：缓存写入时未提取该字段")

                # 检查net_income
                if record.net_income is None and json_data.get('net_income') is not None:
                    if not has_issues:
                        print("\n发现问题：")
                        has_issues = True
                    print(f"\n❌ 记录 #{record.id} ({record.ticker}):")
                    print(f"   - net_income在数据库中为null")
                    print(f"   - 但metrics_json中有值: {json_data.get('net_income')}")
                    print(f"   ⚠️  原因：缓存写入时未提取该字段")

        if not has_issues:
            print("\n✅ 未发现数据不一致问题")

    finally:
        db.close()


def fix_null_values():
    """修复null值问题"""
    print("\n" + "="*80)
    print("🔧 修复Null值")
    print("="*80)

    db = SessionLocal()
    try:
        records = db.query(FinancialMetric).all()
        fixed_count = 0

        for record in records:
            if not record.metrics_json:
                continue

            json_data = record.metrics_json
            updated = False

            # 修复ps_ratio
            if record.ps_ratio is None and json_data.get('price_to_sales_ratio') is not None:
                record.ps_ratio = json_data.get('price_to_sales_ratio')
                updated = True
                print(f"✅ 记录 #{record.id}: 更新 ps_ratio = {record.ps_ratio}")

            # 修复revenue
            if record.revenue is None and json_data.get('revenue') is not None:
                record.revenue = json_data.get('revenue')
                updated = True
                print(f"✅ 记录 #{record.id}: 更新 revenue = {record.revenue}")

            # 修复net_income
            if record.net_income is None and json_data.get('net_income') is not None:
                record.net_income = json_data.get('net_income')
                updated = True
                print(f"✅ 记录 #{record.id}: 更新 net_income = {record.net_income}")

            # 修复market_cap
            if record.market_cap is None and json_data.get('market_cap') is not None:
                record.market_cap = json_data.get('market_cap')
                updated = True
                print(f"✅ 记录 #{record.id}: 更新 market_cap = {record.market_cap}")

            if updated:
                fixed_count += 1

        if fixed_count > 0:
            db.commit()
            print(f"\n✅ 成功修复 {fixed_count} 条记录")
        else:
            print("\n✅ 无需修复，所有数据正常")

    except Exception as e:
        db.rollback()
        print(f"\n❌ 修复失败: {e}")
    finally:
        db.close()


def show_cache_write_code():
    """显示缓存写入代码的问题"""
    print("\n" + "="*80)
    print("📝 代码问题分析")
    print("="*80)

    print("""
问题根源：缓存写入时字段映射不完整

当前代码位置: src/data/mysql_cache.py

问题代码示例:
```python
# 写入缓存时，只提取了部分字段
cache_entry = FinancialMetric(
    ticker=ticker,
    report_period=metrics[0].report_period,
    period=period,
    currency=getattr(metrics[0], 'currency', None),
    market_cap=getattr(metrics[0], 'market_cap', None),
    pe_ratio=getattr(metrics[0], 'price_to_earnings_ratio', None),
    pb_ratio=getattr(metrics[0], 'price_to_book_ratio', None),
    # ❌ 缺少以下字段的映射:
    # ps_ratio=getattr(metrics[0], 'price_to_sales_ratio', None),  # 缺失！
    # revenue=getattr(metrics[0], 'revenue', None),                # 缺失！
    # net_income=getattr(metrics[0], 'net_income', None),          # 缺失！
    metrics_json=metrics[0].model_dump(),  # 完整数据存在这里
    data_source=data_source
)
```

解决方案：
1. 立即修复：运行此脚本的 --fix 选项从 metrics_json 中提取数据
2. 长期修复：更新 mysql_cache.py 代码，添加缺失的字段映射
""")


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description='财务指标数据诊断工具')
    parser.add_argument('--fix', action='store_true', help='修复null值问题')
    parser.add_argument('--show-code', action='store_true', help='显示代码问题分析')

    args = parser.parse_args()

    # 总是先分析
    analyze_null_values()

    # 根据参数执行其他操作
    if args.show_code:
        show_cache_write_code()

    if args.fix:
        fix_null_values()
        print("\n修复完成后，再次分析:")
        analyze_null_values()

    # 如果没有指定任何选项，显示帮助
    if not args.fix and not args.show_code:
        print("\n" + "="*80)
        print("💡 下一步操作:")
        print("="*80)
        print("""
1. 查看代码问题分析:
   poetry run python scripts/diagnose_financial_metrics.py --show-code

2. 修复现有数据:
   poetry run python scripts/diagnose_financial_metrics.py --fix

3. 长期解决方案:
   更新 src/data/mysql_cache.py 中的字段映射代码
""")


if __name__ == "__main__":
    main()
