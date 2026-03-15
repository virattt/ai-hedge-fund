# Tushare 快速配置（5分钟）

## 🚀 三步配置

### 1️⃣ 获取 Token（2分钟）

访问 **https://tushare.pro/register** 注册账号（免费）

注册后访问 **https://tushare.pro/user/token** 复制你的 Token

### 2️⃣ 配置 Token（1分钟）

打开项目根目录的 `.env` 文件，找到这一行：

```bash
TUSHARE_TOKEN=your-tushare-token-here
```

替换为你的实际 Token：

```bash
TUSHARE_TOKEN=你复制的Token粘贴到这里
```

保存文件。

### 3️⃣ 测试验证（2分钟）

```bash
# 运行测试脚本
poetry run python test_data_sources.py
```

如果看到：
```
✅ A股数据 - 通过
```

配置成功！🎉

---

## 💡 或者使用自动配置脚本

```bash
# 运行配置向导
./setup_tushare.sh
```

脚本会引导你完成所有步骤。

---

## ✅ 配置成功后

现在可以稳定获取 A股数据了：

```bash
# 测试单个 A股
poetry run python src/main.py --ticker 000001 --analysts "warren_buffett" --model "MiniMax-M2.5"

# 测试多个 A股
poetry run python src/main.py --ticker 000001,600000,000002 --analysts-all --model "MiniMax-M2.5"
```

---

## ❓ 遇到问题？

查看详细文档：[docs/TUSHARE_SETUP.md](docs/TUSHARE_SETUP.md)

---

**注意**: Token 是私密信息，不要分享给他人或提交到 Git！
