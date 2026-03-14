#!/bin/bash
# 集成测试脚本
# 用于验证所有新功能是否正常工作

set -e  # 遇到错误立即退出

echo "================================"
echo "AI Hedge Fund - 集成测试"
echo "================================"
echo ""

# 颜色定义
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 测试计数器
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0

# 测试函数
run_test() {
    local test_name="$1"
    local test_command="$2"

    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    echo -e "${YELLOW}[TEST $TOTAL_TESTS]${NC} $test_name"

    if eval "$test_command" > /tmp/test_output.log 2>&1; then
        echo -e "${GREEN}✓ PASSED${NC}"
        PASSED_TESTS=$((PASSED_TESTS + 1))
        return 0
    else
        echo -e "${RED}✗ FAILED${NC}"
        echo "Error output:"
        cat /tmp/test_output.log
        FAILED_TESTS=$((FAILED_TESTS + 1))
        return 1
    fi
    echo ""
}

# 1. 依赖检查
echo "Step 1: 检查依赖..."
echo "-----------------------------------"
run_test "检查 Python 版本" "python --version"
run_test "检查 Poetry" "poetry --version"
run_test "检查 akshare 安装" "poetry run python -c 'import akshare'"
run_test "检查 yfinance 安装" "poetry run python -c 'import yfinance'"
run_test "检查 pydantic-settings 安装" "poetry run python -c 'import pydantic_settings'"
echo ""

# 2. 单元测试
echo "Step 2: 运行单元测试..."
echo "-----------------------------------"
run_test "数据源测试" "poetry run pytest tests/markets/sources/ -v --tb=short"
run_test "数据验证测试" "poetry run pytest tests/data/test_validation.py -v --tb=short"
run_test "缓存增强测试" "poetry run pytest tests/data/test_cache_enhancement.py -v --tb=short"
run_test "配置管理测试" "poetry run pytest tests/config/ -v --tb=short"
run_test "监控测试" "poetry run pytest tests/monitoring/ -v --tb=short"
echo ""

# 3. 集成测试
echo "Step 3: 运行集成测试..."
echo "-----------------------------------"
run_test "市场适配器集成测试" "poetry run pytest tests/markets/test_integration.py -v --tb=short"
run_test "端到端测试" "poetry run pytest tests/backtesting/integration/ -v --tb=short"
echo ""

# 4. 功能测试
echo "Step 4: 运行功能测试..."
echo "-----------------------------------"

# 测试美股
run_test "美股价格获取" "poetry run python -c \"
from src.tools.api import get_prices
prices = get_prices('AAPL', '2024-01-01', '2024-01-31')
assert len(prices) > 0, 'No prices returned'
print(f'✓ 获取了 {len(prices)} 条价格数据')
\""

# 测试 A股
run_test "A股价格获取（多数据源）" "poetry run python -c \"
from src.tools.api import get_prices
prices = get_prices('600000.SH', '2024-01-01', '2024-01-31')
assert len(prices) > 0, 'No prices returned'
print(f'✓ 获取了 {len(prices)} 条价格数据')
\""

# 测试港股
run_test "港股价格获取（多数据源）" "poetry run python -c \"
from src.tools.api import get_prices
prices = get_prices('0700.HK', '2024-01-01', '2024-01-31')
assert len(prices) > 0, 'No prices returned'
print(f'✓ 获取了 {len(prices)} 条价格数据')
\""

# 测试缓存
run_test "缓存功能测试" "poetry run python -c \"
from src.data.cache import get_cache
cache = get_cache()
stats = cache.get_stats()
print(f'✓ 缓存统计: {stats}')
assert 'hit_rate' in stats, 'Cache stats missing hit_rate'
\""

# 测试配置
run_test "配置加载测试" "poetry run python -c \"
from src.config.settings import settings
print(f'✓ 数据源权重: {settings.data_source.source_weights}')
print(f'✓ 缓存 TTL: {settings.cache.ttl} 秒')
assert settings.cache.ttl > 0, 'Invalid cache TTL'
\""

# 测试监控
run_test "监控指标测试" "poetry run python -c \"
from src.monitoring.metrics import metrics_collector
summary = metrics_collector.get_summary()
print(f'✓ 监控指标: {summary}')
\""

echo ""

# 5. 回归测试
echo "Step 5: 运行回归测试..."
echo "-----------------------------------"
run_test "原有 API 兼容性" "poetry run pytest tests/tools/test_api.py -v --tb=short"
run_test "回测引擎" "poetry run pytest tests/backtesting/ -v --tb=short"
echo ""

# 6. 性能测试
echo "Step 6: 运行性能测试..."
echo "-----------------------------------"

run_test "缓存性能测试" "poetry run python -c \"
import time
from src.tools.api import get_prices

# 第一次调用（无缓存）
start = time.time()
prices1 = get_prices('AAPL', '2024-01-01', '2024-01-31')
time1 = time.time() - start

# 第二次调用（有缓存）
start = time.time()
prices2 = get_prices('AAPL', '2024-01-01', '2024-01-31')
time2 = time.time() - start

speedup = time1 / time2 if time2 > 0 else 0
print(f'✓ 第一次: {time1:.2f}s, 第二次: {time2:.2f}s, 加速: {speedup:.1f}x')
assert speedup > 5, f'Cache speedup too low: {speedup}x'
\""

echo ""

# 7. 代码质量检查
echo "Step 7: 代码质量检查..."
echo "-----------------------------------"
run_test "代码格式检查" "poetry run black --check src/ tests/ || true"
run_test "类型检查" "poetry run mypy src/ --ignore-missing-imports || true"
echo ""

# 总结
echo "================================"
echo "测试总结"
echo "================================"
echo -e "总测试数: $TOTAL_TESTS"
echo -e "${GREEN}通过: $PASSED_TESTS${NC}"
echo -e "${RED}失败: $FAILED_TESTS${NC}"
echo ""

if [ $FAILED_TESTS -eq 0 ]; then
    echo -e "${GREEN}✓ 所有测试通过！${NC}"
    exit 0
else
    echo -e "${RED}✗ 有 $FAILED_TESTS 个测试失败${NC}"
    exit 1
fi
