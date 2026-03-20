# 周行

`周行` 是一个面向 Python 科研仿真的 Agent-CLI。

当前实现采用双进程架构：

- `Go + Bubble Tea + Bubbles + Lip Gloss` 负责终端 TUI。
- `Python 3.12` 负责 agent runtime、会话存储、工具系统、DeepSeek 接口和长任务监控。

## 已实现能力

- 启动时列出 `.zhouxing/sessions/` 历史会话，并支持新建会话。
- 单会话上下文压缩与上下文占用统计。
- DeepSeek 官方兼容接口调用，默认模型 `deepseek-chat`。
- 离线 `mock` 模式，方便本地调试前后端与工具链。
- 基础代码工具：
  - `list_directory`
  - `read_file`
  - `search_text`
  - `write_file`
  - `insert_text`
  - `replace_in_file`
  - `run_command`
- `run_command` 支持长任务事件流：
  - stdout/stderr 实时输出
  - 20s, 60s, 3min, 10min, 30min, 2h, 5h, 10h 心跳
  - 资源摘要回传
- `sandbox/` 作为默认科研工作区。

## 目录结构

```text
cmd/zhouxing/          Go 入口
internal/tui/          Go TUI 与后端进程通信
zhouxing/              Python backend
sandbox/               科研脚本默认工作区
scripts/               烟测脚本
.zhouxing/sessions/    会话记录
start_zhouxing.bat     启动脚本
```

## 运行

1. 在根目录准备 `.env`，至少包含 `API_KEY`。
2. 运行 `start_zhouxing.bat`。
3. 首次启动会自动补齐根目录 `.venv` 与 `sandbox/.venv`。

示例环境变量见 `.env.example`。

## 离线烟测

不依赖真实模型即可验证后端和工具链：

```powershell
.\.venv\Scripts\python.exe scripts\smoke_backend.py
```

该脚本会：

- 创建临时会话
- 调用离线 mock agent
- 列出 `sandbox/` 目录
- 自动生成并运行 `sandbox/smoke_long_sim.py`
- 验证 20 秒心跳与最终收尾消息

## 真实回归

下面这个脚本会先强制触发一次 fallback 生成脚本，再重启后端载入同一会话并继续追问，专门用于回归“fallback 后会话继续对话”这个真实问题：

```powershell
.\.venv\Scripts\python.exe scripts\e2e_fallback_followup.py
```

运行它需要可用的 DeepSeek API Key。

## 调试日志

后台会把详细日志写到：

- `.zhouxing/logs/backend_latest.jsonl`
- `.zhouxing/logs/backend_YYYYMMDD_HHMMSS.jsonl`

日志内容包括：

- 前端发给 backend 的请求
- backend 发回前端的事件
- agent 每一轮工具/模型步骤
- DeepSeek 请求开始、成功、重试和异常
- 工具调用开始、结束与结果摘要
- fallback 和异常堆栈

## 架构说明

### Go TUI

- 负责会话选择、聊天输入、消息渲染、状态栏和工具事件展示。
- 通过 JSONL over stdio 与 Python backend 通信。

### Python backend

- `config.py`: 配置与目录初始化
- `sessions.py`: 会话与消息存储
- `context.py`: 上下文预算与压缩
- `llm.py`: DeepSeek 与 mock client
- `tools.py`: 工具注册与执行
- `monitor.py`: 资源监控
- `agent.py`: 工具调用循环
- `backend.py`: stdio 协议服务

## 当前注意点

- 在当前沙箱里未安装 `psutil` 时，资源监控会退化为 `basic` 模式，但 `run_command` 仍能工作。
- Go 依赖首次获取需要联网；如果本地还没有模块缓存，需要执行 `go mod tidy` 或直接 `go run ./cmd/zhouxing`。
