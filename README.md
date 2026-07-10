# 🤖 AI Daily

> 每天 10 分钟，掌握 AI 圈重要动态。

AI Daily 是一个自动化的 AI 信息采集与日报生成系统。它从 **6 个数据源** 采集信息，生成结构化的中文日报。

---

## ✨ 功能

| 功能 | 说明 |
|---|---|
| **6 个数据源** | GitHub Trending、Hacker News、Product Hunt、YouTube、X (Twitter)、国产 AI |
| **自动采集** | 每天定时运行，无需人工干预 |
| **增量采集** | 只采集新内容，不重复下载 |
| **事件聚类** | 同一事件在多个源中出现时自动合并 |
| **AI 摘要** | 支持 OpenAI / DeepSeek / Claude / Gemini / 本地模型 |
| **统一配置** | YAML 配置，无需改代码 |
| **多实例容错** | Nitter 多实例健康检查，自动切换 |

---

## 🚀 快速开始

### 环境要求

- Python 3.10+
- macOS / Linux / WSL

### 安装

```bash
# 1. 克隆
git clone https://github.com/your-username/ai-daily.git
cd ai-daily

# 2. 安装依赖
pip install -r requirements.txt

# 3. 运行（零配置启动）
python3 run_daily.py
```

**首次运行说明：**
- 所有数据源默认开启
- Product Hunt 和 GitHub Trending 无需 Token 即可运行（自动降级模式）
- YouTube 需要安装 `yt-dlp`（已包含在 requirements.txt）
- Twitter 使用内置 Nitter 实例

### 首次运行

```bash
python3 run_daily.py
```

执行流程：
1. 并行采集 6 个数据源（约 1-2 分钟）
2. 自动生成日报
3. 输出到 `output/YYYY-MM-DD/daily_report.md`
4. 同时打印到控制台

---

## 📖 配置说明

### 基本配置

编辑 `config/config.yaml` 即可控制：

```yaml
# 启用/禁用数据源
github_trending:
  enabled: true

hacker_news:
  enabled: true

product_hunt:
  enabled: true

youtube:
  enabled: true

twitter:
  enabled: true

china_ai:
  enabled: true
```

### 展示数量

```yaml
hacker_news:
  max_items: 10        # 日报中展示 Top N

product_hunt:
  show_top: 10         # 日报中展示 Top N

twitter:
  max_items: 10        # 日报中展示 Top N
```

### 环境变量（可选）

| 环境变量 | 用途 |
|---|---|
| `GITHUB_TOKEN` | GitHub API Token（提升 API 配额） |
| `PRODUCT_HUNT_TOKEN` | Product Hunt API Token |
| `AI_SUMMARY_API_KEY` | AI 摘要 API Key |
| `AI_SUMMARY_PROVIDER` | AI 摘要 Provider（openai/deepseek/claude/gemini） |

### 详细配置

各数据源的详细配置见：

| 文件 | 说明 |
|---|---|
| `config/config.yaml` | 全局配置 |
| `config/channels.yaml` | YouTube 频道白名单 |
| `config/twitter_accounts.yaml` | X 账号白名单 + Nitter 实例 |
| `config/china_ai_sources.yaml` | 国产 AI 新闻源 |

---

## 📊 数据源说明

| 数据源 | 采集方式 | 是否需要 Token |
|---|---|---|
| **GitHub Trending** | 网页解析 + README 下载 | 可选（GITHUB_TOKEN） |
| **Hacker News** | 官方 Firebase API | ❌ 不需要 |
| **Product Hunt** | 网页析 / GraphQL API | 可选（PRODUCT_HUNT_TOKEN） |
| **YouTube** | yt-dlp | ❌ 不需要 |
| **X (Twitter)** | Nitter RSS（多实例） | ❌ 不需要 |
| **国产 AI** | RSS（量子位/36氪/少数派） | ❌ 不需要 |

---

## 🏗️ 项目架构

