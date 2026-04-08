//go:build !windows

package main

import (
	"os/exec"
	"syscall"
)

// setProcessGroup puts the child in its own process group so we can
// kill the entire tree (parent + children) with a single signal.
func setProcessGroup(cmd *exec.Cmd) {
	cmd.SysProcAttr = &syscall.SysProcAttr{Setpgid: true}
}

// killProcessGroup sends SIGKILL to the entire process group.
// Negative pid = kill the group, not just the leader.
func killProcessGroup(cmd *exec.Cmd) {
	if cmd.Process != nil {
		_ = syscall.Kill(-cmd.Process.Pid, syscall.SIGKILL)
	}
}
