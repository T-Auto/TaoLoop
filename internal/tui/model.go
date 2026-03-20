package tui

import (
	"fmt"
	"strings"

	"github.com/charmbracelet/bubbles/list"
	"github.com/charmbracelet/bubbles/spinner"
	"github.com/charmbracelet/bubbles/textarea"
	"github.com/charmbracelet/bubbles/viewport"
	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"
)

type mode int

const (
	modeLoading mode = iota
	modeSessionPicker
	modeChat
)

var (
	pageStyle = lipgloss.NewStyle().
			Background(lipgloss.Color("#000000")).
			Foreground(lipgloss.Color("#F2F2F2")).
			Padding(1, 2)
	panelStyle = lipgloss.NewStyle().
			Border(lipgloss.RoundedBorder()).
			BorderForeground(lipgloss.Color("#4D4D4D")).
			Background(lipgloss.Color("#0B0B0B")).
			Padding(0, 1)
	headerStyle = lipgloss.NewStyle().
			Bold(true).
			Foreground(lipgloss.Color("#FFFFFF"))
	subtleStyle = lipgloss.NewStyle().
			Foreground(lipgloss.Color("#A6A6A6"))
	userBlockStyle = lipgloss.NewStyle().
			BorderLeft(true).
			BorderForeground(lipgloss.Color("#FFFFFF")).
			PaddingLeft(1).
			Foreground(lipgloss.Color("#FFFFFF"))
	assistantBlockStyle = lipgloss.NewStyle().
				BorderLeft(true).
				BorderForeground(lipgloss.Color("#BFBFBF")).
				PaddingLeft(1).
				Foreground(lipgloss.Color("#E6E6E6"))
	toolBlockStyle = lipgloss.NewStyle().
			BorderLeft(true).
			BorderForeground(lipgloss.Color("#7F7F7F")).
			PaddingLeft(1).
			Foreground(lipgloss.Color("#D0D0D0"))
	eventBlockStyle = lipgloss.NewStyle().
			BorderLeft(true).
			BorderForeground(lipgloss.Color("#4D4D4D")).
			PaddingLeft(1).
			Foreground(lipgloss.Color("#9F9F9F"))
	codeLineStyle = lipgloss.NewStyle().
			Background(lipgloss.Color("#111111")).
			Foreground(lipgloss.Color("#F5F5F5")).
			Padding(0, 1)
	commandLineStyle = lipgloss.NewStyle().
				Background(lipgloss.Color("#1A1A1A")).
				Foreground(lipgloss.Color("#FFFFFF")).
				Bold(true).
				Padding(0, 1)
	statusStyle = lipgloss.NewStyle().
			Background(lipgloss.Color("#111111")).
			Foreground(lipgloss.Color("#F2F2F2")).
			Padding(0, 1)
	primaryKeyStyle = lipgloss.NewStyle().
			Foreground(lipgloss.Color("#4EA1FF")).
			Bold(true)
	dangerKeyStyle = lipgloss.NewStyle().
			Foreground(lipgloss.Color("#FF5F5F")).
			Bold(true)
	confirmTitleStyle = lipgloss.NewStyle().
				Foreground(lipgloss.Color("#FF7A7A")).
				Bold(true)
	confirmPanelStyle = panelStyle.Copy().
				BorderForeground(lipgloss.Color("#FF5F5F")).
				Background(lipgloss.Color("#120C0C")).
				Padding(1, 2)
)

type sessionItem struct {
	summary   SessionSummary
	createNew bool
}

func (i sessionItem) Title() string {
	if i.createNew {
		return "＋ 新建会话"
	}
	return i.summary.Title
}

func (i sessionItem) Description() string {
	if i.createNew {
		return "创建一个新的单会话上下文"
	}
	return fmt.Sprintf("更新时间 %s | %d 条消息", i.summary.UpdatedAt, i.summary.MessageCount)
}

func (i sessionItem) FilterValue() string {
	if i.createNew {
		return "new session"
	}
	return i.summary.Title + " " + i.summary.Summary
}

type backendEventMsg struct {
	event Event
}

type backendClosedMsg struct{}

type Model struct {
	rootDir string
	backend *BackendClient
	events  <-chan Event

	mode     mode
	width    int
	height   int
	ready    *ReadyPayload
	status   StatusPayload
	lastErr  string
	spinner  spinner.Model
	list     list.Model
	viewport viewport.Model
	input    textarea.Model

	sessions      []SessionSummary
	activeSession *SessionRecord
	followTail    bool
	pendingDelete *SessionSummary
}

