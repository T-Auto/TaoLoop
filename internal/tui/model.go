package tui

import (
	"fmt"
	"strings"
	"time"
	"unicode"

	"github.com/atotto/clipboard"
	"github.com/charmbracelet/bubbles/list"
	"github.com/charmbracelet/bubbles/spinner"
	"github.com/charmbracelet/bubbles/textarea"
	"github.com/charmbracelet/bubbles/viewport"
	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"
	"github.com/charmbracelet/x/ansi"
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
	logHeaderStyle = lipgloss.NewStyle().
			Bold(true).
			Foreground(lipgloss.Color("#F2F2F2"))
	logLineStyle = lipgloss.NewStyle().
			Foreground(lipgloss.Color("#7F7F7F"))
	logOmittedStyle = lipgloss.NewStyle().
			Foreground(lipgloss.Color("#5F5F5F"))
	codeLineStyle = lipgloss.NewStyle().
			Background(lipgloss.Color("#111111")).
			Foreground(lipgloss.Color("#F5F5F5")).
			Padding(0, 1)
	codeAddLineStyle = lipgloss.NewStyle().
				Background(lipgloss.Color("#0B1610")).
				Foreground(lipgloss.Color("#E7F6EC")).
				Padding(0, 1)
	codeDeleteLineStyle = lipgloss.NewStyle().
				Background(lipgloss.Color("#1A0D0D")).
				Foreground(lipgloss.Color("#F8E1E1")).
				Padding(0, 1)
	commandLineStyle = lipgloss.NewStyle().
				Background(lipgloss.Color("#1A1A1A")).
				Foreground(lipgloss.Color("#FFFFFF")).
				Bold(true).
				Padding(0, 1)
	codeLineNumberStyle = lipgloss.NewStyle().
				Foreground(lipgloss.Color("#6C7480"))
	codeKeywordTokenStyle = lipgloss.NewStyle().
				Foreground(lipgloss.Color("#7CC4FF")).
				Bold(true)
	codeStringTokenStyle = lipgloss.NewStyle().
				Foreground(lipgloss.Color("#8DD694"))
	codeCommentTokenStyle = lipgloss.NewStyle().
				Foreground(lipgloss.Color("#6E7781"))
	codeNumberTokenStyle = lipgloss.NewStyle().
				Foreground(lipgloss.Color("#F2C66D"))
	commandPromptTokenStyle = lipgloss.NewStyle().
				Foreground(lipgloss.Color("#7CC4FF")).
				Bold(true)
	commandExecTokenStyle = lipgloss.NewStyle().
				Foreground(lipgloss.Color("#FFFFFF")).
				Bold(true)
	commandFlagTokenStyle = lipgloss.NewStyle().
				Foreground(lipgloss.Color("#7CC4FF"))
	commandPathTokenStyle = lipgloss.NewStyle().
				Foreground(lipgloss.Color("#F2C66D"))
	commandStringTokenStyle = lipgloss.NewStyle().
				Foreground(lipgloss.Color("#8DD694"))
	commandOperatorTokenStyle = lipgloss.NewStyle().
					Foreground(lipgloss.Color("#A6A6A6"))
	commandMetaTokenStyle = lipgloss.NewStyle().
				Foreground(lipgloss.Color("#8C8C8C"))
	stderrTokenStyle = lipgloss.NewStyle().
				Foreground(lipgloss.Color("#FF8A8A")).
				Bold(true)
	diffAddMarkerStyle = lipgloss.NewStyle().
				Foreground(lipgloss.Color("#70D88A")).
				Bold(true)
	diffDeleteMarkerStyle = lipgloss.NewStyle().
				Foreground(lipgloss.Color("#FF8A8A")).
				Bold(true)
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

var writeClipboard = clipboard.WriteAll
var readClipboard = clipboard.ReadAll
var timeNow = time.Now

const pasteBurstWindow = 40 * time.Millisecond

const (
	foldedPreviewHeadLines = 2
	foldedPreviewTailLines = 2
	defaultInputHeight     = 4
)

type diffKind int

const (
	diffNone diffKind = iota
	diffAdd
	diffDelete
)

var codeKeywords = map[string]struct{}{
	"and": {}, "as": {}, "async": {}, "await": {}, "break": {}, "case": {}, "catch": {},
	"class": {}, "const": {}, "continue": {}, "def": {}, "default": {}, "defer": {}, "do": {},
	"elif": {}, "else": {}, "except": {}, "export": {}, "extends": {}, "false": {}, "finally": {},
	"fn": {}, "for": {}, "from": {}, "func": {}, "function": {}, "if": {}, "implements": {},
	"import": {}, "in": {}, "interface": {}, "let": {}, "match": {}, "new": {}, "nil": {},
	"none": {}, "not": {}, "null": {}, "or": {}, "package": {}, "pass": {}, "private": {},
	"protected": {}, "public": {}, "raise": {}, "range": {}, "return": {}, "self": {},
	"static": {}, "struct": {}, "super": {}, "switch": {}, "this": {}, "throw": {}, "true": {},
	"try": {}, "type": {}, "var": {}, "while": {}, "with": {}, "yield": {},
}

type pageLayout struct {
	width  int
	height int
}

type chatLayout struct {
	pageWidth         int
	pageHeight        int
	panelContentWidth int
	transcriptHeight  int
	inputHeight       int
	valid             bool
}

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
	notice   string
	spinner  spinner.Model
	list     list.Model
	viewport viewport.Model
	input    textarea.Model

	sessions         []SessionSummary
	activeSession    *SessionRecord
	followTail       bool
	collapseToolLogs bool
	printedBlockKeys map[string]struct{}
	pendingDelete    *SessionSummary

	lastTextInputAt  time.Time
	likelyPasteBurst bool
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
	input.Placeholder = "输入消息，Enter 发送，Ctrl+V/Insert 粘贴，Ctrl+O 折叠日志，Ctrl+Y/F5 复制，Ctrl+L 会话列表"
	input.Prompt = "│ "
	input.ShowLineNumbers = false
	input.SetHeight(4)
	input.Focus()

	vp := viewport.New(40, 12)

	return Model{
		rootDir:          rootDir,
		backend:          backend,
		events:           backend.Events(),
		mode:             modeLoading,
		spinner:          spin,
		list:             sessionList,
		viewport:         vp,
		input:            input,
		followTail:       true,
		collapseToolLogs: true,
		printedBlockKeys: map[string]struct{}{},
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
		cmd := m.applyEvent(msg.event)
		return m, tea.Batch(cmd, waitBackendEvent(m.events))
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
	if m.mode == modeChat {
		return m.updateChatInput(msg)
	}
	return m, nil
}

func (m Model) View() string {
	if m.width == 0 || m.height == 0 {
		return "初始化界面中..."
	}

	switch m.mode {
	case modeLoading:
		return strings.Join([]string{
			"周行",
			m.spinner.View() + " 连接 Python backend 与会话存储...",
		}, "\n")
	case modeSessionPicker:
		return m.renderSessionPickerView()
	default:
		return m.renderChatView()
	}
}

func (m Model) renderSessionPickerView() string {
	lines := []string{
		"周行 / 会话",
		"载入历史会话或新建会话",
	}
	if m.lastErr != "" {
		lines = append(lines, "错误: "+m.lastErr)
	}
	content := m.list.View()
	if m.pendingDelete != nil {
		content = m.renderDeleteConfirmDialog(maxInt(1, m.width))
	}
	lines = append(lines, "", content, "", m.renderSessionPickerHelp())
	return strings.Join(lines, "\n")
}

func (m Model) renderChatView() string {
	status := truncateToWidth(m.renderStatus(), maxInt(1, m.width))
	return strings.Join([]string{
		status,
		m.input.View(),
	}, "\n")
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
	case "ctrl+v", "insert":
		return m.pasteIntoInput()
	case "ctrl+y", "f5":
		if err := m.copyActiveSessionToClipboard(); err != nil {
			m.notice = ""
			m.lastErr = err.Error()
			return m, nil
		}
		m.notice = "已复制当前会话到系统剪贴板"
		return m, nil
	case "ctrl+o":
		m.collapseToolLogs = !m.collapseToolLogs
		if m.collapseToolLogs {
			m.notice = "工具日志已折叠"
		} else {
			m.notice = "工具日志已展开"
		}
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
		if m.shouldTreatEnterAsPastedNewline() {
			m.input.InsertString("\n")
			m.markLikelyPaste()
			return m, nil
		}
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
		m.likelyPasteBurst = false
		m.lastTextInputAt = time.Time{}
		return m, nil
	}

	m.trackTextEntry(msg)
	return m.updateChatInput(msg)
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

func (m Model) updateChatInput(msg tea.Msg) (tea.Model, tea.Cmd) {
	var cmd tea.Cmd
	m.input, cmd = m.input.Update(msg)
	return m, cmd
}

func (m *Model) applyEvent(event Event) tea.Cmd {
	switch event.Type {
	case "ready":
		m.ready = event.Ready
		if m.mode == modeLoading {
			m.mode = modeSessionPicker
		}
		return nil
	case "session_list":
		m.sessions = event.Sessions
		m.refreshSessionList()
		if m.mode == modeLoading {
			m.mode = modeSessionPicker
		}
		return nil
	case "session_loaded":
		if event.Session == nil {
			return nil
		}
		sessionCopy := *event.Session
		m.activeSession = &sessionCopy
		m.pendingDelete = nil
		m.mode = modeChat
		m.followTail = true
		m.rebuildViewport(true)
		return m.flushTranscriptPrintCmd(true)
	case "message":
		if event.Message == nil || m.activeSession == nil {
			return nil
		}
		m.insertMessage(*event.Message, event.AfterMessageID)
		m.rebuildViewport(false)
		return m.flushTranscriptPrintCmd(false)
	case "status":
		if event.Status != nil {
			m.status = *event.Status
		}
		return nil
	case "progress":
		if event.Progress != nil {
			m.status.Phase = event.Progress.Phase
			if event.Progress.Model != "" {
				m.status.Model = event.Progress.Model
			}
			m.status.OfflineMode = event.Progress.OfflineMode
			m.status.Context = event.Progress.Context
		}
		return nil
	case "tool_event":
		if event.Tool == nil || m.activeSession == nil {
			return nil
		}
		synthetic := makeSyntheticToolEventMessage(*event.Tool, len(m.activeSession.Messages))
		m.insertMessage(synthetic, event.Tool.AfterMessageID)
		m.rebuildViewport(false)
		return m.flushTranscriptPrintCmd(false)
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
		return m.flushTranscriptPrintCmd(false)
	case "stderr":
		m.lastErr = event.Stderr
		return nil
	}
	return nil
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

	listWidth := maxInt(1, m.width)
	listHeight := maxInt(1, m.height-4)
	m.list.SetSize(listWidth, listHeight)

	inputHeight := defaultInputHeight
	if m.height <= 2 {
		inputHeight = 1
	} else if m.height-1 < inputHeight {
		inputHeight = m.height - 1
	}
	if inputHeight < 1 {
		inputHeight = 1
	}

	m.viewport.Width = maxInt(1, m.width)
	m.viewport.Height = maxInt(1, m.height-inputHeight-1)
	m.input.SetWidth(maxInt(1, m.width))
	m.input.SetHeight(inputHeight)
	m.rebuildViewport(false)
}

func (m *Model) rebuildViewport(forceBottom bool) {
	if m.activeSession == nil {
		m.viewport.SetContent("")
		return
	}
	atBottom := forceBottom || m.followTail || m.viewport.AtBottom()
	offset := m.viewport.YOffset
	blocks := renderTranscriptBlocks(m.activeSession.Messages, m.viewport.Width, m.collapseToolLogs)
	m.viewport.SetContent(strings.Join(blocks, "\n\n"))
	if atBottom {
		m.viewport.GotoBottom()
		m.followTail = true
		return
	}
	m.viewport.SetYOffset(offset)
	m.followTail = m.viewport.AtBottom()
}

type transcriptPrintBlock struct {
	key  string
	text string
}

func (m *Model) flushTranscriptPrintCmd(reset bool) tea.Cmd {
	text := m.buildPendingTranscriptPrintText(reset)
	if strings.TrimSpace(text) == "" {
		return nil
	}
	return tea.Println(text)
}

func (m *Model) buildPendingTranscriptPrintText(reset bool) string {
	if reset || m.printedBlockKeys == nil {
		m.printedBlockKeys = map[string]struct{}{}
	}
	if m.activeSession == nil {
		return ""
	}

	blocks := buildTranscriptPrintBlocks(m.activeSession.Messages, m.collapseToolLogs)
	pending := make([]string, 0, len(blocks))
	for _, block := range blocks {
		if block.key == "" || strings.TrimSpace(block.text) == "" {
			continue
		}
		if _, exists := m.printedBlockKeys[block.key]; exists {
			continue
		}
		m.printedBlockKeys[block.key] = struct{}{}
		pending = append(pending, block.text)
	}
	return strings.Join(pending, "\n\n")
}

func buildTranscriptPrintBlocks(messages []ChatMessage, collapseToolLogs bool) []transcriptPrintBlock {
	blocks := make([]transcriptPrintBlock, 0, len(messages))
	for index := 0; index < len(messages); {
		message := messages[index]
		if shouldHideChatMessage(message) {
			index++
			continue
		}
		if collapseToolLogs {
			if group, next, ok := buildToolLogGroup(messages, index); ok {
				if group.result != nil {
					header, lines := summarizeToolLogGroup(group)
					blocks = append(blocks, transcriptPrintBlock{
						key:  group.result.ID,
						text: renderTerminalLogBlock(header, lines),
					})
				}
				index = next
				continue
			}
			if block, ok := renderCollapsedStandalonePrintBlock(message); ok {
				blocks = append(blocks, block)
				index++
				continue
			}
		}
		blocks = append(blocks, transcriptPrintBlock{
			key:  message.ID,
			text: renderTerminalMessage(message),
		})
		index++
	}
	return blocks
}

func renderCollapsedStandalonePrintBlock(message ChatMessage) (transcriptPrintBlock, bool) {
	if _, ok := messageToolEvent(message); ok {
		return transcriptPrintBlock{}, false
	}
	if message.Role != "tool" && metaString(message.Meta, "source_tool") == "" {
		return transcriptPrintBlock{}, false
	}
	header, lines := summarizeStandaloneToolMessage(message)
	return transcriptPrintBlock{
		key:  message.ID,
		text: renderTerminalLogBlock(header, lines),
	}, true
}

func renderTerminalMessage(message ChatMessage) string {
	body := strings.TrimRight(message.Content, "\n")
	if strings.TrimSpace(body) == "" {
		body = "(empty)"
	}
	switch message.Role {
	case "user":
		return renderTerminalPrefixedBody(body, "> ", "  ")
	case "event":
		return renderTerminalPrefixedBody(body, "! ", "  ")
	default:
		return renderTerminalBody(body)
	}
}

func renderTerminalLogBlock(header string, lines []string) string {
	preview := foldedPreviewLines(lines)
	if len(preview) == 0 {
		return renderTerminalHighlightedLogHeader(header)
	}
	rendered := []string{renderTerminalHighlightedLogHeader(header), renderTerminalHighlightedLogLine("└ ", preview[0], logLineStyle)}
	for _, line := range preview[1:] {
		style := logLineStyle
		if strings.HasPrefix(line, "… +") {
			style = logOmittedStyle
		}
		rendered = append(rendered, renderTerminalHighlightedLogLine("  ", line, style))
	}
	return strings.Join(rendered, "\n")
}

func renderTerminalPrefixedBody(body string, firstPrefix string, restPrefix string) string {
	lines := strings.Split(body, "\n")
	if len(lines) == 0 {
		return ""
	}
	inCode := false
	rendered := make([]string, 0, len(lines))
	for index, line := range lines {
		trimmed := strings.TrimSpace(line)
		if strings.HasPrefix(trimmed, "```") {
			inCode = !inCode
			continue
		}
		prefix := restPrefix
		if index == 0 {
			prefix = firstPrefix
		}
		rendered = append(rendered, prefix+renderTerminalBodyLine(line, inCode))
	}
	return strings.Join(rendered, "\n")
}

func renderTerminalBody(body string) string {
	lines := strings.Split(body, "\n")
	if len(lines) == 0 {
		return ""
	}
	inCode := false
	rendered := make([]string, 0, len(lines))
	for _, line := range lines {
		trimmed := strings.TrimSpace(line)
		if strings.HasPrefix(trimmed, "```") {
			inCode = !inCode
			continue
		}
		rendered = append(rendered, renderTerminalBodyLine(line, inCode))
	}
	return strings.Join(rendered, "\n")
}

func renderTerminalBodyLine(line string, inCode bool) string {
	trimmed := strings.TrimSpace(line)
	switch {
	case strings.HasPrefix(trimmed, "└"):
		return subtleStyle.Render(line)
	case inCode || looksLikeNumberedCodeLine(line):
		return renderTerminalCodeLine(line)
	case isCommandLine(trimmed):
		return renderTerminalCommandLine(line)
	default:
		return renderStructuredLineContent(line, false)
	}
}

func renderTerminalCodeLine(line string) string {
	content, diff := highlightCodeLineContent(line)
	switch diff {
	case diffAdd:
		return lipgloss.NewStyle().Foreground(lipgloss.Color("#70D88A")).Render(content)
	case diffDelete:
		return lipgloss.NewStyle().Foreground(lipgloss.Color("#FF8A8A")).Render(content)
	default:
		return content
	}
}

func renderTerminalCommandLine(line string) string {
	return highlightCommandText(line)
}

func renderTerminalHighlightedLogHeader(header string) string {
	if strings.HasPrefix(header, "• Ran ") {
		return logHeaderStyle.Render(
			commandMetaTokenStyle.Render("• Ran ") +
				highlightShellCommand(strings.TrimPrefix(header, "• Ran ")),
		)
	}
	return logHeaderStyle.Render(header)
}

func renderTerminalHighlightedLogLine(prefix string, line string, style lipgloss.Style) string {
	return style.Render(prefix + renderStructuredLineContent(line, true))
}

func prefixBlock(text string, firstPrefix string, restPrefix string) string {
	lines := strings.Split(text, "\n")
	for i, line := range lines {
		if i == 0 {
			lines[i] = firstPrefix + line
			continue
		}
		lines[i] = restPrefix + line
	}
	return strings.Join(lines, "\n")
}

func (m Model) computePageLayout() pageLayout {
	return pageLayout{
		width:  maxInt(1, m.width-pageStyle.GetHorizontalFrameSize()),
		height: maxInt(1, m.height-pageStyle.GetVerticalFrameSize()),
	}
}

func (m Model) computeChatLayout() chatLayout {
	page := m.computePageLayout()
	panelFrameW := panelStyle.GetHorizontalFrameSize()
	panelFrameH := panelStyle.GetVerticalFrameSize()

	if page.width < panelFrameW+8 {
		return chatLayout{pageWidth: page.width, pageHeight: page.height}
	}

	headerOuterHeight := 2 + panelFrameH
	statusHeight := 1
	minPanelOuterHeight := panelFrameH + 1
	remainingHeight := page.height - headerOuterHeight - statusHeight
	if remainingHeight < minPanelOuterHeight*2 {
		return chatLayout{pageWidth: page.width, pageHeight: page.height}
	}

	desiredInputOuterHeight := panelFrameH + defaultInputHeight
	inputOuterHeight := minInt(desiredInputOuterHeight, remainingHeight-minPanelOuterHeight)
	if inputOuterHeight < minPanelOuterHeight {
		inputOuterHeight = minPanelOuterHeight
	}
	transcriptOuterHeight := remainingHeight - inputOuterHeight
	if transcriptOuterHeight < minPanelOuterHeight {
		return chatLayout{pageWidth: page.width, pageHeight: page.height}
	}

	return chatLayout{
		pageWidth:         page.width,
		pageHeight:        page.height,
		panelContentWidth: maxInt(1, page.width-panelFrameW),
		transcriptHeight:  maxInt(1, transcriptOuterHeight-panelFrameH),
		inputHeight:       maxInt(1, inputOuterHeight-panelFrameH),
		valid:             true,
	}
}

func (m Model) renderWindowTooSmall(page pageLayout) string {
	panelContentWidth := contentWidthForStyle(page.width, panelStyle)
	body := panelStyle.Width(panelContentWidth).Render(
		headerStyle.Render(truncateToWidth("窗口过小", panelContentWidth)) + "\n" +
			subtleStyle.Render(truncateToWidth(fmt.Sprintf("当前 %dx%d，请放大终端。", m.width, m.height), panelContentWidth)),
	)
	return pageStyle.Render(body)
}

func (m Model) renderHeader(width int) string {
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
	return panelStyle.Width(maxInt(1, width)).Render(
		headerStyle.Render(truncateToWidth(title, width)) + "\n" +
			subtleStyle.Render(truncateToWidth(strings.Join(meta, "  |  "), width)),
	)
}

func (m Model) renderStatus() string {
	state := "idle"
	if m.status.Busy {
		state = m.spinner.View() + " " + m.status.Phase
	} else if m.status.Phase != "" {
		state = m.status.Phase
	}
	title := "周行"
	if m.activeSession != nil && m.activeSession.Title != "" {
		title = m.activeSession.Title
	}
	logState := "logs 展开"
	if m.collapseToolLogs {
		logState = "logs 折叠"
	}
	help := "Ctrl+Y/F5 复制  Ctrl+O 日志  Ctrl+L 会话"
	parts := []string{title, state}
	if m.status.Model != "" {
		parts = append(parts, m.status.Model)
	}
	parts = append(parts, logState)
	if m.notice != "" {
		parts = append(parts, m.notice)
	} else if m.lastErr != "" {
		parts = append(parts, "错误: "+m.lastErr)
	}
	parts = append(parts, help)
	return strings.Join(parts, "  |  ")
}

func (m Model) renderSessionPickerHelp() string {
	return "Enter 打开  ←/→ 翻页  Delete 删除会话  / 搜索  q 退出"
}

func (m Model) renderDeleteConfirmDialog(availableWidth int) string {
	if m.pendingDelete == nil {
		return ""
	}
	_ = availableWidth
	return strings.Join([]string{
		"确认删除会话",
		m.pendingDelete.Title,
		"删除后不可恢复。",
		"Enter 确认删除    Esc 取消",
	}, "\n")
}

func renderChatMessage(message ChatMessage, width int) string {
	label := chatMessageLabel(message)
	switch message.Role {
	case "user":
		return renderFramedMessage(userBlockStyle, label, message.Content, width)
	case "assistant":
		return renderFramedMessage(assistantBlockStyle, label, message.Content, width)
	case "tool":
		return renderFramedMessage(toolBlockStyle, label, message.Content, width)
	default:
		return renderFramedMessage(eventBlockStyle, label, message.Content, width)
	}
}

func renderFramedMessage(style lipgloss.Style, label string, content string, outerWidth int) string {
	contentWidth := contentWidthForStyle(outerWidth, style)
	body := styleMessageBody(content, contentWidth)
	text := headerStyle.Render(truncateToWidth(label, contentWidth)) + "\n" + body
	return style.Width(contentWidth).Render(text)
}

type toolLogGroup struct {
	call    ToolEvent
	hasCall bool
	events  []ToolEvent
	result  *ChatMessage
}

type runCommandSummary struct {
	Command    string
	CWD        string
	ExitCode   string
	Duration   string
	TimedOut   string
	Resources  string
	StdoutTail []string
	StderrTail []string
}

func makeSyntheticToolEventMessage(event ToolEvent, messageCount int) ChatMessage {
	syntheticID := event.ID
	if syntheticID == "" {
		syntheticID = fmt.Sprintf("tool_event_%s_%s_%d", event.Tool, event.Phase, messageCount)
	}
	return ChatMessage{
		ID:        syntheticID,
		Role:      "event",
		Content:   formatToolEvent(event),
		CreatedAt: "",
		Meta: map[string]any{
			"synthetic_tool_event": true,
			"tool_name":            event.Tool,
			"tool_phase":           event.Phase,
			"tool_command":         event.Command,
			"tool_cwd":             event.CWD,
			"tool_summary":         event.Summary,
			"tool_text":            event.Text,
			"tool_channel":         event.Channel,
			"tool_after_sec":       event.AfterSec,
			"tool_exit_code":       event.ExitCode,
			"tool_duration_sec":    event.DurationSec,
			"tool_timeout_sec":     event.TimeoutSec,
			"tool_timed_out":       event.TimedOut,
			"tool_arguments":       event.Arguments,
		},
	}
}

func renderTranscriptBlocks(messages []ChatMessage, width int, collapseToolLogs bool) []string {
	blocks := make([]string, 0, len(messages))
	for index := 0; index < len(messages); {
		message := messages[index]
		if shouldHideChatMessage(message) {
			index++
			continue
		}
		if collapseToolLogs {
			if group, next, ok := buildToolLogGroup(messages, index); ok {
				blocks = append(blocks, renderToolLogGroup(group, width))
				index = next
				continue
			}
			if block, ok := renderCollapsedStandaloneMessage(message, width); ok {
				blocks = append(blocks, block)
				index++
				continue
			}
		}
		blocks = append(blocks, renderChatMessage(message, width))
		index++
	}
	return blocks
}

func shouldHideChatMessage(message ChatMessage) bool {
	if message.Role != "assistant" || strings.TrimSpace(message.Content) != "" {
		return false
	}
	_, hasToolCalls := message.Meta["tool_calls"]
	return hasToolCalls
}

func buildToolLogGroup(messages []ChatMessage, start int) (toolLogGroup, int, bool) {
	callEvent, ok := messageToolEvent(messages[start])
	if !ok || callEvent.Phase != "call" {
		return toolLogGroup{}, start, false
	}
	group := toolLogGroup{
		call:    callEvent,
		hasCall: true,
		events:  []ToolEvent{callEvent},
	}
	index := start + 1
	for index < len(messages) {
		if shouldHideChatMessage(messages[index]) {
			index++
			continue
		}
		event, ok := messageToolEvent(messages[index])
		if ok {
			if event.Phase == "call" {
				break
			}
			group.events = append(group.events, event)
			index++
			continue
		}
		if messages[index].Role == "tool" {
			result := messages[index]
			group.result = &result
			index++
		}
		break
	}
	return group, index, true
}

func renderCollapsedStandaloneMessage(message ChatMessage, width int) (string, bool) {
	if event, ok := messageToolEvent(message); ok {
		if event.Phase == "call" {
			return "", false
		}
		group := toolLogGroup{
			call:   event,
			events: []ToolEvent{event},
		}
		return renderToolLogGroup(group, width), true
	}
	if message.Role != "tool" && metaString(message.Meta, "source_tool") == "" {
		return "", false
	}
	header, lines := summarizeStandaloneToolMessage(message)
	style := toolBlockStyle
	if message.Role == "event" {
		style = eventBlockStyle
	}
	return renderCollapsedLogBlock(header, lines, width, style), true
}

func renderToolLogGroup(group toolLogGroup, width int) string {
	header, lines := summarizeToolLogGroup(group)
	return renderCollapsedLogBlock(header, lines, width, eventBlockStyle)
}

func renderCollapsedLogBlock(header string, lines []string, width int, blockStyle lipgloss.Style) string {
	innerWidth := contentWidthForStyle(width, blockStyle)
	preview := foldedPreviewLines(lines)
	rendered := []string{renderHighlightedLogHeader(header, innerWidth)}
	if len(preview) > 0 {
		rendered = append(rendered, renderHighlightedLogLine("└ ", preview[0], innerWidth, logLineStyle))
		for _, line := range preview[1:] {
			style := logLineStyle
			if strings.HasPrefix(line, "… +") {
				style = logOmittedStyle
			}
			rendered = append(rendered, renderHighlightedLogLine("  ", line, innerWidth, style))
		}
	}
	return blockStyle.Width(innerWidth).Render(strings.Join(rendered, "\n"))
}

func summarizeToolLogGroup(group toolLogGroup) (string, []string) {
	toolName := group.call.Tool
	if toolName == "" && group.result != nil {
		toolName = toolNameForMessage(*group.result)
	}
	if toolName == "run_command" {
		return summarizeRunCommandGroup(group)
	}

	header := summarizeToolCallHeader(toolName, group.call.Arguments)
	lines := []string{}
	if group.result != nil {
		resultHeader, resultLines := summarizeToolPayload(toolName, group.result.Content, nil)
		if header == "" {
			header = resultHeader
		}
		lines = append(lines, resultLines...)
	}
	if header == "" && toolName != "" {
		header = "• " + strings.ReplaceAll(toolName, "_", " ")
	}
	if header == "" {
		header = "• Tool output"
	}
	if len(lines) == 0 {
		lines = append(lines, "(no output)")
	}
	return header, lines
}

func summarizeStandaloneToolMessage(message ChatMessage) (string, []string) {
	toolName := toolNameForMessage(message)
	header, lines := summarizeToolPayload(toolName, message.Content, nil)
	if header == "" {
		header = summarizeToolCallHeader(toolName, nil)
	}
	if header == "" {
		header = "• Tool output"
	}
	if len(lines) == 0 {
		lines = append(lines, "(no output)")
	}
	return header, lines
}

func summarizeToolPayload(toolName string, content string, args map[string]any) (string, []string) {
	intro, payload := stripToolIntro(toolName, content)
	if toolName == "run_command" {
		summary := parseRunCommandSummary(payload)
		header := summarizeToolCallHeader(toolName, args)
		if header == "" && summary.Command != "" {
			header = summarizeToolCallHeader(toolName, map[string]any{"command": summary.Command})
		}
		lines := runCommandBodyLines(summary)
		if intro != "" {
			lines = append([]string{intro}, lines...)
		}
		return header, lines
	}

	header := ""
	if args != nil {
		header = summarizeToolCallHeader(toolName, args)
	}
	if header == "" {
		header = summarizeToolResultHeader(toolName, payload)
	}
	if header == "" {
		header = summarizeToolCallHeader(toolName, nil)
	}
	lines := summarizeToolResultLines(toolName, payload)
	if intro != "" {
		lines = append([]string{intro}, lines...)
	}
	return header, lines
}

func summarizeRunCommandGroup(group toolLogGroup) (string, []string) {
	header := summarizeToolCallHeader("run_command", group.call.Arguments)
	if header == "" && group.call.Command != "" {
		header = summarizeToolCallHeader("run_command", map[string]any{"command": group.call.Command})
	}

	var (
		cwd          string
		heartbeat    string
		timeoutLine  string
		finishLine   string
		outputLines  []string
		truncatedOut bool
	)

	for _, event := range group.events {
		switch event.Phase {
		case "start":
			if cwd == "" {
				cwd = event.CWD
			}
			if header == "" && event.Command != "" {
				header = summarizeToolCallHeader("run_command", map[string]any{"command": event.Command})
			}
		case "output":
			if line := formatToolOutputLine(event.Channel, event.Text); line != "" {
				outputLines = append(outputLines, line)
			}
		case "output_truncated":
			truncatedOut = true
		case "heartbeat":
			heartbeat = fmt.Sprintf("running %ds | %s", event.AfterSec, event.Summary)
		case "timeout":
			timeoutLine = fmt.Sprintf("timeout after %ds", event.TimeoutSec)
		case "finish":
			finishLine = formatToolStatusLine(event)
		}
	}

	lines := []string{}
	if cwd != "" {
		lines = append(lines, "cwd: "+cwd)
	}
	lines = append(lines, outputLines...)
	if truncatedOut {
		lines = append(lines, "UI 已截断持续输出，后台仍保留尾部摘要")
	}
	if timeoutLine != "" {
		lines = append(lines, timeoutLine)
	}
	if finishLine != "" {
		lines = append(lines, finishLine)
	} else if heartbeat != "" {
		lines = append(lines, heartbeat)
	}

	if len(lines) == 0 && group.result != nil {
		resultHeader, resultLines := summarizeToolPayload("run_command", group.result.Content, nil)
		if header == "" {
			header = resultHeader
		}
		lines = append(lines, resultLines...)
	}
	if header == "" {
		header = "• Ran command"
	}
	if len(lines) == 0 {
		lines = append(lines, "(no output)")
	}
	return header, lines
}

func summarizeToolCallHeader(toolName string, args map[string]any) string {
	switch toolName {
	case "run_command":
		command := stringFromAny(args["command"])
		if command == "" {
			return ""
		}
		return "• Ran " + command
	case "read_file":
		path := stringFromAny(args["path"])
		startLine := intFromAny(args["start_line"])
		endLine := intFromAny(args["end_line"])
		switch {
		case path == "":
			return "• Read file"
		case startLine > 0 && endLine >= startLine:
			return fmt.Sprintf("• Read %s (lines %d-%d)", path, startLine, endLine)
		case startLine > 0:
			return fmt.Sprintf("• Read %s (from line %d)", path, startLine)
		default:
			return "• Read " + path
		}
	case "list_directory":
		path := stringFromAny(args["path"])
		if path == "" {
			path = "."
		}
		if boolFromAny(args["recursive"]) {
			return "• Listed " + path + " recursively"
		}
		return "• Listed " + path
	case "search_text":
		pattern := stringFromAny(args["pattern"])
		path := stringFromAny(args["path"])
		switch {
		case pattern != "" && path != "":
			return fmt.Sprintf("• Searched %q in %s", pattern, path)
		case pattern != "":
			return fmt.Sprintf("• Searched %q", pattern)
		default:
			return "• Search results"
		}
	case "write_file":
		path := stringFromAny(args["path"])
		if path == "" {
			return "• Wrote file"
		}
		return "• Wrote " + path
	case "insert_text":
		path := stringFromAny(args["path"])
		if path == "" {
			return "• Inserted text"
		}
		return "• Inserted text into " + path
	case "replace_in_file":
		path := stringFromAny(args["path"])
		if path == "" {
			return "• Replaced text"
		}
		return "• Replaced text in " + path
	default:
		if toolName == "" {
			return ""
		}
		return "• " + strings.ReplaceAll(toolName, "_", " ")
	}
}

func summarizeToolResultHeader(toolName string, content string) string {
	lines := splitContentLines(content)
	if len(lines) == 0 {
		return summarizeToolCallHeader(toolName, nil)
	}
	first := lines[0]
	switch {
	case toolName == "read_file" && strings.HasPrefix(first, "File "):
		return "• Read " + strings.TrimSuffix(strings.TrimPrefix(first, "File "), ":")
	case toolName == "list_directory" && strings.HasPrefix(first, "Listing for "):
		return "• Listed " + strings.TrimSuffix(strings.TrimPrefix(first, "Listing for "), ":")
	case toolName == "search_text" && strings.HasPrefix(first, "Search hits:"):
		return "• Search results"
	case toolName == "run_command" && strings.HasPrefix(first, "command="):
		return "• Ran " + strings.TrimPrefix(first, "command=")
	default:
		return summarizeToolCallHeader(toolName, nil)
	}
}

func summarizeToolResultLines(toolName string, content string) []string {
	lines := splitContentLines(content)
	if len(lines) == 0 {
		return nil
	}
	switch toolName {
	case "read_file", "list_directory", "search_text":
		if len(lines) > 1 {
			return lines[1:]
		}
	case "write_file", "insert_text", "replace_in_file":
		return lines
	}
	return lines
}

func stripToolIntro(toolName string, content string) (string, string) {
	payload := strings.TrimRight(content, "\n")
	markers := toolPayloadMarkers(toolName)
	if len(markers) == 0 {
		return "", payload
	}
	for _, marker := range markers {
		if strings.HasPrefix(payload, marker) {
			return "", payload
		}
		if index := strings.Index(payload, "\n"+marker); index >= 0 {
			intro := strings.TrimSpace(payload[:index])
			return intro, payload[index+1:]
		}
	}
	return "", payload
}

func toolPayloadMarkers(toolName string) []string {
	switch toolName {
	case "run_command":
		return []string{"command="}
	case "read_file":
		return []string{"File "}
	case "list_directory":
		return []string{"Listing for "}
	case "search_text":
		return []string{"Search hits:"}
	case "write_file":
		return []string{"wrote ", "appended to "}
	case "insert_text":
		return []string{"inserted text into "}
	case "replace_in_file":
		return []string{"replaced "}
	default:
		return nil
	}
}

func parseRunCommandSummary(content string) runCommandSummary {
	lines := splitContentLines(content)
	summary := runCommandSummary{}
	section := ""
	for _, line := range lines {
		switch {
		case line == "stdout_tail:":
			section = "stdout"
		case line == "stderr_tail:":
			section = "stderr"
		case strings.HasPrefix(line, "command="):
			summary.Command = strings.TrimPrefix(line, "command=")
			section = ""
		case strings.HasPrefix(line, "cwd="):
			summary.CWD = strings.TrimPrefix(line, "cwd=")
			section = ""
		case strings.HasPrefix(line, "exit_code="):
			summary.ExitCode = strings.TrimPrefix(line, "exit_code=")
			section = ""
		case strings.HasPrefix(line, "duration_sec="):
			summary.Duration = strings.TrimPrefix(line, "duration_sec=")
			section = ""
		case strings.HasPrefix(line, "timed_out="):
			summary.TimedOut = strings.TrimPrefix(line, "timed_out=")
			section = ""
		case strings.HasPrefix(line, "resources="):
			summary.Resources = strings.TrimPrefix(line, "resources=")
			section = ""
		default:
			switch section {
			case "stdout":
				summary.StdoutTail = append(summary.StdoutTail, line)
			case "stderr":
				summary.StderrTail = append(summary.StderrTail, line)
			}
		}
	}
	return summary
}

func runCommandBodyLines(summary runCommandSummary) []string {
	lines := []string{}
	if summary.CWD != "" {
		lines = append(lines, "cwd: "+summary.CWD)
	}
	for _, line := range summary.StdoutTail {
		if trimmed := strings.TrimSpace(line); trimmed != "" && trimmed != "(empty)" {
			lines = append(lines, line)
		}
	}
	for _, line := range summary.StderrTail {
		if trimmed := strings.TrimSpace(line); trimmed != "" && trimmed != "(empty)" {
			lines = append(lines, formatToolOutputLine("stderr", line))
		}
	}
	status := []string{}
	if summary.ExitCode != "" {
		status = append(status, "exit="+summary.ExitCode)
	}
	if summary.Duration != "" {
		status = append(status, "duration="+summary.Duration+"s")
	}
	if summary.TimedOut != "" && summary.TimedOut != "false" && summary.TimedOut != "False" {
		status = append(status, "timed_out="+summary.TimedOut)
	}
	if summary.Resources != "" {
		status = append(status, summary.Resources)
	}
	if len(status) > 0 {
		lines = append(lines, strings.Join(status, " | "))
	}
	return lines
}

func formatToolOutputLine(channel string, text string) string {
	if strings.TrimSpace(text) == "" {
		return ""
	}
	if channel == "stderr" {
		return "stderr | " + text
	}
	return text
}

func formatToolStatusLine(event ToolEvent) string {
	parts := []string{fmt.Sprintf("exit=%d", event.ExitCode)}
	if event.DurationSec > 0 {
		parts = append(parts, fmt.Sprintf("duration=%.2fs", event.DurationSec))
	}
	if event.TimedOut {
		parts = append(parts, "timed_out=true")
	}
	if event.Summary != "" {
		parts = append(parts, event.Summary)
	}
	return strings.Join(parts, " | ")
}

func foldedPreviewLines(lines []string) []string {
	trimmed := trimEmptyEdges(lines)
	if len(trimmed) <= foldedPreviewHeadLines+foldedPreviewTailLines {
		return trimmed
	}
	hidden := len(trimmed) - foldedPreviewHeadLines - foldedPreviewTailLines
	preview := append([]string{}, trimmed[:foldedPreviewHeadLines]...)
	preview = append(preview, fmt.Sprintf("… +%d lines", hidden))
	preview = append(preview, trimmed[len(trimmed)-foldedPreviewTailLines:]...)
	return preview
}

func trimEmptyEdges(lines []string) []string {
	start := 0
	end := len(lines)
	for start < end && strings.TrimSpace(lines[start]) == "" {
		start++
	}
	for end > start && strings.TrimSpace(lines[end-1]) == "" {
		end--
	}
	return lines[start:end]
}

func splitContentLines(content string) []string {
	content = strings.TrimRight(content, "\n")
	if strings.TrimSpace(content) == "" {
		return nil
	}
	return strings.Split(content, "\n")
}

func messageToolEvent(message ChatMessage) (ToolEvent, bool) {
	if message.Role != "event" || !metaBool(message.Meta, "synthetic_tool_event") {
		return ToolEvent{}, false
	}
	return ToolEvent{
		ID:          message.ID,
		Tool:        metaString(message.Meta, "tool_name"),
		Phase:       metaString(message.Meta, "tool_phase"),
		Command:     metaString(message.Meta, "tool_command"),
		CWD:         metaString(message.Meta, "tool_cwd"),
		Summary:     metaString(message.Meta, "tool_summary"),
		Text:        metaString(message.Meta, "tool_text"),
		Channel:     metaString(message.Meta, "tool_channel"),
		AfterSec:    metaInt(message.Meta, "tool_after_sec"),
		ExitCode:    metaInt(message.Meta, "tool_exit_code"),
		DurationSec: metaFloat(message.Meta, "tool_duration_sec"),
		TimeoutSec:  metaInt(message.Meta, "tool_timeout_sec"),
		TimedOut:    metaBool(message.Meta, "tool_timed_out"),
		Arguments:   metaMap(message.Meta, "tool_arguments"),
	}, true
}

func toolNameForMessage(message ChatMessage) string {
	if message.Name != "" {
		return message.Name
	}
	return metaString(message.Meta, "source_tool")
}

func metaString(meta map[string]any, key string) string {
	return stringFromAny(meta[key])
}

func metaInt(meta map[string]any, key string) int {
	return intFromAny(meta[key])
}

func metaFloat(meta map[string]any, key string) float64 {
	switch value := meta[key].(type) {
	case float64:
		return value
	case float32:
		return float64(value)
	case int:
		return float64(value)
	case int64:
		return float64(value)
	default:
		return 0
	}
}

func metaBool(meta map[string]any, key string) bool {
	return boolFromAny(meta[key])
}

func metaMap(meta map[string]any, key string) map[string]any {
	value, ok := meta[key]
	if !ok {
		return nil
	}
	switch typed := value.(type) {
	case map[string]any:
		return typed
	default:
		return nil
	}
}

func stringFromAny(value any) string {
	switch typed := value.(type) {
	case string:
		return typed
	default:
		return ""
	}
}

func intFromAny(value any) int {
	switch typed := value.(type) {
	case int:
		return typed
	case int32:
		return int(typed)
	case int64:
		return int(typed)
	case float64:
		return int(typed)
	case float32:
		return int(typed)
	default:
		return 0
	}
}

func boolFromAny(value any) bool {
	switch typed := value.(type) {
	case bool:
		return typed
	default:
		return false
	}
}

func (m Model) copyActiveSessionToClipboard() error {
	if m.activeSession == nil {
		return fmt.Errorf("当前没有活动会话可复制")
	}
	transcript := buildTranscriptText(m.activeSession)
	if strings.TrimSpace(transcript) == "" {
		return fmt.Errorf("当前会话没有可复制内容")
	}
	if err := writeClipboard(transcript); err != nil {
		return fmt.Errorf("写入系统剪贴板失败: %w", err)
	}
	return nil
}

func (m Model) pasteIntoInput() (tea.Model, tea.Cmd) {
	text, err := readClipboard()
	if err != nil {
		m.notice = ""
		m.lastErr = fmt.Sprintf("读取系统剪贴板失败: %v", err)
		return m, nil
	}
	if text == "" {
		return m, nil
	}
	text = normalizeClipboardText(text)
	m.input.InsertString(text)
	m.notice = "已从系统剪贴板粘贴"
	m.lastErr = ""
	m.markLikelyPaste()
	return m, nil
}

func normalizeClipboardText(text string) string {
	text = strings.ReplaceAll(text, "\r\n", "\n")
	text = strings.ReplaceAll(text, "\r", "\n")
	return text
}

func (m *Model) trackTextEntry(msg tea.KeyMsg) {
	if msg.Type != tea.KeyRunes || len(msg.Runes) == 0 {
		m.clearLikelyPasteIfExpired()
		return
	}
	now := timeNow()
	likelyPaste := msg.Paste || len(msg.Runes) > 1
	if !m.lastTextInputAt.IsZero() && now.Sub(m.lastTextInputAt) <= pasteBurstWindow {
		likelyPaste = true
	}
	m.lastTextInputAt = now
	m.likelyPasteBurst = likelyPaste
}

func (m *Model) markLikelyPaste() {
	m.lastTextInputAt = timeNow()
	m.likelyPasteBurst = true
}

func (m *Model) clearLikelyPasteIfExpired() {
	if m.lastTextInputAt.IsZero() {
		m.likelyPasteBurst = false
		return
	}
	if timeNow().Sub(m.lastTextInputAt) > pasteBurstWindow {
		m.likelyPasteBurst = false
	}
}

func (m *Model) shouldTreatEnterAsPastedNewline() bool {
	if !m.likelyPasteBurst || m.lastTextInputAt.IsZero() {
		return false
	}
	return timeNow().Sub(m.lastTextInputAt) <= pasteBurstWindow
}

func buildTranscriptText(session *SessionRecord) string {
	if session == nil || len(session.Messages) == 0 {
		return ""
	}
	blocks := make([]string, 0, len(session.Messages))
	for _, message := range session.Messages {
		body := strings.TrimRight(message.Content, "\n")
		if body == "" {
			body = "(empty)"
		}
		blocks = append(blocks, chatMessageLabel(message)+"\n"+body)
	}
	return strings.Join(blocks, "\n\n")
}

func chatMessageLabel(message ChatMessage) string {
	label := strings.ToUpper(message.Role)
	if message.Role == "tool" && message.Name != "" {
		label = "TOOL/" + strings.ToUpper(message.Name)
	}
	if message.Role == "event" {
		label = "EVENT"
	}
	return label
}

func renderHighlightedLogHeader(header string, width int) string {
	if strings.HasPrefix(header, "• Ran ") {
		return logHeaderStyle.Width(width).Render(
			commandMetaTokenStyle.Render("• Ran ") +
				highlightShellCommand(strings.TrimPrefix(header, "• Ran ")),
		)
	}
	return logHeaderStyle.Width(width).Render(header)
}

func renderHighlightedLogLine(prefix string, line string, width int, style lipgloss.Style) string {
	return style.Width(width).Render(prefix + renderStructuredLineContent(line, true))
}

func renderStructuredLineContent(line string, allowStandaloneDiff bool) string {
	switch {
	case strings.HasPrefix(line, "stderr | "):
		return stderrTokenStyle.Render("stderr |") + " " + strings.TrimPrefix(line, "stderr | ")
	case strings.HasPrefix(line, "cwd: "):
		return commandMetaTokenStyle.Render("cwd: ") + commandPathTokenStyle.Render(strings.TrimPrefix(line, "cwd: "))
	case strings.HasPrefix(line, "cwd="):
		return commandMetaTokenStyle.Render("cwd=") + commandPathTokenStyle.Render(strings.TrimPrefix(line, "cwd="))
	case isCommandLine(strings.TrimSpace(line)):
		return highlightCommandText(line)
	case looksLikeNumberedCodeLine(line):
		content, _ := highlightCodeLineContent(line)
		return content
	case allowStandaloneDiff && looksLikeStandaloneDiffLine(strings.TrimSpace(line)):
		content, _ := highlightCodeLineContent(line)
		return content
	default:
		return line
	}
}

func styleMessageBody(content string, width int) string {
	lines := strings.Split(content, "\n")
	if len(lines) == 0 {
		return ""
	}
	rendered := make([]string, 0, len(lines))
	inCode := false
	for _, line := range lines {
		trimmed := strings.TrimSpace(line)
		if strings.HasPrefix(trimmed, "```") {
			inCode = !inCode
			continue
		}
		rendered = append(rendered, renderMessageBodyLine(line, width, inCode))
	}
	return strings.Join(rendered, "\n")
}

func renderMessageBodyLine(line string, width int, inCode bool) string {
	trimmed := strings.TrimSpace(line)
	switch {
	case strings.HasPrefix(trimmed, "└"):
		return subtleStyle.Width(width).Render(line)
	case inCode || looksLikeNumberedCodeLine(line):
		return renderCodeMessageLine(line, width)
	case isCommandLine(trimmed):
		return renderCommandMessageLine(line, width)
	default:
		return lipgloss.NewStyle().Width(width).Render(renderStructuredLineContent(line, false))
	}
}

func renderCodeMessageLine(line string, width int) string {
	content, diff := highlightCodeLineContent(line)
	style := codeLineStyle
	switch diff {
	case diffAdd:
		style = codeAddLineStyle
	case diffDelete:
		style = codeDeleteLineStyle
	}
	return style.Width(width).Render(content)
}

func renderCommandMessageLine(line string, width int) string {
	return commandLineStyle.Width(width).Render(highlightCommandText(line))
}

func highlightCommandText(line string) string {
	switch {
	case strings.HasPrefix(line, "$ "):
		return commandPromptTokenStyle.Render("$ ") + highlightShellCommand(strings.TrimPrefix(line, "$ "))
	case strings.HasPrefix(line, "PS> "):
		return commandPromptTokenStyle.Render("PS> ") + highlightShellCommand(strings.TrimPrefix(line, "PS> "))
	case strings.HasPrefix(line, "PS>"):
		return commandPromptTokenStyle.Render("PS>") + highlightShellCommand(strings.TrimPrefix(line, "PS>"))
	case strings.HasPrefix(line, "command="):
		return commandMetaTokenStyle.Render("command=") + highlightShellCommand(strings.TrimPrefix(line, "command="))
	default:
		return highlightShellCommand(line)
	}
}

func highlightShellCommand(command string) string {
	tokens := splitCommandTokens(command)
	var builder strings.Builder
	firstWord := true
	for _, token := range tokens {
		switch {
		case strings.TrimSpace(token) == "":
			builder.WriteString(token)
		case len(token) >= 2 && ((token[0] == '"' && token[len(token)-1] == '"') || (token[0] == '\'' && token[len(token)-1] == '\'') || (token[0] == '`' && token[len(token)-1] == '`')):
			builder.WriteString(commandStringTokenStyle.Render(token))
			firstWord = false
		case isCommandOperator(token):
			builder.WriteString(commandOperatorTokenStyle.Render(token))
		case firstWord && strings.Contains(token, "=") && !strings.HasPrefix(token, ".") && !looksLikePathToken(token):
			builder.WriteString(commandMetaTokenStyle.Render(token))
		case firstWord:
			builder.WriteString(commandExecTokenStyle.Render(token))
			firstWord = false
		case isCommandFlag(token):
			builder.WriteString(commandFlagTokenStyle.Render(token))
		case looksLikeEnvToken(token):
			builder.WriteString(commandMetaTokenStyle.Render(token))
		case looksLikePathToken(token):
			builder.WriteString(commandPathTokenStyle.Render(token))
		default:
			builder.WriteString(token)
		}
	}
	return builder.String()
}

func splitCommandTokens(command string) []string {
	tokens := make([]string, 0, len(command)/2)
	for index := 0; index < len(command); {
		switch {
		case isWhitespaceByte(command[index]):
			start := index
			for index < len(command) && isWhitespaceByte(command[index]) {
				index++
			}
			tokens = append(tokens, command[start:index])
		case strings.HasPrefix(command[index:], "&&"),
			strings.HasPrefix(command[index:], "||"),
			strings.HasPrefix(command[index:], ">>"):
			tokens = append(tokens, command[index:index+2])
			index += 2
		case strings.ContainsRune("|;&<>", rune(command[index])):
			tokens = append(tokens, command[index:index+1])
			index++
		case command[index] == '"' || command[index] == '\'' || command[index] == '`':
			end := scanQuotedSegment(command, index, command[index])
			tokens = append(tokens, command[index:end])
			index = end
		default:
			start := index
			for index < len(command) &&
				!isWhitespaceByte(command[index]) &&
				!strings.ContainsRune("|;&<>", rune(command[index])) &&
				command[index] != '"' &&
				command[index] != '\'' &&
				command[index] != '`' {
				index++
			}
			tokens = append(tokens, command[start:index])
		}
	}
	return tokens
}

func isCommandOperator(token string) bool {
	switch token {
	case "|", "||", "&&", ";", ">", ">>", "<":
		return true
	default:
		return false
	}
}

func isCommandFlag(token string) bool {
	if len(token) < 2 {
		return false
	}
	if token[0] == '-' {
		return true
	}
	return token[0] == '/' && !looksLikePathToken(token)
}

func looksLikeEnvToken(token string) bool {
	if strings.HasPrefix(token, "$") {
		return true
	}
	return strings.HasPrefix(token, "%") && strings.HasSuffix(token, "%")
}

func looksLikePathToken(token string) bool {
	switch {
	case strings.Contains(token, `\`), strings.Contains(token, "/"):
		return true
	case strings.HasPrefix(token, "."), strings.HasPrefix(token, "~"):
		return true
	case len(token) >= 3 && unicode.IsLetter(rune(token[0])) && token[1] == ':' && (token[2] == '\\' || token[2] == '/'):
		return true
	default:
		return false
	}
}

func highlightCodeLineContent(line string) (string, diffKind) {
	prefix, content := splitLineNumberPrefix(line)
	leading, marker, rest, diff := splitDiffPayload(content)

	var builder strings.Builder
	if prefix != "" {
		builder.WriteString(codeLineNumberStyle.Render(prefix))
	}
	if leading != "" {
		builder.WriteString(leading)
	}
	switch diff {
	case diffAdd:
		builder.WriteString(diffAddMarkerStyle.Render(marker))
	case diffDelete:
		builder.WriteString(diffDeleteMarkerStyle.Render(marker))
	}
	builder.WriteString(highlightCodeTokens(rest))
	return builder.String(), diff
}

func splitLineNumberPrefix(line string) (string, string) {
	index := 0
	for index < len(line) && isWhitespaceByte(line[index]) {
		index++
	}
	digitStart := index
	for index < len(line) && unicode.IsDigit(rune(line[index])) {
		index++
	}
	if index == digitStart || index >= len(line) || line[index] != ':' {
		return "", line
	}
	index++
	for index < len(line) && line[index] == ' ' {
		index++
	}
	return line[:index], line[index:]
}

func splitDiffPayload(text string) (string, string, string, diffKind) {
	index := 0
	for index < len(text) && isWhitespaceByte(text[index]) {
		index++
	}
	if index >= len(text) {
		return "", "", text, diffNone
	}
	switch text[index] {
	case '+':
		if strings.HasPrefix(text[index:], "+++") {
			return "", "", text, diffNone
		}
		return text[:index], "+", text[index+1:], diffAdd
	case '-':
		if strings.HasPrefix(text[index:], "---") {
			return "", "", text, diffNone
		}
		return text[:index], "-", text[index+1:], diffDelete
	default:
		return "", "", text, diffNone
	}
}

func highlightCodeTokens(text string) string {
	var builder strings.Builder
	for index := 0; index < len(text); {
		switch {
		case strings.HasPrefix(text[index:], "//"):
			builder.WriteString(codeCommentTokenStyle.Render(text[index:]))
			return builder.String()
		case text[index] == '#' && (index == 0 || isWhitespaceByte(text[index-1])):
			builder.WriteString(codeCommentTokenStyle.Render(text[index:]))
			return builder.String()
		case strings.HasPrefix(text[index:], "-- ") && (index == 0 || isWhitespaceByte(text[index-1])):
			builder.WriteString(codeCommentTokenStyle.Render(text[index:]))
			return builder.String()
		case text[index] == '"' || text[index] == '\'' || text[index] == '`':
			end := scanQuotedSegment(text, index, text[index])
			builder.WriteString(codeStringTokenStyle.Render(text[index:end]))
			index = end
		case isCodeNumberStart(text, index):
			end := scanCodeNumber(text, index)
			builder.WriteString(codeNumberTokenStyle.Render(text[index:end]))
			index = end
		case isCodeWordStart(text[index]):
			end := scanCodeWord(text, index)
			word := text[index:end]
			if _, ok := codeKeywords[strings.ToLower(word)]; ok {
				builder.WriteString(codeKeywordTokenStyle.Render(word))
			} else {
				builder.WriteString(word)
			}
			index = end
		default:
			builder.WriteByte(text[index])
			index++
		}
	}
	return builder.String()
}

func scanQuotedSegment(text string, start int, quote byte) int {
	index := start + 1
	for index < len(text) {
		if quote != '`' && text[index] == '\\' && index+1 < len(text) {
			index += 2
			continue
		}
		if text[index] == quote {
			return index + 1
		}
		index++
	}
	return len(text)
}

func isCodeNumberStart(text string, index int) bool {
	if index >= len(text) || !unicode.IsDigit(rune(text[index])) {
		return false
	}
	return index == 0 || !isCodeWordByte(text[index-1])
}

func scanCodeNumber(text string, start int) int {
	index := start
	for index < len(text) {
		switch {
		case unicode.IsDigit(rune(text[index])):
			index++
		case text[index] == '.', text[index] == '_', text[index] == 'x', text[index] == 'X', text[index] == 'b', text[index] == 'B', text[index] == 'o', text[index] == 'O':
			index++
		case text[index] >= 'a' && text[index] <= 'f':
			index++
		case text[index] >= 'A' && text[index] <= 'F':
			index++
		default:
			return index
		}
	}
	return index
}

func isCodeWordStart(char byte) bool {
	return char == '_' || unicode.IsLetter(rune(char))
}

func isCodeWordByte(char byte) bool {
	return isCodeWordStart(char) || unicode.IsDigit(rune(char))
}

func scanCodeWord(text string, start int) int {
	index := start
	for index < len(text) && isCodeWordByte(text[index]) {
		index++
	}
	return index
}

func isCommandLine(trimmed string) bool {
	return strings.HasPrefix(trimmed, "$ ") ||
		strings.HasPrefix(trimmed, "PS>") ||
		strings.HasPrefix(trimmed, "command=")
}

func looksLikeNumberedCodeLine(line string) bool {
	prefix, _ := splitLineNumberPrefix(line)
	return prefix != ""
}

func looksLikeStandaloneDiffLine(trimmed string) bool {
	return strings.HasPrefix(trimmed, "diff --git") ||
		strings.HasPrefix(trimmed, "@@") ||
		strings.HasPrefix(trimmed, "+++ ") ||
		strings.HasPrefix(trimmed, "--- ") ||
		(strings.HasPrefix(trimmed, "+") && !strings.HasPrefix(trimmed, "+++")) ||
		(strings.HasPrefix(trimmed, "-") && !strings.HasPrefix(trimmed, "---"))
}

func isWhitespaceByte(char byte) bool {
	return char == ' ' || char == '\t'
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

func contentWidthForStyle(outerWidth int, style lipgloss.Style) int {
	return maxInt(1, outerWidth-style.GetHorizontalFrameSize())
}

func truncateToWidth(text string, width int) string {
	if width <= 0 {
		return ""
	}
	return ansi.Cut(text, 0, width)
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
