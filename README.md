# “周行”

> 有物混成，先天地生。寂兮寥兮，独立而不改，周行而不殆，可以为天下母，出自《道德经》第二十五章。**周行**，即“道”循环运行、永不停息
>
> 这正是周行（TaoLoop-cli）的目标——不眠不休，周而复始地遍历所有参数，所有路径，所有可能性，寻找宇宙的规律



`周行 / TaoLoop-cli` 是一个专注于科研的Agent-CLI，与常规Agent-CLI项目相比：

- 专注科研、数据处理与仿真，支持为复杂学术难题启动深入研究与集群推理
- 自动监看算力资源占用与OOM / 进程挂起，守护长时仿真/训练进程，避免算力资源浪费
- 支持tools扩展与外部工具调用，支持自主操作物理实验平台
- 轻量化，token节省，支持24小时待机



## 目录结构

当前实现采用双进程架构：

- `Go + Bubble Tea + Bubbles + Lip Gloss` 负责终端 TUI
- `Python 3.12` 负责 agent runtime、会话存储、工具系统、DeepSeek 接口和长任务监控

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

聊天界面默认运行在可复制文本的终端模式下，可直接用终端鼠标拖选内容；输入时建议使用 `Ctrl+V` 或 `Insert` 从系统剪贴板粘贴，也可以按 `Ctrl+Y` 或 `F5` 将当前会话全文复制到系统剪贴板。
