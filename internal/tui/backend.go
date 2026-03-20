package tui

import (
	"bufio"
	"encoding/json"
	"fmt"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"sync"
)

type ReadyPayload struct {
	Model       string `json:"model"`
	OfflineMode bool   `json:"offline_mode"`
	RootDir     string `json:"root_dir"`
	SandboxDir  string `json:"sandbox_dir"`
	LogPath     string `json:"log_path"`
}

type SessionSummary struct {
	ID           string         `json:"id"`
	Title        string         `json:"title"`
	CreatedAt    string         `json:"created_at"`
	UpdatedAt    string         `json:"updated_at"`
	MessageCount int            `json:"message_count"`
	Summary      string         `json:"summary"`
	Meta         map[string]any `json:"meta"`
}

type ChatMessage struct {
	ID         string         `json:"id"`
	Role       string         `json:"role"`
	Content    string         `json:"content"`
	CreatedAt  string         `json:"created_at"`
	Name       string         `json:"name"`
	ToolCallID string         `json:"tool_call_id"`
	Meta       map[string]any `json:"meta"`
}

type SessionRecord struct {
	ID        string         `json:"id"`
	Title     string         `json:"title"`
	CreatedAt string         `json:"created_at"`
	UpdatedAt string         `json:"updated_at"`
	Summary   string         `json:"summary"`
	Messages  []ChatMessage  `json:"messages"`
	Meta      map[string]any `json:"meta"`
}

type ContextUsage struct {
	UsedTokens   int     `json:"used_tokens"`
	LimitTokens  int     `json:"limit_tokens"`
	CachedTokens int     `json:"cached_tokens"`
	UsageRatio   float64 `json:"usage_ratio"`
}

type StatusPayload struct {
	Phase       string       `json:"phase"`
	Busy        bool         `json:"busy"`
	QueueLength int          `json:"queue_length"`
	Model       string       `json:"model"`
	OfflineMode bool         `json:"offline_mode"`
	SessionID   string       `json:"session_id"`
	Context     ContextUsage `json:"context"`
}

type ProgressPayload struct {
	Phase       string       `json:"phase"`
	Model       string       `json:"model"`
	OfflineMode bool         `json:"offline_mode"`
	Context     ContextUsage `json:"context"`
	Step        int          `json:"step"`
}

type ToolEvent struct {
	ID             string         `json:"id"`
	AfterMessageID string         `json:"after_message_id"`
	Tool           string         `json:"tool"`
	Phase          string         `json:"phase"`
	Command        string         `json:"command"`
	CWD            string         `json:"cwd"`
	Summary        string         `json:"summary"`
	Text           string         `json:"text"`
	Channel        string         `json:"channel"`
	Step           int            `json:"step"`
	AfterSec       int            `json:"after_sec"`
	ExitCode       int            `json:"exit_code"`
	DurationSec    float64        `json:"duration_sec"`
	TimeoutSec     int            `json:"timeout_sec"`
	TimedOut       bool           `json:"timed_out"`
	Arguments      map[string]any `json:"arguments"`
}

type Event struct {
	Type           string
	Ready          *ReadyPayload
	Sessions       []SessionSummary
	Session        *SessionRecord
	Message        *ChatMessage
	AfterMessageID string
	Status         *StatusPayload
	Progress       *ProgressPayload
	Tool           *ToolEvent
	Error          string
	Stderr         string
}

type BackendClient struct {
	rootDir string
	cmd     *exec.Cmd
	stdin   io.WriteCloser
	events  chan Event

	sendMu    sync.Mutex
	closeOnce sync.Once
	readWG    sync.WaitGroup
}

func StartBackend(rootDir string) (*BackendClient, error) {
	pythonPath := filepath.Join(rootDir, ".venv", "Scripts", "python.exe")
	if _, err := os.Stat(pythonPath); err != nil {
		return nil, fmt.Errorf("backend python not found at %s", pythonPath)
	}

	cmd := exec.Command(pythonPath, "-X", "utf8", "-m", "zhouxing.backend")
	cmd.Dir = rootDir
	cmd.Env = append(os.Environ(), "PYTHONDONTWRITEBYTECODE=1", "PYTHONUTF8=1")

	stdout, err := cmd.StdoutPipe()
	if err != nil {
		return nil, fmt.Errorf("attach backend stdout failed: %w", err)
	}
	stderr, err := cmd.StderrPipe()
	if err != nil {
		return nil, fmt.Errorf("attach backend stderr failed: %w", err)
	}
	stdin, err := cmd.StdinPipe()
	if err != nil {
		return nil, fmt.Errorf("attach backend stdin failed: %w", err)
	}
	if err := cmd.Start(); err != nil {
		return nil, fmt.Errorf("start backend failed: %w", err)
	}

	client := &BackendClient{
		rootDir: rootDir,
		cmd:     cmd,
		stdin:   stdin,
		events:  make(chan Event, 2048),
	}
	client.readWG.Add(2)
	go client.readStdout(stdout)
	go client.readStderr(stderr)
	go client.wait()

	if err := client.Send(map[string]any{"type": "hello"}); err != nil {
		_ = client.Close()
		return nil, err
	}
	return client, nil
}

