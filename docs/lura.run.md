# lura.run.run()

```
def run(
  argv,
  mode = 'popen',
  env = None,
  cwd = None,
  shell = None,
  stdout = [],
  stderr = [],
  sudo_user = None,
  sudo_group = None,
  sudo_password = None,
  sudo_login = None,
  sudo_timeout = 3,
  enforce = 0,
):
  pass
```
```
:param [str, Sequence]   argv:          command
:param str               mode:          popen, pty, sudo
:param dict              env:           environment
:param string            cwd:           working directory
:param bool              shell:         run with shell
:param [file, Sequence]  stdout:        file or list of files
:param [file, Sequence]  stderr:        file or list of files
:param str               sudo_user:     sudo user
:param str               sudo_group:    sudo group
:param str               sudo_password: sudo password
:param str               sudo_login:    execute login scripts
:param float             sudo_timeout:  askpass password timeout
:param [None, int]       enforce:       enforce exit code, disabled if None
```

The `lura.run` module tries to improve quality of life while working with
unix shell commands by

- using context managers to reduce the number of arguments needed for
  multiple commands.
- providing i/o hooks for easy and multiple output redirection.
- allowing commands to be run in ptys.
- allowing commands to be run as root with sudo without worrying about
  password interaction.

`lura.run` is not well-suited for:

- handling binary output from commands. It's unclear whether `lura.run` should
  handle binary data as this is a tool to ease human interaction with things
  like gnu coreutils and not a data processing library. This will be
  investigated further.
- handling output volume on the order of gigabyes from commands. `lura.run`
  buffers all command output to memory as the command runs, and returns it to
  the user in the `run.result` object. It can efficiently handle as much output
  as your machine has memory, but it doesn't do anything special to make the
  process more resource-friendly, like buffering output to files.
- complex pipeline configurations. `lura.run` can process shell command
  pipelines using the system shell when `shell` is `True`, but all of the work
  is done by the shell, and we provide no additional capabilities.

## Argument overview

## Modes

Run has three modes, `popen` (the default), `pty`, and `sudo`.

### popen mode and result objects

`popen` is the default mode and uses `subprocess.Popen` to run commands.

Run `ls -l /` and cature the result:

```
> from lura.run import run
> result = run('ls -l /')
```

The result object has attributes like `argv`, `code`, `stdout`, etc.

```
> result
<lura.run.Result object at 0x7f1075f0edd8>
> result.code
0
> result.argv
(...)
```

Result objects have `as_dict()`, `format()`, `print()`, and `log()` methods.

```
> type(result.format())
<class 'str'>
```
`result.print()` sends `result.format()`'s return value to stdout, where we can
see that it is a yaml expression of `result`'s attributes:
```
> result.print()
run:
  args: 'ls -l /'
  argv:
    - ls
    - '-l'
    - /
  code: 0
  stdout: |
    total 56
    lrwxrwxrwx   1 root root    7 Mar 30 19:40 bin -> usr/bin
    drwxr-xr-x   1 root root  386 Apr 12 12:01 boot
    drwxr-xr-x  20 root root 4420 Jun 14 09:07 dev
    drwxr-xr-x   1 root root 3920 Jun 15 19:52 etc
    drwxr-xr-x   1 root root    8 Mar 30 19:51 home
(...)
> import logging
> logger = logging.get_logger('lura.run.example')
> result.log(logger)
(...)
>
```

### pty mode

pty mode uses ptyprocess to launch a process in a pseudoterminal. Some
programs behave differently when attached to a pty and it's sometimes useful
to run them this way from scripts. A pty has one output stream (the console),
so the stderr argument is ignored.

```
> result = run('ls -l /', mode='pty')
# or
> result = run.pty('ls -l /')
> result.print()
run:
  args: 'ls -l /'
  argv:
    - ls
    - '-l'
    - /
  code: 0
  stdout: |
    total 56
    lrwxrwxrwx   1 root root    7 Mar 30 19:40 bin -> usr/bin
    drwxr-xr-x   1 root root  386 Apr 12 12:01 boot
    drwxr-xr-x  20 root root 4420 Jun 14 09:07 dev
    drwxr-xr-x   1 root root 3920 Jun 15 19:52 etc
    drwxr-xr-x   1 root root    8 Mar 30 19:51 home
(...)
>
```

### sudo mode

sudo mode uses lura.sudo to run commands as root

