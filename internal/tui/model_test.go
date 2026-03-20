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
		status: StatusPayload{
			Model: "deepseek",
			Context: ContextUsage{
				UsedTokens:  12,
				LimitTokens: 128,
			},
		},
	}

	status := m.renderStatus()
	for _, want := range []string{"Ctrl+V/Insert 粘贴", "Ctrl+Y/F5 复制"} {
		if !contains(status, want) {
			t.Fatalf("status missing hint %q: %s", want, status)
		}
	}
}

func TestCtrlVPastesClipboardIntoInput(t *testing.T) {
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

	updatedModel, _ := m.updateChat(tea.KeyMsg{Type: tea.KeyCtrlV})
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

	updatedModel, _ := m.updateChat(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune("hello")})
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
