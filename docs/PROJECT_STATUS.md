# AI Daily — Project Status

> Version: **v2.0.0-rc1**
> Status: **Production Ready** ✅
> Current Phase: **Production Validation**
> Last Updated: **2026-07-10**

---

## 项目概况

AI Daily 是一个 AI 信息采集与日报生成系统。每天从 6 个数据源自动采集，生成结构化中文日报。

### 核心指标

| 指标 | 值 |
|---|---|
| 数据源 | 6 个 |
| Python 文件 | 42 个 |
| 测试用例 | 101 个（8 个测试文件） |
| MCP 工具 | 10 个 |
| 配置中心 | YAML，5 个配置文件 |
| 单次运行 | ~74s，~240 条数据 |
| 运行频率 | 每天 06:00 CST（systemd timer） |

### 技术栈

- Python 3.12
- MCP SDK 1.28
- yt-dlp
- systemd
- 无数据库依赖

---

## 部署状态

| 组件 | 位置 | 状态 |
|---|---|---|
| 项目代码 | `/opt/ai-daily/app/` | ✅ |
| Python venv | `/opt/ai-daily/venv/` | ✅ |
| 符号链接 | `app/* → /opt/ai-daily/*` | ✅ |
| Data storage | `/opt/ai-daily/storage/` | ✅ （293 文件） |
| Report output | `/opt/ai-daily/output/` | ✅ |
| Logs | `/opt/ai-daily/logs/` | ✅ |
| Cache | `/opt/ai-daily/cache/` | ✅ |
| systemd service | `ai-daily.service` | ✅ |
| systemd timer | `ai-daily.timer`（06:00 CST） | ✅ |
| MCP Server | Hermes stdio | ✅ |

---

## 数据源

| 数据源 | 采集方式 | Token 要求 | 状态 |
|---|---|---|---|
| GitHub Trending | 网页解析 + README 下载 | 可选 | ✅ |
| Hacker News | Firebase API | 无 | ✅ |
| Product Hunt | 网页降级 / GraphQL API | 可选 | ✅ |
| YouTube | yt-dlp | 无 | ✅ |
| X（Twitter） | Nitter RSS（多实例） | 无 | ✅ |
| 国产 AI | RSS（量子位/36氪/少数派） | 无 | ✅ |

---

## 运行方式

```bash
# 完整采集 + 日报生成
/opt/ai-daily/venv/bin/python3 /opt/ai-daily/app/run_daily.py

# 定时运行（每天 06:00）
sudo systemctl start ai-daily.timer

# 查看运行状态
journalctl -u ai-daily.service -n 20
```