```
> password = run.getsudopass()
[sudo] password for eckso:
> result = run('ls -l /root', mode='sudo', sudo_password=password)
# or
> result = run.sudo('ls -l /root', sudo_password=password)
> result.print()
run:
  args: 'ls -l /root'
  argv:
    - ls
    - '-l'
    - /root
  code: 0
  stdout: |
    total 0
    -rw-r--r-- 1 root root 0 Jun 10 20:49 hello-from-root
  stderr: ""
> run.sudo('whoami', sudo_password=password).print()
run:
  args: whoami
  argv:
    - whoami
  code: 0
  stdout: "root\n"
  stderr: ""

```

## Context managers

`lura.run` context manages exist to solve the problem of wanting to run many
commands with the same set of flags. Context managers will set a number
of flags for the duration of the context, unsetting them at the end.

### Enforce

`Enforce` allows the `enforce` argument to be set for a context.

```
# without context manager
run('/bin/false', enforce=0) # Enforce exit code 0, raises exception
run('/bin/false', enforce=1) # Enforce exit code 0, no exception raised

# with context manager

with run.Enforce(0):
  run('/bin/false')
  # raises exception, /bin/false did not exit 0

with run.Enforce(1):
  run('/bin/false')
  # no exception, /bin/false exits 1
```

### Quash

`Quash` sets the `enforce` argument to `None` for a context, which disabled
exit code enforcement.

```
with run.Quash():
  run('/bin/false')
  # no exception
```

### Stdio

```
with run.Stdio(sys.stdout, sys.stderr):
  run('echo hello')
hello

from io import StringIO()

buf = StringIO()
with run.Stdio(StringIO())
  run('echo hello')
print(buf.getvalue())
hello
```

### Log

### Sudo

```
run('git clone https://github.com/myfunhub/funhub')
password = run.getsudopassword()
[sudo] password for eckso:
with run.Sudo(password):
  run('apt-get install -y nginx')
  run('cp funhub/funhub.conf /etc/nginx/sites-enabled')
  run('systemctl restart nginx')
```

## Internals

### Argument processing

There are three ways to set the variables `run()` will finally execute with.
For the following, consider that `enforce` is set to  `0` by default, which
will raise an exception when a command exits with something other than code 0.

1. Passing arguments directly.

```
run('/bin/false', enforce=None)   # Does not enforce exit code.
# no exception
```
2. Passing arguments indirectly by using a context manager. The context
   managers work by setting variables in thread-local storage at `run.context`.

```
with run.Enforce(None):           # Sets run.context.enforce to None
  run('/bin/false')               # Does not enforce exit code
# no exception
```

3. Setting the default in `run.defaults`. If the user supplies no argument, and
   no context is used, then the the value from `run.defaults` is used.

```
run.defaults.enforce = None       # Set global default to None
run('/bin/false')                 # Does not enforce exit code
# no exception
```

- Arguments always take precedence.

```
run.defaults.enforce = None       # Set global default to None
with run.Enforce(None):           # Sets run.context.enforce to None
  run('/bin/false', enforce=0)    # Enforces exit code 0
# raises exception
```

- Context managers take precedence over defaults.

```
run.defaults.enforce = None       # Set global default to None
with run.Enforce(0):              # Sets run.context.enforce to 0
  run('/bin/false')               # Enforces exit code 0
# raises exception
```

`run()` accepts a bundle of `kwargs` and passes them to to `merge_args()` to sort
out. Once the arguments are in order, run calls one of `runpopen`, `runpty`, or
`runsudo`, depending on the value fo the `mode` argument. It will either raise
`run.error` on unexpected exit code, or return a `run.result` object.

`merge_args()` uses `lookup()` to resolve all arguments other than `stdout` and
`stderr`.

`lookup()` first checks `run.context` for an argument value, and returns it if
found; else the value from `run.defaults` is returned.

`merge_args()` and `lookup()` handle `stdout` and `stderr` as special cases.
`run()` lets users pass lists of file objects for `stdio` and `stderr` if they
choose - mostly to make the implementation a bit cleaner, but also because why
not.

Anyway, for each of `stdout` and `stderr`, the list of file objects passed by
the user is joined with the lists of file objects from `run.context` and
`run.defaults`. So for example, each line of `stdout` will be sent to the
following file objects:

- all file objects passed by the user via `run(stdout=...)`
- all file objects in the list `run.context.stdout`
- all file objects in the list `run.defaults.stdout`
