#!/usr/bin/env python3
"""
添加数据库表和字段的中文注释

使用方法:
    poetry run python scripts/add_database_comments.py

或者直接执行SQL文件:
    mysql -u root -p hedge-fund < database_comments.sql
"""
import os
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text
from src.database.connection import SessionLocal, engine, test_connection


def read_sql_file():
    """读取SQL注释文件"""
    sql_file = project_root / "database_comments.sql"
    if not sql_file.exists():
        print(f"❌ SQL文件不存在: {sql_file}")
        return None

    with open(sql_file, 'r', encoding='utf-8') as f:
        content = f.read()

    return content


def split_sql_statements(sql_content):
    """
    分割SQL语句
    忽略注释行和空行
    """
    statements = []
    current_statement = []

    for line in sql_content.split('\n'):
        # 跳过注释和空行
        stripped = line.strip()
        if not stripped or stripped.startswith('--'):
            continue

        # USE语句单独处理
        if stripped.upper().startswith('USE'):
            if current_statement:
                statements.append('\n'.join(current_statement))
                current_statement = []
            statements.append(stripped)
            continue

        current_statement.append(line)

        # 如果遇到分号，保存当前语句
        if stripped.endswith(';'):
            statements.append('\n'.join(current_statement))
            current_statement = []

    # 添加最后一条语句（如果有）
    if current_statement:
        statements.append('\n'.join(current_statement))

    return statements


def execute_sql_statements(statements):
    """执行SQL语句"""
    db = SessionLocal()
    success_count = 0
    error_count = 0

    try:
        for i, statement in enumerate(statements, 1):
            statement = statement.strip()
            if not statement:
                continue

            try:
                # 显示正在执行的语句（简短版本）
                preview = statement[:100].replace('\n', ' ')
                if len(statement) > 100:
                    preview += '...'
                print(f"[{i}/{len(statements)}] 执行: {preview}")

                db.execute(text(statement))
                db.commit()
                success_count += 1

            except Exception as e:
                error_count += 1
                print(f"❌ 执行失败: {e}")
                print(f"   语句: {statement[:200]}")
                db.rollback()

    finally:
        db.close()

    return success_count, error_count


def verify_comments():
    """验证注释是否添加成功"""
    db = SessionLocal()

    try:
        # 获取所有表
        result = db.execute(text("SHOW TABLES"))
        tables = [row[0] for row in result]

        print("\n" + "="*80)
        print("验证表注释:")
        print("="*80)

        for table in tables:
            # 获取表注释
            result = db.execute(text(f"SHOW TABLE STATUS LIKE '{table}'"))
            row = result.fetchone()
            if row:
                comment = row[17] if len(row) > 17 else ""  # Comment字段通常在第18列
                status = "✅" if comment else "❌"
                print(f"{status} {table:40} {comment}")

        print("\n" + "="*80)
        print("验证字段注释 (示例表: trading_sessions):")
        print("="*80)

        # 显示一个表的字段注释作为示例
        result = db.execute(text("SHOW FULL COLUMNS FROM trading_sessions"))
        for row in result:
            field = row[0]
            comment = row[8] if len(row) > 8 else ""
            status = "✅" if comment else "❌"
            print(f"{status} {field:30} {comment}")

    finally:
        db.close()


def main():
    """主函数"""
    print("="*80)
    print("数据库表注释添加工具")
    print("="*80)

    # 测试数据库连接
    print("\n1. 测试数据库连接...")
    if not test_connection():
        print("❌ 数据库连接失败，请检查配置")
        return 1

    # 读取SQL文件
    print("\n2. 读取SQL注释文件...")
    sql_content = read_sql_file()
    if not sql_content:
        return 1
    print(f"✅ 成功读取SQL文件 ({len(sql_content)} 字符)")

    # 分割SQL语句
    print("\n3. 解析SQL语句...")
    statements = split_sql_statements(sql_content)
    print(f"✅ 解析出 {len(statements)} 条SQL语句")

    # 执行SQL语句
    print("\n4. 执行SQL语句...")
    success, errors = execute_sql_statements(statements)
    print(f"\n执行完成: ✅ {success} 成功, ❌ {errors} 失败")

    # 验证注释
    print("\n5. 验证注释...")
    verify_comments()

    print("\n" + "="*80)
    print("完成!")
    print("="*80)

    return 0 if errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
