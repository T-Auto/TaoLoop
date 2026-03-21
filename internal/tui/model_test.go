package tui

import (
	"bytes"
	"encoding/json"
	"errors"
	"strings"
	"testing"
	"time"

	"github.com/charmbracelet/bubbles/list"
	"github.com/charmbracelet/bubbles/textarea"
	"github.com/charmbracelet/bubbles/viewport"
	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"
	"github.com/charmbracelet/x/ansi"
)

func TestToolEventStaysBeforeQueuedReply(t *testing.T) {
	m := Model{
		viewport: viewport.New(80, 20),
		activeSession: &SessionRecord{
			ID: "session_test",
			Messages: []ChatMessage{
				{ID: "assistant_running", Role: "assistant", Content: "正在运行"},
			},
		},
	}

	queuedUser := ChatMessage{ID: "user_stop", Role: "user", Content: "你可以停下来吗"}
	m.applyEvent(Event{Type: "message", Message: &queuedUser})

	delayedToolEvent := ToolEvent{
		ID:             "tool_event_finish",
		AfterMessageID: "assistant_running",
		Tool:           "run_command",
		Phase:          "finish",
		Summary:        "命令结束",
	}
	m.applyEvent(Event{Type: "tool_event", Tool: &delayedToolEvent})

	reply := ChatMessage{ID: "assistant_reply", Role: "assistant", Content: "可以，已经结束了"}
	m.applyEvent(Event{Type: "message", Message: &reply, AfterMessageID: "user_stop"})

	assertMessageOrder(t, m.activeSession.Messages, []string{
		"assistant_running",
		"tool_event_finish",
		"user_stop",
		"assistant_reply",
	})
}

func TestToolMessageCanFollowSyntheticToolEvent(t *testing.T) {
	m := Model{
		viewport: viewport.New(80, 20),
		activeSession: &SessionRecord{
			ID: "session_test",
			Messages: []ChatMessage{
				{ID: "assistant_read", Role: "assistant", Content: "我来读取文件"},
			},
		},
	}

	callEvent := ToolEvent{
		ID:             "tool_event_call",
		AfterMessageID: "assistant_read",
		Tool:           "read_file",
		Phase:          "call",
	}
	m.applyEvent(Event{Type: "tool_event", Tool: &callEvent})

	toolMessage := ChatMessage{ID: "tool_read_result", Role: "tool", Name: "read_file", Content: "File ..."}
	m.applyEvent(Event{Type: "message", Message: &toolMessage, AfterMessageID: "tool_event_call"})

	assertMessageOrder(t, m.activeSession.Messages, []string{
		"assistant_read",
		"tool_event_call",
		"tool_read_result",
	})
}

func TestSessionPickerViewShowsShortcutHints(t *testing.T) {
	m := Model{
		mode:   modeSessionPicker,
		width:  100,
		height: 30,
		list:   newSessionPickerListForTest(),
	}

	view := ansi.Strip(m.View())
	for _, want := range []string{"←/→ 翻页", "Delete 删除会话"} {
		if !contains(view, want) {
			t.Fatalf("session picker view missing hint %q: %s", want, view)
		}
	}
}

func TestDeleteOpensConfirmationDialog(t *testing.T) {
	m := Model{
		mode:   modeSessionPicker,
		width:  100,
		height: 30,
		list:   newSessionPickerListForTest(),
		sessions: []SessionSummary{
			{ID: "session_1", Title: "待删除会话"},
		},
	}
	m.refreshSessionList()
	m.list.Select(1)

	updatedModel, _ := m.updateSessionPicker(tea.KeyMsg{Type: tea.KeyDelete})
	updated := updatedModel.(Model)

	if updated.pendingDelete == nil {
		t.Fatalf("expected pending delete session to be set")
	}
	if updated.pendingDelete.ID != "session_1" {
		t.Fatalf("unexpected pending delete session: %+v", updated.pendingDelete)
	}

	view := ansi.Strip(updated.View())
	if !contains(view, "确认删除会话") {
		t.Fatalf("expected confirmation dialog in view: %s", view)
	}
}