func New(rootDir string) (Model, error) {
	backend, err := StartBackend(rootDir)
	if err != nil {
		return Model{}, err
	}

	spin := spinner.New()
	spin.Spinner = spinner.Dot
	spin.Style = lipgloss.NewStyle().Foreground(lipgloss.Color("#FFFFFF"))

	delegate := list.NewDefaultDelegate()
	delegate.ShowDescription = true
	sessionList := list.New([]list.Item{sessionItem{createNew: true}}, delegate, 40, 12)
	sessionList.Title = "周行 / 选择会话"
	sessionList.SetShowHelp(false)
	sessionList.SetShowStatusBar(false)
	sessionList.SetFilteringEnabled(true)

	input := textarea.New()
	input.Placeholder = "输入消息，Enter 发送，Ctrl+L 返回会话列表，Ctrl+N 新建会话"
	input.Prompt = "│ "
	input.ShowLineNumbers = false
	input.SetHeight(4)
	input.Focus()

	vp := viewport.New(40, 12)

	return Model{
		rootDir:    rootDir,
		backend:    backend,
		events:     backend.Events(),
		mode:       modeLoading,
		spinner:    spin,
		list:       sessionList,
		viewport:   vp,
		input:      input,
		followTail: true,
	}, nil
}

func (m Model) Init() tea.Cmd {
	return tea.Batch(waitBackendEvent(m.events), m.spinner.Tick)
}

func waitBackendEvent(events <-chan Event) tea.Cmd {
	return func() tea.Msg {
		event, ok := <-events
		if !ok {
			return backendClosedMsg{}
		}
		return backendEventMsg{event: event}
	}
}

func (m Model) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	switch msg := msg.(type) {
	case tea.WindowSizeMsg:
		m.width = msg.Width
		m.height = msg.Height
		m.updateLayout()
		return m, nil
	case spinner.TickMsg:
		var cmd tea.Cmd
		m.spinner, cmd = m.spinner.Update(msg)
		return m, cmd
	case backendClosedMsg:
		m.lastErr = "后端已退出"
		return m, tea.Quit
	case backendEventMsg:
		m.applyEvent(msg.event)
		return m, waitBackendEvent(m.events)
	case tea.MouseMsg:
		if m.mode == modeChat {
			return m.updateChatMouse(msg)
		}
	case tea.KeyMsg:
		switch msg.String() {
		case "ctrl+c", "q":
			_ = m.backend.Close()
			return m, tea.Quit
		}
		if m.mode == modeSessionPicker {
			return m.updateSessionPicker(msg)
		}
		if m.mode == modeChat {
			return m.updateChat(msg)
		}
	}
	return m, nil
}

func (m Model) View() string {
	if m.width == 0 || m.height == 0 {
		return "初始化界面中..."
	}

	switch m.mode {
	case modeLoading:
		body := panelStyle.Width(maxInt(40, m.width-8)).Render(
			headerStyle.Render("周行") + "\n" +
				subtleStyle.Render("连接 Python backend 与会话存储...") + "\n\n" +
				m.spinner.View() + " " + subtleStyle.Render("等待后端就绪"),
		)
		return pageStyle.Render(body)
	case modeSessionPicker:
		titleLines := []string{
			headerStyle.Render("周行"),
			subtleStyle.Render("载入历史会话或新建会话"),
		}
		if m.lastErr != "" {
			titleLines = append(titleLines, subtleStyle.Render("错误: "+m.lastErr))
		}
		title := strings.Join(titleLines, "\n")
		panelWidth := maxInt(48, m.width-8)
		panelInnerWidth := maxInt(32, panelWidth-4)
		contentHeight := maxInt(10, m.height-14)
		content := m.list.View()
		if m.pendingDelete != nil {
			content = lipgloss.Place(panelInnerWidth, contentHeight, lipgloss.Center, lipgloss.Center, m.renderDeleteConfirmDialog(panelInnerWidth))
		}
		help := m.renderSessionPickerHelp()
		body := panelStyle.Width(panelWidth).Render(title + "\n\n" + content + "\n" + help)
		return pageStyle.Render(body)
	default:
		header := m.renderHeader()
		transcript := panelStyle.Height(maxInt(8, m.viewport.Height)).Render(m.viewport.View())
		input := panelStyle.Render(m.input.View())
		status := statusStyle.Width(maxInt(20, m.width-4)).Render(m.renderStatus())
		return pageStyle.Render(lipgloss.JoinVertical(lipgloss.Left, header, transcript, input, status))
	}
}

