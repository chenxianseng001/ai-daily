# Changelog

所有重要更改记录在此文件。

格式基于 [Keep a Changelog](https://keepachangelog.com/)。
版本号遵循 [Semantic Versioning](https://semver.org/)。

---

## [v2.0.0-rc1] — 2026-07-10

### 🚀 生产部署

- 项目部署到 `/opt/ai-daily/` 正式生产目录
- 创建 Python venv `/opt/ai-daily/venv/`（隔离系统 Python）
- 代码与数据分离（symlink 实现）
- systemd service + timer 部署（每天 06:00 自动运行）
- MCP Server 保持 stdio 模式，由 Hermes 管理

### 🏗️ 架构

- 数据目录使用 symlink 实现分离，无需修改代码
- MCP 保持 stdio，不采用 SSE（仅 Hermes 使用）

### ✅ 测试

- 101 个测试用例，8 个测试文件

---

## [v2.0.0-dev] — 开发阶段

### ✨ 新功能

- 6 个数据源完整支持（GitHub/HN/PH/YouTube/Twitter/China AI）
- 统一 ReportBuilder + 模块化 Section 架构
- Event Clustering（事件聚类）
- AI Summary（8 个 Provider：OpenAI/DeepSeek/Gemini/Claude/…）
- MCP Server（10 个 Tool，只读本地）
- 统一配置中心（config.yaml + 环境变量覆盖）
- 增量采集（state 管理）
- Nitter 多实例容错（健康检查 + 自动切换）
- YouTube 字幕获取（yt-dlp，96% 成功率）

### 🔧 优化

- YouTube 采集性能优化（158s → 43s，-73%）
- HN 文章缓存（相同 URL 不重复下载）
- 统一 HTTP 客户端（限流 + 重试 + 超时）
- 代码与数据分离架构

### 📝 文档

- README 重写（新用户导向）
- MCP_CONFIG.md 配置文档
- PROJECT_STATUS.md / ARCHITECTURE.md / DECISIONS.md