func TestEnterConfirmsDeleteSessionRequest(t *testing.T) {
	var sink bytes.Buffer
	m := Model{
		mode:   modeSessionPicker,
		width:  100,
		height: 30,
		list:   newSessionPickerListForTest(),
		backend: &BackendClient{
			stdin: nopWriteCloser{Buffer: &sink},
		},
		pendingDelete: &SessionSummary{
			ID:    "session_1",
			Title: "待删除会话",
		},
	}

	updatedModel, _ := m.updateSessionPicker(tea.KeyMsg{Type: tea.KeyEnter})
	updated := updatedModel.(Model)

	if updated.pendingDelete != nil {
		t.Fatalf("expected pending delete session to be cleared after confirm")
	}

	var payload map[string]any
	if err := json.Unmarshal(sink.Bytes(), &payload); err != nil {
		t.Fatalf("decode payload failed: %v; raw=%q", err, sink.String())
	}
	if payload["type"] != "delete_session" {
		t.Fatalf("unexpected request type: %#v", payload)
	}
	if payload["session_id"] != "session_1" {
		t.Fatalf("unexpected session_id: %#v", payload)
	}
}

func TestEscCancelsDeleteConfirmation(t *testing.T) {
	m := Model{
		mode:   modeSessionPicker,
		width:  100,
		height: 30,
		list:   newSessionPickerListForTest(),
		pendingDelete: &SessionSummary{
			ID:    "session_1",
			Title: "待删除会话",
		},
	}

	updatedModel, _ := m.updateSessionPicker(tea.KeyMsg{Type: tea.KeyEsc})
	updated := updatedModel.(Model)

	if updated.pendingDelete != nil {
		t.Fatalf("expected pending delete session to be cleared on esc")
	}
}

func TestCopyTranscriptShortcutWritesClipboard(t *testing.T) {
	oldWriteClipboard := writeClipboard
	defer func() {
		writeClipboard = oldWriteClipboard
	}()

	var copied string
	writeClipboard = func(text string) error {
		copied = text
		return nil
	}

	m := Model{
		mode: modeChat,
		activeSession: &SessionRecord{
			ID: "session_copy",
			Messages: []ChatMessage{
				{ID: "user_1", Role: "user", Content: "你好"},
				{ID: "assistant_1", Role: "assistant", Content: "世界"},
				{ID: "tool_1", Role: "tool", Name: "read_file", Content: "result.txt"},
			},
		},
	}

	updatedModel, _ := m.updateChat(tea.KeyMsg{Type: tea.KeyCtrlY})
	updated := updatedModel.(Model)

	want := "USER\n你好\n\nASSISTANT\n世界\n\nTOOL/READ_FILE\nresult.txt"
	if copied != want {
		t.Fatalf("clipboard content mismatch:\nwant:\n%s\n\ngot:\n%s", want, copied)
	}
	if updated.notice != "已复制当前会话到系统剪贴板" {
		t.Fatalf("unexpected notice: %q", updated.notice)
	}
}

func TestCopyTranscriptShortcutReportsClipboardError(t *testing.T) {
	oldWriteClipboard := writeClipboard
	defer func() {
		writeClipboard = oldWriteClipboard
	}()

	writeClipboard = func(string) error {
		return errors.New("clipboard unavailable")
	}

	m := Model{
		mode: modeChat,
		activeSession: &SessionRecord{
			ID: "session_copy",
			Messages: []ChatMessage{
				{ID: "assistant_1", Role: "assistant", Content: "世界"},
			},
		},
	}

	updatedModel, _ := m.updateChat(tea.KeyMsg{Type: tea.KeyF5})
	updated := updatedModel.(Model)

	if updated.notice != "" {
		t.Fatalf("expected notice to stay empty on error, got %q", updated.notice)
	}
	if !strings.Contains(updated.lastErr, "写入系统剪贴板失败") {
		t.Fatalf("expected clipboard error, got %q", updated.lastErr)
	}
}

