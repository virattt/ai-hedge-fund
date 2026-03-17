#!/usr/bin/env python3
"""
测试脚本：验证ROE修复和JSON解析增强

测试内容:
1. ROE数据格式修复 (EastmoneyCurlSource)
2. JSON解析增强 (处理<think>标签)
"""

import sys
from src.tools.api import get_financial_metrics
from src.utils.llm import extract_json_from_response


def test_roe_fix():
    """测试ROE数据格式修复"""
    print("=" * 60)
    print("测试 1: ROE数据格式修复")
    print("=" * 60)

    ticker = '000001.SZ'
    metrics = get_financial_metrics(ticker, '2024-03-01', period='ttm', limit=1)

    if not metrics:
        print("❌ 无法获取财务指标")
        return False

    m = metrics[0]
    roe = m.return_on_equity

    print(f"\n股票代码: {m.ticker}")
    print(f"报告期: {m.report_period}")
    print(f"ROE: {roe:.4f} ({roe:.2%})")

    # 验证ROE是否在合理范围内 (0-1之间,表示0%-100%)
    if 0 <= roe <= 1:
        print(f"\n✅ ROE格式正确: {roe:.2%}")
        return True
    else:
        print(f"\n❌ ROE格式错误: {roe} (应该在0-1之间)")
        return False


def test_json_parsing():
    """测试JSON解析增强"""
    print("\n" + "=" * 60)
    print("测试 2: JSON解析增强")
    print("=" * 60)

    test_cases = [
        {
            "name": "<think>标签包裹",
            "input": '''<think>
Some reasoning here...
</think>

{
  "sentiment": "positive",
  "confidence": 90
}''',
            "expected": {"sentiment": "positive", "confidence": 90}
        },
        {
            "name": "Markdown代码块",
            "input": '''```json
{"sentiment": "negative", "confidence": 75}
```''',
            "expected": {"sentiment": "negative", "confidence": 75}
        },
        {
            "name": "纯JSON",
            "input": '{"sentiment": "neutral", "confidence": 50}',
            "expected": {"sentiment": "neutral", "confidence": 50}
        },
        {
            "name": "多个<think>标签",
            "input": '''<think>First</think>
{"sentiment": "positive", "confidence": 85}
<think>Second</think>''',
            "expected": {"sentiment": "positive", "confidence": 85}
        }
    ]

    all_passed = True

    for i, test in enumerate(test_cases, 1):
        print(f"\n测试案例 {i}: {test['name']}")
        result = extract_json_from_response(test['input'])

        if result == test['expected']:
            print(f"  ✅ 通过: {result}")
        else:
            print(f"  ❌ 失败")
            print(f"    期望: {test['expected']}")
            print(f"    实际: {result}")
            all_passed = False

    return all_passed


def main():
    """运行所有测试"""
    print("\n🧪 开始测试修复...\n")

    test1_passed = test_roe_fix()
    test2_passed = test_json_parsing()

    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)
    print(f"ROE修复: {'✅ 通过' if test1_passed else '❌ 失败'}")
    print(f"JSON解析: {'✅ 通过' if test2_passed else '❌ 失败'}")

    if test1_passed and test2_passed:
        print("\n🎉 所有测试通过!")
        return 0
    else:
        print("\n❌ 部分测试失败")
        return 1


if __name__ == "__main__":
    sys.exit(main())