func (c *BackendClient) Events() <-chan Event {
	return c.events
}

func (c *BackendClient) Send(payload any) error {
	c.sendMu.Lock()
	defer c.sendMu.Unlock()

	encoder := json.NewEncoder(c.stdin)
	if err := encoder.Encode(payload); err != nil {
		return fmt.Errorf("send backend request failed: %w", err)
	}
	return nil
}

func (c *BackendClient) Close() error {
	var closeErr error
	c.closeOnce.Do(func() {
		if c.stdin != nil {
			_ = c.stdin.Close()
		}
		if c.cmd != nil && c.cmd.Process != nil {
			closeErr = c.cmd.Process.Kill()
		}
	})
	return closeErr
}

func (c *BackendClient) readStdout(reader io.Reader) {
	defer c.readWG.Done()
	scanner := bufio.NewScanner(reader)
	scanner.Buffer(make([]byte, 0, 4096), 8*1024*1024)
	for scanner.Scan() {
		event, err := parseEvent(scanner.Bytes())
		if err != nil {
			c.events <- Event{Type: "error", Error: fmt.Sprintf("decode backend event failed: %v", err)}
			continue
		}
		c.events <- event
	}
	if err := scanner.Err(); err != nil {
		c.events <- Event{Type: "stderr", Stderr: fmt.Sprintf("backend stdout scanner failed: %v", err)}
	}
}

func (c *BackendClient) readStderr(reader io.Reader) {
	defer c.readWG.Done()
	scanner := bufio.NewScanner(reader)
	scanner.Buffer(make([]byte, 0, 1024), 256*1024)
	for scanner.Scan() {
		c.events <- Event{Type: "stderr", Stderr: scanner.Text()}
	}
	if err := scanner.Err(); err != nil {
		c.events <- Event{Type: "stderr", Stderr: fmt.Sprintf("backend stderr scanner failed: %v", err)}
	}
}

func (c *BackendClient) wait() {
	err := c.cmd.Wait()
	c.readWG.Wait()
	if err != nil {
		c.events <- Event{Type: "closed", Error: err.Error()}
	} else {
		c.events <- Event{Type: "closed"}
	}
	close(c.events)
}

func parseEvent(line []byte) (Event, error) {
	var header struct {
		Type string `json:"type"`
	}
	if err := json.Unmarshal(line, &header); err != nil {
		return Event{}, err
	}

	switch header.Type {
	case "ready":
		var payload struct {
			Type string `json:"type"`
			ReadyPayload
		}
		if err := json.Unmarshal(line, &payload); err != nil {
			return Event{}, err
		}
		return Event{Type: payload.Type, Ready: &payload.ReadyPayload}, nil
	case "session_list":
		var payload struct {
			Type     string           `json:"type"`
			Sessions []SessionSummary `json:"sessions"`
		}
		if err := json.Unmarshal(line, &payload); err != nil {
			return Event{}, err
		}
		return Event{Type: payload.Type, Sessions: payload.Sessions}, nil
	case "session_loaded":
		var payload struct {
			Type    string        `json:"type"`
			Session SessionRecord `json:"session"`
		}
		if err := json.Unmarshal(line, &payload); err != nil {
			return Event{}, err
		}
		return Event{Type: payload.Type, Session: &payload.Session}, nil
	case "message":
		var payload struct {
			Type           string      `json:"type"`
			Message        ChatMessage `json:"message"`
			AfterMessageID string      `json:"after_message_id"`
		}
		if err := json.Unmarshal(line, &payload); err != nil {
			return Event{}, err
		}
		return Event{
			Type:           payload.Type,
			Message:        &payload.Message,
			AfterMessageID: payload.AfterMessageID,
		}, nil
	case "status":
		var payload struct {
			Type string `json:"type"`
			StatusPayload
		}
		if err := json.Unmarshal(line, &payload); err != nil {
			return Event{}, err
		}
		return Event{Type: payload.Type, Status: &payload.StatusPayload}, nil
	case "progress":
		var payload struct {
			Type string `json:"type"`
			ProgressPayload
		}
		if err := json.Unmarshal(line, &payload); err != nil {
			return Event{}, err
		}
		return Event{Type: payload.Type, Progress: &payload.ProgressPayload}, nil
	case "tool_event":
		var payload struct {
			Type string `json:"type"`
			ToolEvent
		}
		if err := json.Unmarshal(line, &payload); err != nil {
			return Event{}, err
		}
		return Event{Type: payload.Type, Tool: &payload.ToolEvent}, nil
	case "error":
		var payload struct {
			Type    string `json:"type"`
			Message string `json:"message"`
		}
		if err := json.Unmarshal(line, &payload); err != nil {
			return Event{}, err
		}
		return Event{Type: payload.Type, Error: payload.Message}, nil
	default:
		return Event{Type: header.Type}, nil
	}
}
