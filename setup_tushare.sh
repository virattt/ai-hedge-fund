#!/bin/bash

# Tushare 配置脚本
# 用于快速配置 Tushare Pro 数据源

set -e

echo "=========================================="
echo "Tushare Pro 配置向导"
echo "=========================================="
echo ""

# 检查 .env 文件
if [ ! -f .env ]; then
    echo "❌ 错误: .env 文件不存在"
    echo "   请先从 .env.example 复制:"
    echo "   cp .env.example .env"
    exit 1
fi

# 检查当前配置
current_token=$(grep "^TUSHARE_TOKEN=" .env | cut -d'=' -f2)

if [ "$current_token" != "your-tushare-token-here" ] && [ -n "$current_token" ]; then
    echo "✅ 检测到已配置的 Tushare Token"
    echo "   Token: ${current_token:0:10}...${current_token: -10}"
    echo ""
    read -p "是否要更新 Token? (y/N): " update_token

    if [ "$update_token" != "y" ] && [ "$update_token" != "Y" ]; then
        echo "保持现有配置"
        exit 0
    fi
fi

# 显示注册指引
echo "📝 步骤 1: 获取 Tushare Token"
echo "=========================================="
echo ""
echo "1. 访问 Tushare 注册页面:"
echo "   https://tushare.pro/register"
echo ""
echo "2. 使用手机号或邮箱注册（免费）"
echo ""
echo "3. 登录后访问 Token 页面:"
echo "   https://tushare.pro/user/token"
echo ""
echo "4. 复制你的 Token"
echo ""
echo "按回车键继续..."
read

# 输入 Token
echo ""
echo "📋 步骤 2: 输入 Token"
echo "=========================================="
echo ""
read -p "请粘贴你的 Tushare Token: " new_token

# 验证 Token 格式
if [ -z "$new_token" ]; then
    echo "❌ Token 不能为空"
    exit 1
fi

if [ ${#new_token} -lt 30 ]; then
    echo "❌ Token 长度太短，请检查是否完整复制"
    exit 1
fi

# 更新 .env 文件
echo ""
echo "💾 步骤 3: 保存配置"
echo "=========================================="
echo ""

# 备份 .env
cp .env .env.backup
echo "已备份 .env 到 .env.backup"

# 更新或添加 TUSHARE_TOKEN
if grep -q "^TUSHARE_TOKEN=" .env; then
    # 替换现有配置
    sed -i.tmp "s|^TUSHARE_TOKEN=.*|TUSHARE_TOKEN=$new_token|" .env
    rm -f .env.tmp
    echo "✅ 已更新 TUSHARE_TOKEN"
else
    # 添加新配置
    echo "" >> .env
    echo "# Tushare Pro - Chinese stock data" >> .env
    echo "TUSHARE_TOKEN=$new_token" >> .env
    echo "✅ 已添加 TUSHARE_TOKEN"
fi

# 验证配置
echo ""
echo "✅ 步骤 4: 验证配置"
echo "=========================================="
echo ""

# 检查是否能导入 tushare
if ! poetry run python -c "import tushare" 2>/dev/null; then
    echo "⚠️  tushare 未安装，正在安装..."
    poetry add tushare
fi

# 测试 Token
echo "测试 Tushare 连接..."
test_result=$(poetry run python -c "
import os
from dotenv import load_dotenv

load_dotenv()
token = os.getenv('TUSHARE_TOKEN')

try:
    import tushare as ts
    ts.set_token(token)
    pro = ts.pro_api()

    # 测试获取数据
    df = pro.daily(ts_code='000001.SZ', start_date='20240102', end_date='20240105')

    if df is not None and not df.empty:
        print('SUCCESS:' + str(len(df)))
    else:
        print('ERROR:No data returned')
except Exception as e:
    print('ERROR:' + str(e))
" 2>&1)

if [[ $test_result == SUCCESS:* ]]; then
    record_count=$(echo $test_result | cut -d':' -f2)
    echo "✅ Tushare 配置成功!"
    echo "   测试获取到 $record_count 条数据记录"
else
    echo "❌ Tushare 配置失败:"
    echo "   $(echo $test_result | cut -d':' -f2-)"
    echo ""
    echo "可能的原因:"
    echo "  1. Token 错误"
    echo "  2. 网络连接问题"
    echo "  3. Tushare 服务异常"
    echo ""
    echo "请检查后重新运行此脚本"
    exit 1
fi

# 显示下一步
echo ""
echo "🎉 配置完成!"
echo "=========================================="
echo ""
echo "下一步:"
echo ""
echo "1. 运行数据源测试:"
echo "   poetry run python test_data_sources.py"
echo ""
echo "2. 测试 A股数据获取:"
echo "   poetry run python src/main.py --ticker 000001 --analysts \"warren_buffett\" --model \"MiniMax-M2.5\""
echo ""
echo "3. 查看完整文档:"
echo "   cat docs/TUSHARE_SETUP.md"
echo ""
echo "=========================================="
echo ""