func (m Model) updateSessionPicker(msg tea.KeyMsg) (tea.Model, tea.Cmd) {
	if m.pendingDelete != nil {
		switch msg.String() {
		case "esc":
			m.pendingDelete = nil
			return m, nil
		case "enter":
			err := m.backend.Send(map[string]any{
				"type":       "delete_session",
				"session_id": m.pendingDelete.ID,
			})
			if err != nil {
				m.lastErr = err.Error()
				return m, nil
			}
			if m.activeSession != nil && m.activeSession.ID == m.pendingDelete.ID {
				m.activeSession = nil
			}
			m.pendingDelete = nil
			return m, nil
		}
		return m, nil
	}

	switch msg.String() {
	case "enter":
		item, ok := m.list.SelectedItem().(sessionItem)
		if !ok {
			return m, nil
		}
		if item.createNew {
			err := m.backend.Send(map[string]any{"type": "create_session"})
			if err != nil {
				m.lastErr = err.Error()
			}
			return m, nil
		}
		err := m.backend.Send(map[string]any{
			"type":       "load_session",
			"session_id": item.summary.ID,
		})
		if err != nil {
			m.lastErr = err.Error()
		}
		return m, nil
	case "delete":
		if m.list.SettingFilter() {
			break
		}
		item, ok := m.list.SelectedItem().(sessionItem)
		if !ok || item.createNew {
			return m, nil
		}
		summary := item.summary
		m.pendingDelete = &summary
		return m, nil
	}

	var cmd tea.Cmd
	m.list, cmd = m.list.Update(msg)
	return m, cmd
}

func (m Model) updateChat(msg tea.KeyMsg) (tea.Model, tea.Cmd) {
	switch msg.String() {
	case "ctrl+l":
		m.mode = modeSessionPicker
		_ = m.backend.Send(map[string]any{"type": "list_sessions"})
		return m, nil
	case "ctrl+n":
		_ = m.backend.Send(map[string]any{"type": "create_session"})
		return m, nil
	case "ctrl+up", "alt+up":
		m.followTail = false
		m.viewport.LineUp(1)
		return m, nil
	case "ctrl+down", "alt+down":
		m.viewport.LineDown(1)
		m.followTail = m.viewport.AtBottom()
		return m, nil
	case "pgup", "ctrl+u":
		m.followTail = false
		m.viewport.HalfViewUp()
		return m, nil
	case "pgdown", "ctrl+d":
		m.viewport.HalfViewDown()
		m.followTail = m.viewport.AtBottom()
		return m, nil
	case "home":
		m.followTail = false
		m.viewport.GotoTop()
		return m, nil
	case "end":
		m.viewport.GotoBottom()
		m.followTail = true
		return m, nil
	case "enter":
		content := strings.TrimSpace(m.input.Value())
		if content == "" {
			return m, nil
		}
		err := m.backend.Send(map[string]any{
			"type":    "user_message",
			"content": content,
		})
		if err != nil {
			m.lastErr = err.Error()
			return m, nil
		}
		m.input.Reset()
		return m, nil
	}

	var cmd tea.Cmd
	m.input, cmd = m.input.Update(msg)
	return m, cmd
}

func (m Model) updateChatMouse(msg tea.MouseMsg) (tea.Model, tea.Cmd) {
	prevOffset := m.viewport.YOffset
	var cmd tea.Cmd
	m.viewport, cmd = m.viewport.Update(msg)
	if m.viewport.YOffset != prevOffset {
		m.followTail = m.viewport.AtBottom()
	}
	return m, cmd
}