func TestRenderStatusShowsCopyHint(t *testing.T) {
	m := Model{
		collapseToolLogs: true,
		activeSession: &SessionRecord{
			ID:    "session_status",
			Title: "状态测试",
		},
		status: StatusPayload{
			Model: "deepseek",
			Context: ContextUsage{
				UsedTokens:  12,
				LimitTokens: 128,
			},
		},
	}

	status := m.renderStatus()
	for _, want := range []string{"状态测试", "Ctrl+S 多行发送", "Ctrl+Y/F5 复制", "Ctrl+O 日志", "logs 折叠"} {
		if !contains(status, want) {
			t.Fatalf("status missing hint %q: %s", want, status)
		}
	}
}

func TestCollapsedRunCommandLogGroupsStreamingOutput(t *testing.T) {
	m := Model{
		viewport:         viewport.New(80, 20),
		collapseToolLogs: true,
		activeSession: &SessionRecord{
			ID: "session_logs",
			Messages: []ChatMessage{
				makeSyntheticToolEventMessage(ToolEvent{
					ID:    "tool_call",
					Tool:  "run_command",
					Phase: "call",
					Arguments: map[string]any{
						"command": "go test ./...",
					},
				}, 0),
				makeSyntheticToolEventMessage(ToolEvent{
					ID:      "tool_start",
					Tool:    "run_command",
					Phase:   "start",
					Command: "go test ./...",
					CWD:     "D:\\Auto\\research\\Astronomy\\ZhouXing",
				}, 1),
				makeSyntheticToolEventMessage(ToolEvent{
					ID:      "tool_out_1",
					Tool:    "run_command",
					Phase:   "output",
					Channel: "stdout",
					Text:    "stdout one",
				}, 2),
				makeSyntheticToolEventMessage(ToolEvent{
					ID:      "tool_out_2",
					Tool:    "run_command",
					Phase:   "output",
					Channel: "stdout",
					Text:    "stdout two",
				}, 3),
				makeSyntheticToolEventMessage(ToolEvent{
					ID:      "tool_out_3",
					Tool:    "run_command",
					Phase:   "output",
					Channel: "stdout",
					Text:    "stdout three",
				}, 4),
				makeSyntheticToolEventMessage(ToolEvent{
					ID:      "tool_out_4",
					Tool:    "run_command",
					Phase:   "output",
					Channel: "stdout",
					Text:    "stdout four",
				}, 5),
				makeSyntheticToolEventMessage(ToolEvent{
					ID:          "tool_finish",
					Tool:        "run_command",
					Phase:       "finish",
					ExitCode:    0,
					DurationSec: 1.25,
					Summary:     "cpu 12%",
				}, 6),
				{
					ID:      "tool_result",
					Role:    "tool",
					Name:    "run_command",
					Content: "command=go test ./...\nstdout_tail:\nstdout one\nstderr_tail:\n(empty)",
				},
			},
		},
	}

	m.rebuildViewport(true)
	view := ansi.Strip(m.viewport.View())

	for _, want := range []string{"• Ran go test ./...", "stdout one", "stdout four", "exit=0 | duration=1.25s | cpu 12%", "… +2 lines"} {
		if !contains(view, want) {
			t.Fatalf("collapsed run command log missing %q: %s", want, view)
		}
	}
	for _, hidden := range []string{"stdout two", "stdout three"} {
		if contains(view, hidden) {
			t.Fatalf("expected collapsed run command log to hide %q: %s", hidden, view)
		}
	}
}

