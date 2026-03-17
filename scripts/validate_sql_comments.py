#!/usr/bin/env python3
"""
验证SQL注释文件的语法和完整性

使用方法:
    poetry run python scripts/validate_sql_comments.py
"""
import re
from pathlib import Path

project_root = Path(__file__).parent.parent
sql_file = project_root / "database_comments.sql"


def validate_sql_file():
    """验证SQL文件"""
    print("="*80)
    print("验证SQL注释文件")
    print("="*80)

    if not sql_file.exists():
        print(f"❌ SQL文件不存在: {sql_file}")
        return False

    with open(sql_file, 'r', encoding='utf-8') as f:
        content = f.read()

    print(f"\n✅ 文件存在: {sql_file}")
    print(f"   文件大小: {len(content)} 字符")

    # 统计表数量
    tables = re.findall(r"ALTER TABLE `(\w+)`", content)
    print(f"\n✅ 找到 {len(set(tables))} 个表的注释:")
    for table in sorted(set(tables)):
        count = tables.count(table)
        print(f"   - {table}: {count} 条ALTER语句")

    # 检查每个表的注释结构
    print("\n检查表注释结构:")

    # 业务表
    expected_tables = [
        "trading_sessions",
        "trading_decisions",
        "analyst_analyses",
        "market_data",
        "performance_metrics",
        # 缓存表
        "stock_prices",
        "financial_metrics",
        "company_news",
        # Web应用表
        "hedge_fund_flows",
        "hedge_fund_flow_runs",
        "hedge_fund_flow_run_cycles",
        "api_keys"
    ]

    missing_tables = []
    for table in expected_tables:
        if table in tables:
            print(f"   ✅ {table}")
        else:
            print(f"   ❌ {table} - 缺失")
            missing_tables.append(table)

    if missing_tables:
        print(f"\n⚠️  缺少 {len(missing_tables)} 个表的注释")
        return False

    # 检查SQL语法
    print("\n检查SQL语法:")

    # 检查是否有未闭合的语句
    alter_starts = content.count("ALTER TABLE")
    semicolons = content.count(";")
    print(f"   ALTER TABLE 语句: {alter_starts}")
    print(f"   分号数量: {semicolons}")

    if semicolons < alter_starts:
        print(f"   ⚠️  可能有未闭合的语句")

    # 检查是否有中文注释
    chinese_comments = re.findall(r"COMMENT '([^']*[\u4e00-\u9fff]+[^']*)'", content)
    print(f"\n✅ 找到 {len(chinese_comments)} 个中文注释")

    if len(chinese_comments) < 50:
        print("   ⚠️  中文注释数量偏少")

    # 检查常见错误
    print("\n检查常见错误:")

    errors = []

    # 检查是否有空注释
    empty_comments = re.findall(r"COMMENT ''", content)
    if empty_comments:
        errors.append(f"发现 {len(empty_comments)} 个空注释")

    # 检查是否有未转义的引号
    unescaped_quotes = re.findall(r"COMMENT '[^']*'[^',;]", content)
    if unescaped_quotes:
        errors.append(f"可能有未转义的引号: {len(unescaped_quotes)} 处")

    if errors:
        for error in errors:
            print(f"   ⚠️  {error}")
    else:
        print("   ✅ 未发现常见错误")

    print("\n" + "="*80)
    if missing_tables or errors:
        print("验证完成: 发现一些问题需要修复")
        print("="*80)
        return False
    else:
        print("验证完成: SQL文件格式正确")
        print("="*80)
        return True


def show_table_structure():
    """显示表结构概览"""
    print("\n" + "="*80)
    print("数据库表结构概览")
    print("="*80)

    # 从models.py读取表结构
    models_file = project_root / "src" / "database" / "models.py"
    backend_models_file = project_root / "app" / "backend" / "database" / "models.py"

    print("\n业务表 (src/database/models.py):")
    if models_file.exists():
        with open(models_file, 'r', encoding='utf-8') as f:
            content = f.read()
            classes = re.findall(r'class (\w+)\(Base\):\s*"""([^"]+)"""', content)
            for cls, desc in classes:
                print(f"   - {cls}: {desc}")

    print("\nWeb应用表 (app/backend/database/models.py):")
    if backend_models_file.exists():
        with open(backend_models_file, 'r', encoding='utf-8') as f:
            content = f.read()
            classes = re.findall(r'class (\w+)\(Base\):\s*"""([^"]+)"""', content)
            for cls, desc in classes:
                print(f"   - {cls}: {desc}")


def main():
    """主函数"""
    success = validate_sql_file()
    show_table_structure()

    return 0 if success else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
