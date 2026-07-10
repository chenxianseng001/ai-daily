# Architecture Decision Records

重大架构决策记录。

---

## ADR-001: MCP 保持 stdio，不采用 SSE

**日期：** 2026-07-10
**状态：** ✅ 已确认

### 背景

MCP Server 需要确定通信模式：stdio 还是 SSE。

### 选项

- **stdio**：Hermes 通过子进程启动 MCP Server，stdin/stdout 通信
- **SSE**：MCP Server 监听 HTTP 端口，通过 SSE 通信

### 决策

选择 **stdio**。

### 理由

1. 当前仅 Hermes 一个客户端，不需要多客户端支持
2. stdio 更简单（无端口/防火墙/守护进程管理）
3. stdio 更安全（不暴露网络端口）
4. Hermes 管理 MCP 生命周期
5. 未来需要多客户端时，可以增量添加 SSE

### 结果

- systemd 不管理 MCP Server
- Hermes 在 `config.yaml` 中通过 stdio 配置 MCP
- 无需端口管理、firewall rules

---

## ADR-002: 数据目录采用 symlink 实现分离

**日期：** 2026-07-10
**状态：** ✅ 已确认

### 背景

生产部署需要代码与数据分离：代码在 `app/`，数据在顶层目录。

### 选项

- **Code Changes**：修改所有路径引用，从 `PROJECT_ROOT` 改为环境变量
- **Symlink**：在 `app/` 中创建符号链接指向顶层数据目录

### 决策

选择 **Symlink**。

### 理由

1. 零代码修改——所有相对路径（`storage/`、`output/` 等）自动解析到顶层
2. 升级简单——替换 `app/` 后重建 4 条 symlink 即可
3. 开发/生产环境一致——开发环境可以直接使用 `./storage/`
4. 回滚容易——只需 `ln -sf` 修正链接

### 结果

- `app/storage → /opt/ai-daily/storage`
- `app/output → /opt/ai-daily/output`
- `app/logs → /opt/ai-daily/logs`
- `app/cache → /opt/ai-daily/cache`

---

## ADR-003: systemd 仅管理 AI Daily Timer，不管理 MCP

**日期：** 2026-07-10
**状态：** ✅ 已确认

### 背景

生产环境需要定时运行 AI Daily 采集。MCP Server 由 Hermes 管理。

### 选项

- **systemd 管理全部**：timer + service + MCP SSE daemon
- **systemd 仅管 timer**：MCP 由 Hermes 管理（stdio）

### 决策

选择 **仅管 timer**。

### 理由

1. Hermes 已经在 VM 中长期运行
2. MCP 使用 stdio 模式，由 Hermes 管理生命周期
3. 减少 systemd 复杂度
4. 未来需要多客户端时，再增加 SSE 模式

### 结果

- `ai-daily.service`（oneshot）：执行 `run_daily.py`
- `ai-daily.timer`（06:00 CST）：定时触发 service
- MCP Server 由 Hermes 通过 `mcpServers` stdio 配置管理

---

## ADR-004: Hacker News 使用官方 Firebase API

**日期：** 2026-07-10
**状态：** ✅ 已确认

直接使用 Firebase API 而非网页爬取。无需 API Key，稳定可靠。

---

## ADR-005: YouTube 使用 yt-dlp 而非 API

**日期：** 2026-07-10
**状态：** ✅ 已确认

使用 `yt-dlp` 获取频道视频列表和详情。字幕使用 yt-dlp 内置字幕下载（成功率 96%），远超 `youtube-transcript-api`（0%）。