func TestCollapsedStandaloneReadFileToolMessage(t *testing.T) {
	m := Model{
		viewport:         viewport.New(80, 20),
		collapseToolLogs: true,
		activeSession: &SessionRecord{
			ID: "session_read",
			Messages: []ChatMessage{
				{
					ID:   "tool_read",
					Role: "tool",
					Name: "read_file",
					Content: strings.Join([]string{
						"File D:\\Auto\\research\\Astronomy\\ZhouXing\\internal\\tui\\model.go lines 1-6:",
						"   1: package tui",
						"   2: import (",
						"   3: \"fmt\"",
						"   4: \"strings\"",
						"   5: \"time\"",
						"   6: )",
					}, "\n"),
				},
			},
		},
	}

	m.rebuildViewport(true)
	view := ansi.Strip(m.viewport.View())

	for _, want := range []string{
		"• Read D:\\Auto\\research\\Astronomy\\ZhouXing\\internal\\tui\\model.go lines 1-6",
		"   1: package tui",
		"   2: import (",
		"   5: \"time\"",
		"   6: )",
		"… +2 lines",
	} {
		if !contains(view, want) {
			t.Fatalf("collapsed read_file log missing %q: %s", want, view)
		}
	}
	for _, hidden := range []string{"   3: \"fmt\"", "   4: \"strings\""} {
		if contains(view, hidden) {
			t.Fatalf("expected collapsed read_file log to hide %q: %s", hidden, view)
		}
	}
}

func TestCtrlOTogglesToolLogCollapse(t *testing.T) {
	m := Model{
		mode:             modeChat,
		viewport:         viewport.New(80, 20),
		collapseToolLogs: true,
	}

	updatedModel, _ := m.updateChat(tea.KeyMsg{Type: tea.KeyCtrlO})
	updated := updatedModel.(Model)

	if updated.collapseToolLogs {
		t.Fatalf("expected ctrl+o to expand tool logs")
	}
	if updated.notice != "工具日志已展开" {
		t.Fatalf("unexpected notice after ctrl+o: %q", updated.notice)
	}
}

func TestChatViewFitsWindowAfterResize(t *testing.T) {
	m := newChatModelForLayoutTest()

	for _, size := range []struct {
		width  int
		height int
	}{
		{width: 100, height: 30},
		{width: 72, height: 20},
		{width: 48, height: 14},
	} {
		m.width = size.width
		m.height = size.height
		m.updateLayout()

		view := ansi.Strip(m.View())
		if got := lipgloss.Height(view); got > size.height {
			t.Fatalf("view height overflow after resize %dx%d: got %d lines\n%s", size.width, size.height, got, view)
		}
		if got := lipgloss.Width(view); got > size.width {
			t.Fatalf("view width overflow after resize %dx%d: got %d cols\n%s", size.width, size.height, got, view)
		}
		for _, unwanted := range []string{"╭", "╰"} {
			if contains(view, unwanted) {
				t.Fatalf("chat view should not contain panel border %q after resize %dx%d: %s", unwanted, size.width, size.height, view)
			}
		}
	}
}

func TestChatViewShowsBottomInputOnly(t *testing.T) {
	m := newChatModelForLayoutTest()
	m.width = 80
	m.height = 20
	m.updateLayout()

	view := ansi.Strip(m.View())
	for _, want := range []string{"布局测试", "Ctrl+Y/F5 复制", "输入消息"} {
		if !contains(view, want) {
			t.Fatalf("chat view missing %q: %s", want, view)
		}
	}
	if !contains(view, "\n\n│ ") {
		t.Fatalf("chat view should keep a blank line before input: %q", view)
	}
	for _, unwanted := range []string{"请帮我检查日志折叠", "╭", "╰"} {
		if contains(view, unwanted) {
			t.Fatalf("chat view should not render transcript area or panel border %q: %s", unwanted, view)
		}
	}
}

