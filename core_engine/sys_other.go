//go:build !windows

package main

import (
	"os/exec"
)

func setHideWindow(cmd *exec.Cmd) {
	// No-op on Linux and macOS, as there's no console window to hide
}