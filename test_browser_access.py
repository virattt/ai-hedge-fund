#!/usr/bin/env python3
"""测试使用浏览器自动化访问 Eastmoney API"""
import json

def test_with_playwright():
    """使用 Playwright 测试（项目已安装）"""
    try:
        from playwright.sync_api import sync_playwright

        print("=" * 60)
        print("使用 Playwright 测试浏览器访问")
        print("=" * 60)

        with sync_playwright() as p:
            # 启动浏览器
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            # 访问 API
            url = 'http://push2.eastmoney.com/api/qt/stock/get?secid=0.000001&fields=f116'
            print(f"\n访问 URL: {url}")

            try:
                response = page.goto(url, timeout=15000)

                if response and response.ok:
                    print(f"✅ 成功！状态码: {response.status}")

                    # 获取页面内容
                    content = page.content()

                    # 尝试解析 JSON
                    try:
                        # 查找 <pre> 标签中的内容（浏览器通常这样显示 JSON）
                        json_text = page.inner_text('pre')
                        data = json.loads(json_text)
                        print(f"   市值: {data['data']['f116']}")
                        print(f"   完整数据: {data}")
                    except:
                        # 尝试直接从 body 获取
                        json_text = page.inner_text('body')
                        data = json.loads(json_text)
                        print(f"   市值: {data['data']['f116']}")
                        print(f"   完整数据: {data}")
                else:
                    print(f"❌ 失败！状态码: {response.status if response else 'None'}")

            except Exception as e:
                print(f"❌ 页面加载错误: {type(e).__name__}: {e}")

            browser.close()

    except ImportError:
        print("❌ Playwright 未安装")
        print("   运行: poetry add playwright && poetry run playwright install")
    except Exception as e:
        print(f"❌ 错误: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

def test_different_urls():
    """测试不同的 URL 变体"""
    urls = [
        'http://push2.eastmoney.com/api/qt/stock/get?secid=0.000001&fields=f116',
        'https://push2.eastmoney.com/api/qt/stock/get?secid=0.000001&fields=f116',
        'http://61.129.129.196/api/qt/stock/get?secid=0.000001&fields=f116',
    ]

    print("\n" + "=" * 60)
    print("测试不同的 URL 变体")
    print("=" * 60)

    import requests

    for url in urls:
        print(f"\n测试: {url}")
        try:
            headers = {
                'Host': 'push2.eastmoney.com',
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
                'Accept': 'application/json, text/plain, */*',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                'Connection': 'keep-alive',
            }

            response = requests.get(url, headers=headers, timeout=10)
            print(f"  ✅ 成功！状态码: {response.status_code}")
            data = response.json()
            print(f"     市值: {data['data']['f116']}")
        except Exception as e:
            print(f"  ❌ 失败: {type(e).__name__}: {str(e)[:80]}")

if __name__ == "__main__":
    # 测试 1: 使用 Playwright
    test_with_playwright()

    # 测试 2: 测试不同 URL
    test_different_urls()
