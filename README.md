`lura` is a collection of devops-oriented utility modules.

| Module           | Description                                                                |
| ---------------- | -------------------------------------------------------------------------- |
| `asset`          | syntactic sugar for `pkg_resources`                                        |
| `at`             | api for periodic task scheduling using `schedule`                          |
| `attrs`          | `dict`s with keys accessible as attributes                                 |
| `concurl`        | framework for http testers and stressers                                   |
| `crypto`         | syntactic sugar for `cryptography.fernet`                                  |
| `docker`         | api for docker cli                                                         |
| `docker.compose` | api for docker-compose cli                                                 |
| `formats`        | api for dealing with json, yaml, etc.                                      |
| `git`            | api for git cli                                                            |
| `hash`           | syntactic sugar for hashlib                                                |
| `kube`           | api for kubectl cli                                                        |
| `logutils`       | extensions for logging and an easy package-level configurator              |
| `messaging`      | api for sending messages to discord, teams, etc.                           |
| `plates`         | api for dealing with jinja2, `string.Template`, etc.                       |
| `rpc`            | syntactic sugar for `rpyc`                                                 |
| `run`            | api for running shell commands, optionally with sudo                       |
| `ssh`            | wrapper for `fabric.Connection`                                            |
| `sudo`           | sudoing `popen()` and a helper for implementing sudo support using askpass |
| `systemd`        | api for systemctl and journalctl clis                                      |
| `threads`        | cancellable threads and synchronization helpers                            |
| `time`           | time utilities                                                             |