func (m *Model) applyEvent(event Event) {
	switch event.Type {
	case "ready":
		m.ready = event.Ready
		if m.mode == modeLoading {
			m.mode = modeSessionPicker
		}
	case "session_list":
		m.sessions = event.Sessions
		m.refreshSessionList()
		if m.mode == modeLoading {
			m.mode = modeSessionPicker
		}
	case "session_loaded":
		if event.Session == nil {
			return
		}
		sessionCopy := *event.Session
		m.activeSession = &sessionCopy
		m.pendingDelete = nil
		m.mode = modeChat
		m.followTail = true
		m.rebuildViewport(true)
	case "message":
		if event.Message == nil || m.activeSession == nil {
			return
		}
		m.insertMessage(*event.Message, event.AfterMessageID)
		m.rebuildViewport(false)
	case "status":
		if event.Status != nil {
			m.status = *event.Status
		}
	case "progress":
		if event.Progress != nil {
			m.status.Phase = event.Progress.Phase
			if event.Progress.Model != "" {
				m.status.Model = event.Progress.Model
			}
			m.status.OfflineMode = event.Progress.OfflineMode
			m.status.Context = event.Progress.Context
		}
	case "tool_event":
		if event.Tool == nil || m.activeSession == nil {
			return
		}
		syntheticID := event.Tool.ID
		if syntheticID == "" {
			syntheticID = fmt.Sprintf("tool_event_%s_%s_%d", event.Tool.Tool, event.Tool.Phase, len(m.activeSession.Messages))
		}
		synthetic := ChatMessage{
			ID:        syntheticID,
			Role:      "event",
			Content:   formatToolEvent(*event.Tool),
			CreatedAt: "",
		}
		m.insertMessage(synthetic, event.Tool.AfterMessageID)
		m.rebuildViewport(false)
	case "error":
		m.lastErr = event.Error
		if m.activeSession != nil {
			m.insertMessage(ChatMessage{
				ID:      fmt.Sprintf("error_%d", len(m.activeSession.Messages)),
				Role:    "event",
				Content: "错误: " + event.Error,
			}, "")
			m.rebuildViewport(false)
		}
	case "stderr":
		m.lastErr = event.Stderr
	}
}

func (m *Model) refreshSessionList() {
	items := []list.Item{sessionItem{createNew: true}}
	for _, summary := range m.sessions {
		items = append(items, sessionItem{summary: summary})
	}
	m.list.SetItems(items)
}

func (m *Model) insertMessage(message ChatMessage, afterMessageID string) {
	if m.activeSession == nil {
		return
	}
	if afterMessageID == "" {
		m.activeSession.Messages = append(m.activeSession.Messages, message)
		return
	}
	index := -1
	for i, existing := range m.activeSession.Messages {
		if existing.ID == afterMessageID {
			index = i
			break
		}
	}
	if index < 0 {
		m.activeSession.Messages = append(m.activeSession.Messages, message)
		return
	}
	messages := make([]ChatMessage, 0, len(m.activeSession.Messages)+1)
	messages = append(messages, m.activeSession.Messages[:index+1]...)
	messages = append(messages, message)
	messages = append(messages, m.activeSession.Messages[index+1:]...)
	m.activeSession.Messages = messages
}

func (m *Model) updateLayout() {
	if m.width <= 0 || m.height <= 0 {
		return
	}
	contentWidth := maxInt(32, m.width-8)
	headerHeight := 3
	statusHeight := 1
	inputHeight := 6
	bodyHeight := maxInt(10, m.height-headerHeight-statusHeight-inputHeight-6)

	m.list.SetSize(contentWidth, maxInt(10, m.height-8))
	m.viewport.Width = contentWidth - 4
	m.viewport.Height = bodyHeight
	m.input.SetWidth(contentWidth - 4)
	m.input.SetHeight(4)
	m.rebuildViewport(false)
}

func (m *Model) rebuildViewport(forceBottom bool) {
	if m.activeSession == nil {
		m.viewport.SetContent("")
		return
	}
	atBottom := forceBottom || m.followTail || m.viewport.AtBottom()
	offset := m.viewport.YOffset
	blocks := make([]string, 0, len(m.activeSession.Messages))
	for _, message := range m.activeSession.Messages {
		blocks = append(blocks, renderChatMessage(message, m.viewport.Width))
	}
	m.viewport.SetContent(strings.Join(blocks, "\n\n"))
	if atBottom {
		m.viewport.GotoBottom()
		m.followTail = true
		return
	}
	m.viewport.SetYOffset(offset)
	m.followTail = m.viewport.AtBottom()
}

func (m Model) renderHeader() string {
	title := "周行"
	if m.activeSession != nil {
		title = m.activeSession.Title
	}
	meta := []string{}
	if m.ready != nil {
		meta = append(meta, "model "+m.ready.Model)
		meta = append(meta, "sandbox "+m.ready.SandboxDir)
		if m.ready.OfflineMode {
			meta = append(meta, "offline")
		}
	}
	if m.lastErr != "" {
		meta = append(meta, "error "+m.lastErr)
	}
	return panelStyle.Width(maxInt(20, m.width-8)).Render(
		headerStyle.Render(title) + "\n" + subtleStyle.Render(strings.Join(meta, "  |  ")),
	)
}

