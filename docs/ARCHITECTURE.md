# AI Daily — Architecture

## 整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                    采集层 (Collector)                            │
│                                                                 │
│  GitHub     HN      PH      YouTube   Twitter    China AI       │
│   ↓          ↓       ↓         ↓         ↓          ↓          │
│  JSON+raw  JSON+raw JSON+raw  JSON+raw  JSON+raw  JSON+raw     │
│   ↓          ↓       ↓         ↓         ↓          ↓          │
├─────────────────────────────────────────────────────────────────┤
│                   存储层 (Storage)                                │
│                                                                 │
│  /opt/ai-daily/storage/ (符号链接)                               │
│    ├── {source}/json/YYYY-MM-DD.json  (标准化 JSON)              │
│    └── {source}/raw/YYYY-MM-DD/       (原始内容)                 │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│                    报告层 (Reporter)                              │
│                                                                 │
│  Event Clustering → AI Summary（可选）→ Section 渲染 → Markdown  │
│                                                                 │
│  输出: /opt/ai-daily/output/YYYY-MM-DD/daily_report.md          │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│                    服务层 (MCP Server)                            │
│                                                                 │
│  10 Tools (stdio 模式, 仅本地读取)                                │
│  Hermes 通过 stdio 管理                                           │
└─────────────────────────────────────────────────────────────────┘
```

## 分层原则

| 层 | 职责 | 网络 | 依赖 |
|---|---|---|---|
| Collector | 采集原始数据 | ✅ 允许联网 | 外部 API / RSS |
| Storage | 缓存数据（JSON + raw） | ❌ | 本地文件系统 |
| Reporter | 生成日报 | ❌ 只读本地 | 本地缓存 |
| MCP Server | 对外提供查询 | ❌ stdio 通信 | 本地缓存 |

## Data Contract

所有数据源使用统一的 JSON Schema：

```json
{
  "id": "唯一标识",
  "title": "标题",
  "description": "简述",
  "author": "作者",
  "published_at": "ISO 时间",
  "url": "原文链接",
  "raw_score": "热度分",
  "content_hash": "内容 MD5（用于去重/缓存）",
  "tags": ["标签"],
  "language": "语言",
  "category": "分类",
  "raw": {
    "源特有字段": "..."
  }
}
```

## 状态流

```
图例: [Collector] → [JSON] → [Reporter]
      ↘ [state] 跟踪增量
      ↙ [raw] 保存原始内容

第 1 天: 全量采集 → 生成日报
第 2 天: 增量采集 → 更新日报
第 N 天: 持续增量 → 每日新报
```

## 容错机制

- 单个 Collector 失败不影响其他 5 个
- 连续 3 次失败自动禁用该数据源
- 字幕获取失败跳过单个视频
- Nitter 多实例健康检查，自动切换
