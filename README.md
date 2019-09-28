`lura` is a collection of devops-oriented utility modules.


| Module           | Description                                                                |
| ---------------- | -------------------------------------------------------------------------- |
| `assets`         | syntactic sugar for `pkg_resources`                                        |
| `at`             | api for periodic task scheduling using `schedule`                          |
| `attrs`          | `dict`s with keys accessible as attributes                                 |
| `concurl`        | framework for http testers and stressers                                   |
| `crypto`         | syntactic sugar for `cryptography.fernet`                                  |
| `docker`         | api for docker cli                                                         |
| `docker.compose` | api for docker-compose cli                                                 |
| `formats`        | api for dealing with json, yaml, etc.                                      |
| `git`            | api for git cli                                                            |
| `hash`           | syntactic sugar for hashlib                                                |
| `installer`      | primitive software installer                                               |
| `kube`           | api for kubectl cli                                                        |
| `log`            | helpers for `logging` including an easy application-level configurator     |
| `messaging`      | api for sending messages to discord, teams, etc.                           |
| `plates`         | api for dealing with jinja2, `string.Template`, etc.                       |
| `rpc`            | syntactic sugar for `rpyc`                                                 |
| `run`            | api for running shell commands, optionally with sudo                       |
| `ssh`            | syntactic sugar for `fabric.Connection`                                    |
| `sudo`           | sudoing `popen()` and a helper for implementing sudo support using askpass |
| `system`         | api for operating local and remote unix systems                            |
| `systemd`        | api for systemctl and journalctl clis                                      |
| `threads`        | syntactic sugar for `threading`                                            |
| `time`           | time utilities                                                             |
