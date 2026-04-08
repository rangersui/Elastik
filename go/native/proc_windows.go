//go:build windows

package main

import (
	"os/exec"
	"syscall"
)

// setProcessGroup assigns CREATE_NEW_PROCESS_GROUP so the child gets
// its own group.  On Windows, exec.CommandContext already calls
// TerminateProcess which kills the leader; Job Objects would be needed
// for full tree kill, but CREATE_NEW_PROCESS_GROUP + cmd.Process.Kill()
// covers the common case and avoids cgo / win32 API complexity.
func setProcessGroup(cmd *exec.Cmd) {
	cmd.SysProcAttr = &syscall.SysProcAttr{
		CreationFlags: syscall.CREATE_NEW_PROCESS_GROUP,
	}
}

// killProcessGroup on Windows falls back to killing just the leader.
// Full process-tree kill requires Job Objects (not worth the complexity
// for a dev tool — the test harness does wmic cleanup for edge cases).
func killProcessGroup(cmd *exec.Cmd) {
	if cmd.Process != nil {
		_ = cmd.Process.Kill()
	}
}