```
采集层（Collector）                   报告层（Reporter）
┌──────────────┐                  ┌──────────────────┐
│ GitHub       │ → JSON + raw →   │ Section: GitHub  │
│ Hacker News  │ → JSON + raw →   │ Section: HN      │
│ Product Hunt │ → JSON + raw →   │ Section: PH      │
│ YouTube      │ → JSON + raw →   │ Section: YT      │
│ X (Twitter)  │ → JSON + raw →   │ Section: X       │
│ 国产 AI      │ → JSON + raw →   │ Section: China   │
└──────────────┘                  └──────────────────┘
                                            ↓
                                    Event Clustering
                                            ↓
                                      AI Summary
                                            ↓
                                    Markdown 日报
```

### 核心设计原则

- **Data Contract**：所有数据源使用统一 JSON Schema
- **分离原则**：Collector 只采集不分析，Reporter 只读取不联网
- **模块化**：新增数据源只需新建一个 Collector 文件 + 一个 Section 文件

---

## 📁 目录结构

```
ai-daily/
├── run_daily.py           # 统一运行入口（推荐）
├── run_collector.py       # 仅采集
├── run_reporter.py        # 仅生成报告
│
├── core/                  # 基础设施
│   ├── config.py          # 配置加载
│   ├── http_client.py     # HTTP 客户端（限流/重试/超时）
│   ├── logger.py          # 统一日志
│   └── utils.py           # 工具函数
│
├── collectors/            # 采集器（每个数据源一个）
│   ├── base_collector.py  # 基类 + State 管理
│   ├── github_trending.py
│   ├── hacker_news.py
│   ├── product_hunt.py
│   ├── youtube.py
│   ├── twitter.py
│   └── china_ai.py
│
├── reporter/              # 报告生成
│   ├── base_section.py    # Section 基类
│   ├── report_builder.py  # 报告构建器
│   ├── event_cluster.py   # 事件聚类
│   └── sections/          # 各数据源 Section
│
├── config/                # 配置文件
├── tests/                 # 单元测试（101 个）
└── storage/ / output/     # 缓存/输出（自动生成）
```

---

## 🔧 如何新增一个数据源

只需 4 步：

### 1. 创建 Collector

`collectors/my_source.py`:

```python
from collectors.base_collector import BaseCollector, CollectorResult

class MySourceCollector(BaseCollector):
    @property
    def source_name(self) -> str:
        return "my_source"

    def collect(self, state: dict) -> CollectorResult:
        # 1. 采集数据
        # 2. build_item() 构造 item
        # 3. write_raw() 保存原始内容
        # 4. write_json() 写入缓存
        ...
```

### 2. 添加到配置

`config/config.yaml`:

```yaml
my_source:
  enabled: true
  max_items: 10
```

### 3. 注册到 run_collector.py

在 `create_collectors()` 中添加一行。

### 4. 创建 Section

`reporter/sections/my_source_section.py`:

```python
from reporter.base_section import BaseSection

class MySourceSection(BaseSection):
    @property
    def name(self) -> str: return "My Source"
    @property
    def source_name(self) -> str: return "my_source"
    def render(self, items, config=None) -> str: ...
```

然后在 `reporter/report_builder.py` 的 `SECTIONS` 中注册。

---

## 🧪 测试

```bash
# 运行所有测试
python3 -m pytest tests/ -v

# 运行特定测试
python3 -m pytest tests/test_summary.py -v
```

当前共 **101 个测试**。

---

## ❓ 常见问题

**Q: 需要 API Key 吗？**
A: 不需要。6 个数据源中 5 个无需任何 API Key 即可运行。配置 Token 可以获得更完整的数据。

**Q: 运行需要多久？**
A: 首次运行约 1-2 分钟，后续增量运行约 30-60 秒。主要耗时在 YouTube 视频获取和 Hacker News 文章下载。

**Q: 日报在哪里看？**
A: 运行后自动输出到 `output/YYYY-MM-DD/daily_report.md`。

**Q: 可以每天自动运行吗？**
A: 可以。使用 cron job 或 Hermes Cron Job 设置定时任务。

**Q: Product Hunt 怎么没有投票数？**
A: 网页降级模式无法获取实时投票数。配置 `PRODUCT_HUNT_TOKEN` 后可通过 API 获取。

**Q: YouTube 字幕获取失败怎么办？**
A: 字幕获取失败不影响采集。Collector 会自动跳过，日志中会记录失败原因。

---

## 📄 License

MIT
