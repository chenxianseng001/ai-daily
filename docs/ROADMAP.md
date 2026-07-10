# Roadmap

## ✅ 已完成

| 阶段 | 状态 | 说明 |
|---|---|---|
| v1.0 Core | ✅ | 6 个数据源 Collect → Report 闭环 |
| v1.0 Polish | ✅ | 测试、配置、错误处理 |
| v1.1 Intelligence | ✅ | Event Clustering, AI Summary |
| v1.2 Productization | ✅ | 文档、排版、用户引导 |
| v2.0 MCP Server | ✅ | 10 个 Tool，stdio 模式 |
| v2.0 Deployment | ✅ | systemd timer, venv, symlink |

## 🔜 下一阶段

### 1. GitHub Repository（优先级：高）

- 创建公开 GitHub 仓库
- LICENSE（MIT）
- GitHub Actions CI（自动运行测试）
- README 最终优化

### 2. 一周稳定性验证（优先级：高）

- 连续运行 7 天，验证无崩溃
- 检查每日日报完整性
- 验证增量采集正确性
- 检查日志无异常

### 3. Bug Fix Sprint（优先级：中）

- 修复已知问题
- 根据用户反馈优化

### 4. v2.0.0 Release（优先级：中）

- 正式版本发布
- Release Notes
- 社区反馈收集

## 🌟 远期规划

| 功能 | 优先级 | 说明 |
|---|---|---|
| Docker 一键部署 | P3 | 简化安装 |
| Web UI 历史日报 | P3 | 按日期浏览 |
| 飞书机器人自动推送 | P3 | 定时推送到群聊 |
| LLM 长文本摘要 | P3 | 跨源 AI 综合总结 |
| 趋势分析 | P4 | 基于历史数据的趋势发现 |
| 个性化推荐 | P4 | 根据兴趣筛选内容 |
