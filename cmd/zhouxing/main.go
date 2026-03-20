package main

import (
	"fmt"
	"os"
	"path/filepath"

	tea "github.com/charmbracelet/bubbletea"

	"zhouxing/internal/tui"
)

func main() {
	root, err := os.Getwd()
	if err != nil {
		fmt.Fprintf(os.Stderr, "resolve working directory failed: %v\n", err)
		os.Exit(1)
	}
	root, err = filepath.Abs(root)
	if err != nil {
		fmt.Fprintf(os.Stderr, "resolve absolute path failed: %v\n", err)
		os.Exit(1)
	}

	model, err := tui.New(root)
	if err != nil {
		fmt.Fprintf(os.Stderr, "initialize TUI failed: %v\n", err)
		os.Exit(1)
	}

	program := tea.NewProgram(model, tea.WithAltScreen(), tea.WithMouseAllMotion())
	if _, err := program.Run(); err != nil {
		fmt.Fprintf(os.Stderr, "run TUI failed: %v\n", err)
		os.Exit(1)
	}
}
