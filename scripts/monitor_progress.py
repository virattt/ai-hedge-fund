#!/usr/bin/env python3
"""
子代理进度监控脚本
实时监控3个子代理的执行状态
"""

import time
import os
from datetime import datetime

# Agent 输出文件路径
AGENT_OUTPUTS = {
    'Agent 1 (多数据源)': '/private/tmp/claude-501/-Users-luobotao--openclaw-workspace-ai-hedge-fund/fb6055dc-5344-4838-93a4-e8e37b8d8d6e/tasks/acc72d30638aa1479.output',
    'Agent 2 (缓存增强)': '/private/tmp/claude-501/-Users-luobotao--openclaw-workspace-ai-hedge-fund/fb6055dc-5344-4838-93a4-e8e37b8d8d6e/tasks/a0b9725fdc5f7e7ac.output',
    'Agent 3 (配置监控)': '/private/tmp/claude-501/-Users-luobotao--openclaw-workspace-ai-hedge-fund/fb6055dc-5344-4838-93a4-e8e37b8d8d6e/tasks/a716b9b3e49c800ac.output',
}

def get_file_size(filepath):
    """获取文件大小（字节）"""
    try:
        return os.path.getsize(filepath)
    except:
        return 0

def get_last_lines(filepath, n=5):
    """获取文件最后 n 行"""
    try:
        with open(filepath, 'r') as f:
            lines = f.readlines()
            return ''.join(lines[-n:])
    except:
        return "无法读取"

def check_completion(filepath):
    """检查是否完成"""
    try:
        with open(filepath, 'r') as f:
            content = f.read()
            # 检查完成标记
            if '完成' in content or 'completed' in content.lower() or 'success' in content.lower():
                return True
            if '错误' in content or 'error' in content.lower() or 'failed' in content.lower():
                return 'ERROR'
        return False
    except:
        return False

def print_status():
    """打印当前状态"""
    os.system('clear')  # 清屏

    print("=" * 80)
    print(f"{'AI Hedge Fund - 子代理进度监控':^80}")
    print(f"{'更新时间: ' + datetime.now().strftime('%Y-%m-%d %H:%M:%S'):^80}")
    print("=" * 80)
    print()

    all_completed = True
    has_error = False

    for agent_name, output_file in AGENT_OUTPUTS.items():
        size = get_file_size(output_file)
        status = check_completion(output_file)

        # 状态图标
        if status == True:
            icon = "✅"
            status_text = "完成"
        elif status == 'ERROR':
            icon = "❌"
            status_text = "错误"
            has_error = True
            all_completed = False
        else:
            icon = "🔄"
            status_text = "进行中"
            all_completed = False

        print(f"{icon} {agent_name}")
        print(f"   状态: {status_text}")
        print(f"   输出大小: {size:,} 字节")
        print(f"   文件: {output_file}")

        # 显示最后几行
        if size > 0:
            last_lines = get_last_lines(output_file, 3)
            if last_lines.strip():
                print(f"   最新输出:")
                for line in last_lines.strip().split('\n'):
                    print(f"     {line[:100]}")

        print()

    print("=" * 80)

    if all_completed:
        print("✅ 所有子代理已完成！")
        return 'COMPLETED'
    elif has_error:
        print("❌ 有子代理执行失败，请检查日志")
        return 'ERROR'
    else:
        print("🔄 子代理执行中... (每30秒自动刷新)")
        return 'RUNNING'

def main():
    """主函数"""
    print("开始监控子代理进度...")
    print("按 Ctrl+C 退出")
    print()

    try:
        while True:
            status = print_status()

            if status == 'COMPLETED':
                print("\n✅ 监控完成！所有子代理已成功执行。")
                break
            elif status == 'ERROR':
                print("\n❌ 检测到错误，请手动检查日志。")
                break

            # 等待30秒
            time.sleep(30)

    except KeyboardInterrupt:
        print("\n\n⚠️  监控已停止")

if __name__ == '__main__':
    main()