func (m Model) renderStatus() string {
	state := "idle"
	if m.status.Busy {
		state = m.spinner.View() + " " + m.status.Phase
	} else if m.status.Phase != "" {
		state = m.status.Phase
	}
	ctx := fmt.Sprintf("ctx %d/%d", m.status.Context.UsedTokens, m.status.Context.LimitTokens)
	queue := fmt.Sprintf("queue %d", m.status.QueueLength)
	help := "Enter 发送  PgUp/PgDn/鼠标滚轮滚动  End 回底  Ctrl+L 会话"
	return strings.Join([]string{state, m.status.Model, ctx, queue, help}, "  |  ")
}

func (m Model) renderSessionPickerHelp() string {
	parts := []string{
		primaryKeyStyle.Render("Enter") + subtleStyle.Render(" 打开"),
		subtleStyle.Render("←/→ 翻页"),
		dangerKeyStyle.Render("Delete") + subtleStyle.Render(" 删除会话"),
		subtleStyle.Render("/ 搜索"),
		subtleStyle.Render("q 退出"),
	}
	return strings.Join(parts, "  ")
}

func (m Model) renderDeleteConfirmDialog(availableWidth int) string {
	if m.pendingDelete == nil {
		return ""
	}
	dialogWidth := minInt(64, maxInt(36, availableWidth-6))
	body := strings.Join([]string{
		confirmTitleStyle.Render("确认删除会话"),
		headerStyle.Render(m.pendingDelete.Title),
		subtleStyle.Render("删除后不可恢复。"),
		"",
		primaryKeyStyle.Render("Enter") + subtleStyle.Render(" 确认删除    ") + subtleStyle.Render("Esc 取消"),
	}, "\n")
	return confirmPanelStyle.Width(dialogWidth).Render(body)
}

func renderChatMessage(message ChatMessage, width int) string {
	label := strings.ToUpper(message.Role)
	if message.Role == "tool" && message.Name != "" {
		label = "TOOL/" + strings.ToUpper(message.Name)
	}
	if message.Role == "event" {
		label = "EVENT"
	}

	body := styleMessageBody(message.Content, maxInt(20, width-2))
	text := headerStyle.Render(label) + "\n" + body
	switch message.Role {
	case "user":
		return userBlockStyle.Width(width).Render(text)
	case "assistant":
		return assistantBlockStyle.Width(width).Render(text)
	case "tool":
		return toolBlockStyle.Width(width).Render(text)
	default:
		return eventBlockStyle.Width(width).Render(text)
	}
}

func styleMessageBody(content string, width int) string {
	lines := strings.Split(content, "\n")
	if len(lines) == 0 {
		return ""
	}
	var rendered []string
	inCode := false
	for _, line := range lines {
		trimmed := strings.TrimSpace(line)
		switch {
		case strings.HasPrefix(trimmed, "```"):
			inCode = !inCode
			continue
		case inCode:
			rendered = append(rendered, codeLineStyle.Width(width).Render(line))
		case strings.HasPrefix(trimmed, "$ ") || strings.HasPrefix(trimmed, "PS>") || strings.HasPrefix(trimmed, "command="):
			rendered = append(rendered, commandLineStyle.Width(width).Render(line))
		default:
			rendered = append(rendered, lipgloss.NewStyle().Width(width).Render(line))
		}
	}
	return strings.Join(rendered, "\n")
}

func formatToolEvent(event ToolEvent) string {
	switch event.Phase {
	case "call":
		return fmt.Sprintf("调用工具 %s args=%v", event.Tool, event.Arguments)
	case "start":
		return fmt.Sprintf("启动命令\ncommand=%s\ncwd=%s", event.Command, event.CWD)
	case "output":
		if event.Channel != "" {
			return fmt.Sprintf("[%s] %s", event.Channel, event.Text)
		}
		return event.Text
	case "output_truncated":
		return event.Text
	case "heartbeat":
		return fmt.Sprintf("运行中 %ds\n%s", event.AfterSec, event.Summary)
	case "timeout":
		return fmt.Sprintf("命令达到超时阈值 %ds", event.TimeoutSec)
	case "finish":
		return fmt.Sprintf("命令结束 exit=%d duration=%.2fs\n%s", event.ExitCode, event.DurationSec, event.Summary)
	default:
		return fmt.Sprintf("%s: %s", event.Phase, event.Summary)
	}
}

func maxInt(a, b int) int {
	if a > b {
		return a
	}
	return b
}

func minInt(a, b int) int {
	if a < b {
		return a
	}
	return b
}