func TestBuildPendingTranscriptPrintTextPrintsCollapsedTranscript(t *testing.T) {
	m := Model{
		collapseToolLogs: true,
		activeSession: &SessionRecord{
			ID:    "session_print",
			Title: "打印测试",
			Messages: []ChatMessage{
				{ID: "user_1", Role: "user", Content: "请读取配置"},
				{
					ID:   "tool_read",
					Role: "tool",
					Name: "read_file",
					Content: strings.Join([]string{
						"File D:\\Auto\\research\\Astronomy\\ZhouXing\\README.md lines 1-5:",
						"   1: # 周行",
						"   2: ",
						"   3: 说明",
						"   4: 更多说明",
						"   5: 结束",
					}, "\n"),
				},
				{ID: "assistant_1", Role: "assistant", Content: "已经读取完成。"},
			},
		},
	}

	printed := m.buildPendingTranscriptPrintText(true)

	for _, want := range []string{"> 请读取配置", "• Read D:\\Auto\\research\\Astronomy\\ZhouXing\\README.md lines 1-5", "… +1 lines", "已经读取完成。"} {
		if !contains(printed, want) {
			t.Fatalf("printed transcript missing %q: %s", want, printed)
		}
	}
}

func TestBuildPendingTranscriptPrintTextOnlyPrintsNewBlocks(t *testing.T) {
	m := Model{
		collapseToolLogs: true,
		activeSession: &SessionRecord{
			ID: "session_incremental",
			Messages: []ChatMessage{
				{ID: "assistant_1", Role: "assistant", Content: "第一条"},
			},
		},
	}

	first := m.buildPendingTranscriptPrintText(true)
	if !contains(first, "第一条") {
		t.Fatalf("expected first transcript print to contain initial message: %s", first)
	}

	second := m.buildPendingTranscriptPrintText(false)
	if second != "" {
		t.Fatalf("expected no duplicate transcript output, got: %s", second)
	}

	m.activeSession.Messages = append(m.activeSession.Messages, ChatMessage{ID: "assistant_2", Role: "assistant", Content: "第二条"})
	third := m.buildPendingTranscriptPrintText(false)
	if strings.TrimSpace(third) != "第二条" {
		t.Fatalf("expected only new message to be printed, got: %s", third)
	}
}

func TestWrapTranscriptPrintTextHardwrapsLongLines(t *testing.T) {
	text := "> abcdefghijklmnopqrstuvwxyz\n\n第二行"
	wrapped := wrapTranscriptPrintText(text, 10)

	if !contains(wrapped, "\n") {
		t.Fatalf("expected wrapped transcript to contain newlines: %q", wrapped)
	}
	for _, line := range strings.Split(wrapped, "\n") {
		if ansi.StringWidth(line) > 10 {
			t.Fatalf("wrapped line exceeds width: %q", line)
		}
	}
}

func TestFormatTranscriptPrintTextAddsTrailingBlankLine(t *testing.T) {
	formatted := formatTranscriptPrintText("> 第一条\n\n第二条", 20)
	if !strings.HasSuffix(formatted, "\n") {
		t.Fatalf("expected formatted transcript to end with a blank line: %q", formatted)
	}
	if !contains(formatted, "\n\n第二条") {
		t.Fatalf("expected formatted transcript to preserve block spacing: %q", formatted)
	}
}

func TestHighlightCommandTextPreservesCommandText(t *testing.T) {
	raw := highlightCommandText("$ git diff --stat .\\internal\\tui\\model.go")
	if got := ansi.Strip(raw); got != "$ git diff --stat .\\internal\\tui\\model.go" {
		t.Fatalf("unexpected stripped command output: %q", got)
	}
}

func TestHighlightCodeLineContentMarksDiffAddsAndDeletes(t *testing.T) {
	addedRaw, addedDiff := highlightCodeLineContent("   8: +return value")
	if addedDiff != diffAdd {
		t.Fatalf("expected diffAdd, got %v", addedDiff)
	}
	if got := ansi.Strip(addedRaw); got != "   8: +return value" {
		t.Fatalf("unexpected stripped added line: %q", got)
	}

	deletedRaw, deletedDiff := highlightCodeLineContent("   9: -return oldValue")
	if deletedDiff != diffDelete {
		t.Fatalf("expected diffDelete, got %v", deletedDiff)
	}
	if got := ansi.Strip(deletedRaw); got != "   9: -return oldValue" {
		t.Fatalf("unexpected stripped deleted line: %q", got)
	}
}

