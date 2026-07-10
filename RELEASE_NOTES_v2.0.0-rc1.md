## AI Daily v2.0.0-rc1 — Production Ready

> 第一个可运行的生产版本。6 个数据源 · 事件聚类 · AI 摘要 · MCP Server

### 📦 安装

```bash
git clone https://github.com/chenxianseng001/ai-daily.git
cd ai-daily
pip install -r requirements.txt
python3 run_daily.py
```

### ✨ 功能

| 功能 | 说明 |
|---|---|
| **6 个数据源** | GitHub Trending / Hacker News / Product Hunt / YouTube / X(Twitter) / 国产 AI |
| **零配置运行** | 5/6 数据源无需 API Key |
| **事件聚类** | 同一事件跨源自动合并 |
| **AI 摘要** | 8 个 LLM Provider：OpenAI / DeepSeek / Claude / Gemini / 本地模型 |
| **MCP Server** | 10 个只读 Tool，支持 Hermes / Claude Desktop / Cursor |
| **增量采集** | 只采集新内容，不重复下载 |
| **定时运行** | systemd timer，每天 06:00 自动采集 |
| **多实例容错** | Nitter 多实例健康检查，自动切换 |

### 🏗️ 架构

- Collector / Reporter / MCP 三层分离
- Data Contract v1.0 统一数据格式
- 模块化 Section 设计，新增数据源只需 4 步
- 101 个测试用例

### 🚀 生产部署

详见 `deploy/systemd/` 和 `docs/PROJECT_STATUS.md`。

系统要求：Python 3.10+，Ubuntu 24.04（推荐）