func TestInsertPastesClipboardIntoInput(t *testing.T) {
	oldReadClipboard := readClipboard
	oldTimeNow := timeNow
	defer func() {
		readClipboard = oldReadClipboard
		timeNow = oldTimeNow
	}()

	readClipboard = func() (string, error) {
		return "第一行\r\n第二行", nil
	}
	timeNow = func() time.Time {
		return time.Unix(100, 0)
	}

	m := Model{
		mode:  modeChat,
		input: textarea.New(),
	}
	m.input.Focus()

	updatedModel, _ := m.updateChat(tea.KeyMsg{Type: tea.KeyInsert})
	updated := updatedModel.(Model)

	if updated.notice != "已从系统剪贴板粘贴" {
		t.Fatalf("unexpected notice: %q", updated.notice)
	}
	if got := updated.input.Value(); got != "第一行\n第二行" {
		t.Fatalf("unexpected pasted input: %q", got)
	}
}

func TestEnterDuringPasteBurstInsertsNewlineInsteadOfSending(t *testing.T) {
	oldTimeNow := timeNow
	defer func() {
		timeNow = oldTimeNow
	}()

	now := time.Unix(100, 0)
	timeNow = func() time.Time {
		return now
	}

	var sink bytes.Buffer
	m := Model{
		mode:  modeChat,
		input: textarea.New(),
		backend: &BackendClient{
			stdin: nopWriteCloser{Buffer: &sink},
		},
	}
	m.input.Focus()

	updatedModel, _ := m.updateChat(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune("hello"), Paste: true})
	updated := updatedModel.(Model)

	now = now.Add(10 * time.Millisecond)
	updatedModel, _ = updated.updateChat(tea.KeyMsg{Type: tea.KeyEnter})
	updated = updatedModel.(Model)

	if sink.Len() != 0 {
		t.Fatalf("expected no backend send during paste burst, got %q", sink.String())
	}
	if got := updated.input.Value(); got != "hello\n" {
		t.Fatalf("unexpected input after enter: %q", got)
	}
}

func TestEnterSendsMultiRuneInputWithoutPasteFlag(t *testing.T) {
	var sink bytes.Buffer
	m := Model{
		mode:  modeChat,
		input: textarea.New(),
		backend: &BackendClient{
			stdin: nopWriteCloser{Buffer: &sink},
		},
	}
	m.input.Focus()

	updatedModel, _ := m.updateChat(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune("你好世界")})
	updated := updatedModel.(Model)

	updatedModel, _ = updated.updateChat(tea.KeyMsg{Type: tea.KeyEnter})
	updated = updatedModel.(Model)

	if sink.Len() == 0 {
		t.Fatalf("expected enter to send multi-rune input")
	}
	var payload map[string]any
	if err := json.Unmarshal(sink.Bytes(), &payload); err != nil {
		t.Fatalf("decode payload failed: %v; raw=%q", err, sink.String())
	}
	if payload["type"] != "user_message" {
		t.Fatalf("unexpected request type: %#v", payload)
	}
	if payload["content"] != "你好世界" {
		t.Fatalf("unexpected content: %#v", payload["content"])
	}
	if got := updated.input.Value(); got != "" {
		t.Fatalf("expected input to reset after send, got %q", got)
	}
}

func TestEnterDoesNotSendWhenInputAlreadyMultiline(t *testing.T) {
	var sink bytes.Buffer
	m := Model{
		mode:  modeChat,
		input: textarea.New(),
		backend: &BackendClient{
			stdin: nopWriteCloser{Buffer: &sink},
		},
	}
	m.input.Focus()
	m.input.SetValue("第一行\n第二行")

	updatedModel, _ := m.updateChat(tea.KeyMsg{Type: tea.KeyEnter})
	updated := updatedModel.(Model)

	if sink.Len() != 0 {
		t.Fatalf("expected multiline enter to stay in editor, got %q", sink.String())
	}
	if got := updated.input.Value(); got != "第一行\n第二行\n" {
		t.Fatalf("unexpected multiline input after enter: %q", got)
	}
}

func TestCtrlSSendsMultilineInput(t *testing.T) {
	var sink bytes.Buffer
	m := Model{
		mode:  modeChat,
		input: textarea.New(),
		backend: &BackendClient{
			stdin: nopWriteCloser{Buffer: &sink},
		},
	}
	m.input.Focus()
	m.input.SetValue("第一行\n第二行")

	updatedModel, _ := m.updateChat(tea.KeyMsg{Type: tea.KeyCtrlS})
	updated := updatedModel.(Model)

	if sink.Len() == 0 {
		t.Fatalf("expected ctrl+s to send multiline input")
	}
	var payload map[string]any
	if err := json.Unmarshal(sink.Bytes(), &payload); err != nil {
		t.Fatalf("decode payload failed: %v; raw=%q", err, sink.String())
	}
	if payload["type"] != "user_message" {
		t.Fatalf("unexpected request type: %#v", payload)
	}
	if payload["content"] != "第一行\n第二行" {
		t.Fatalf("unexpected content: %#v", payload["content"])
	}
	if got := updated.input.Value(); got != "" {
		t.Fatalf("expected input to reset after ctrl+s send, got %q", got)
	}
}

func assertMessageOrder(t *testing.T, messages []ChatMessage, want []string) {
	t.Helper()

	got := make([]string, 0, len(messages))
	for _, message := range messages {
		got = append(got, message.ID)
	}

	if len(got) != len(want) {
		t.Fatalf("message count mismatch: got=%v want=%v", got, want)
	}
	for index := range want {
		if got[index] != want[index] {
			t.Fatalf("message order mismatch: got=%v want=%v", got, want)
		}
	}
}

func newSessionPickerListForTest() list.Model {
	delegate := list.NewDefaultDelegate()
	delegate.ShowDescription = true
	sessionList := list.New([]list.Item{sessionItem{createNew: true}}, delegate, 40, 12)
	sessionList.Title = "周行 / 选择会话"
	sessionList.SetShowHelp(false)
	sessionList.SetShowStatusBar(false)
	sessionList.SetFilteringEnabled(true)
	return sessionList
}

func newChatModelForLayoutTest() Model {
	input := textarea.New()
	input.Placeholder = "输入消息"
	input.Prompt = "│ "
	input.ShowLineNumbers = false
	input.Focus()

	return Model{
		mode:             modeChat,
		list:             newSessionPickerListForTest(),
		viewport:         viewport.New(80, 20),
		input:            input,
		collapseToolLogs: true,
		activeSession: &SessionRecord{
			ID:    "session_layout",
			Title: "布局测试",
			Messages: []ChatMessage{
				{ID: "user_1", Role: "user", Content: "请帮我检查日志折叠"},
				{ID: "assistant_1", Role: "assistant", Content: "我会先读取相关文件。"},
				{
					ID:   "tool_read",
					Role: "tool",
					Name: "read_file",
					Content: strings.Join([]string{
						"File D:\\Auto\\research\\Astronomy\\ZhouXing\\internal\\tui\\model.go lines 1-5:",
						"   1: package tui",
						"   2: import (",
						"   3: \"fmt\"",
						"   4: \"strings\"",
						"   5: \"time\"",
					}, "\n"),
				},
			},
		},
		status: StatusPayload{
			Model: "deepseek",
			Context: ContextUsage{
				UsedTokens:  12,
				LimitTokens: 128,
			},
		},
	}
}

func contains(text string, fragment string) bool {
	return strings.Contains(text, fragment)
}

type nopWriteCloser struct {
	*bytes.Buffer
}

func (n nopWriteCloser) Write(p []byte) (int, error) {
	return n.Buffer.Write(p)
}

func (n nopWriteCloser) Close() error {
	return nil
}
