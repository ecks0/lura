'''
A front-end for subprocess.'

### Example

```
from lura.run import run

>>> res = run('ls -l /')
>>> res.code
0
>>> res.stdout
'total 28\n<... etc ...>'
>>> res.stderr
''
```

### `run()` function

The `run()` function executes commands in subprocesses and returns a `Result`
object containing the exit code, stdout, stderr, and more.

`run()` arguments:

```
def run(

  argv: Union[str, Sequence[str]],
  # may be a string or list of strings

  env: Optional[Mapping[str, str]] = None,
  # environment variables for child process

  env_replace: bool = False,
  # if True, use only environment ariables from env;
  # if False, merge environment variables from os.environ and env

  cwd: Optional[str] = None,
  # run command in the specified directory

  shell: bool = False,
  # if True, run with the system shell;
  # if False, do not run with the system shell

  stdin: Optional[IO] = None,
  # file input for stdin

  stdout: Optional[Sequence[IO]] = None,
  # list of files to receive stdout in real time

  stderr: Optional[Sequence[IO]] = None,
  # list of files to receive stderr in real time

  enforce: bool = True,
  # if True, raise Error when subprocess exits with a code other than
  # enforce_code (see below);
  # if False, enforce_code and the subprocess exit code are ignored

  enforce_code: int = 0,
  # when enforce is True, raise Error when subprocess exits with code
  # other than this

  text: bool = True,
  # if True, use text i/o using the specified encoding (see below);
  # if False, use binary i/o and ignore encoding (see below)

  encoding: Optional[str] = None,
  # text encoding for text i/o mode. uses system default text encoding if None.
  # ignored when text is False

) -> Result: ...
```

### `Result` object

`Result` is the return value of `run()`.

```
class Result:

  args: str
  # argv as string

  argv: Sequence[str]
  # argv as list

  code: int
  # subprocess result code

  stdout: Union[bytes, str]
  # stdout as bytes or str

  stderr: Union[bytes, str]
  # stderr as bytes or str

  context: Mapping[str, Any]
  # variables set by context managers at the time of run() call

  def format(self) -> str: ...
  # return instance variable names and values as yaml string

  def print(self, file=None) -> None: ...
  # print instance variable names and values as yaml string. prints to stdout
  # if file is None
```

### `Error` object

`Error` is raised when the subprocess exits with an unexpected exit code.
The `run()` arguments `enforce` and `enforce_code` control this behavior.

```
class Error(RuntimeError):

  result: Result
  # Result instance describing failed run() call
```

### Context managers

Context managers can be used to set arguments and/or combinations of arguments
for successive calls to `run()`.

For example, the following `run()` call would normally raise `Error` for
non-zero exit code, but the `run.quash()` context manager disables enforcing
of exit values:

```
>> with run.quash():
..   res = run('/bin/false')
..   print(res.code)
..
1
```

Available context managers:

```
  @contextmanager
  def quash(self) -> Iterator[None]: ...
  # do not enforce exit code while in this context

  @contextmanager
  def enforce(self, enforce_code: int = 0) -> Iterator[None]: ...
  # enforce exit code enforce_code while in this context

  @contextmanager
  def cwd(self, cwd: str) -> Iterator[None]: ...
  # run in directory cwd while in this context

  @contextmanager
  def shell(self) -> Iterator[None]: ...
  # run commands with the system shell while in this context

  @contextmanager
  def log(self, logger: logging.Logger, log_level: int = logging.DEBUG) -> Iterator[None]: ...
  # send stdout and stderr to a logger while in this context
```
'''

import io
import logging
import os
import shlex
import subprocess
import sys
import threading
import traceback
from contextlib import contextmanager
from copy import deepcopy
from enum import Enum
from lura.formats import Pyaml
from lura.threads import Thread
from lura.attrs import attr
from subprocess import list2cmdline as shjoin
from typing import (
  Any, Callable, IO, Iterator, Mapping, Optional, Sequence, TextIO, Tuple,
  Type, Union, cast
)

#####
## globals

logger = logging.getLogger(__name__)

# maximum amount of time in seconds to spend polling for a process's exit code
# before allowing execution to return to the interpreter
PROCESS_POLL_INTERVAL = 1.0

# maximum amount of time in seconds to wait for stdio threads to join before
# giving up
STDIO_JOIN_TIMEOUT = 0.5

#####
## context manager state

class Context(threading.local):
  'Thread-local storage for run arguments set via context managers.'

  # default values for some run() arguments are also set here

  env: Optional[Mapping[str, str]]
  env_replace: bool
  cwd: Optional[str]
  shell: bool
  stdin: Optional[IO]
  stdout: Optional[Sequence[IO]]
  stderr: Optional[Sequence[IO]]
  enforce: bool
  enforce_code: int
  text: bool
  encoding: Optional[str]

  def __init__(self) -> None:
    super().__init__()
    self.env = None
    self.env_replace = False # run() default, inherit os.environ when False
    self.cwd = None
    self.shell = False       # run() default
    self.stdin = None
    self.stdout = None
    self.stderr = None
    self.enforce = True      # run() default, enforce_code is ignored when False
    self.enforce_code = 0    # run() default, raise if process does not exit with this code
    self.text = True         # run() default, encoding is ignored when False
    self.encoding = None     # run() default, uses system default when None

#####
## run result and error

class Result:
  'The value returned by `run()`.'

  args: str                  # argv as string
  argv: Sequence[str]        # argv as list
  code: int                  # result code
  stdout: Union[bytes, str]  # stdout
  stderr: Union[bytes, str]  # stderr
  context: Mapping[str, Any] # arguments from context managers

  def __init__(
    self,
    argv: Union[str, Sequence[str]],
    code: int,
    stdout: str,
    stderr: str,
    context: Context,
  ) -> None:

    super().__init__()
    if isinstance(argv, str):
      self.args = argv
      self.argv = shlex.split(argv)
    else:
      self.args = shjoin(argv)
      self.argv = argv
    self.code = code
    self.stdout = stdout
    self.stderr = stderr
    # copy the context's values, but don't keep a reference to the context as
    # it will be reset when context managers exit
    self.context = deepcopy(vars(context))

  def format(self) -> str:
    return Pyaml().dumps({
      'run': {
        'argv': self.args,
        'code': self.code,
        'stdout': self.stdout,
        'stderr': self.stderr,
      }
    })

  def print(self, file=None) -> None:
    file = sys.stdout if file is None else file
    file.write(self.format())

class Error(RuntimeError):
  'Raised by run() when a subprocess exits with an unexpected code.'

  result: Result

  def __init__(self, enforce_code: int, result: Result) -> None:
    msg = 'Expected exit code {} but received {}{}{}'.format(
      enforce_code, result.code, os.linesep, result.format())
    super().__init__(msg)
    self.result = result

#####
## stdio handling

class IoModes(Enum):
  BINARY = 'binary'
  TEXT   = 'text'

def get_io_mode(file: Any) -> IoModes:
  if hasattr(file, 'mode'):
    return IoModes.BINARY if 'b' in file.mode else IoModes.TEXT
  elif isinstance(file, (io.RawIOBase, io.BufferedIOBase)):
    return IoModes.BINARY
  elif isinstance(file, io.TextIOBase):
    return IoModes.TEXT
  else:
    raise ValueError(f'Unable to determine file object io mode: {file}')

class Tee(Thread):
  'Read data from one source and write it to many targets.'

  buflen = 4096          # buffer size for binary io

  _mode: IoModes         # io mode of source file object
  _source: IO            # source file object
  _targets: Sequence[IO] # target file objects
  _work: bool

  def __init__(self, source: IO, targets: Sequence[IO], name='Tee'):
    super().__init__(name=name)
    self._mode = get_io_mode(source)
    # ensure targets are using the same io mode as the source
    for target in targets:
      target_mode = get_io_mode(target)
      if target_mode != self._mode:
        raise ValueError(
          f'Source is {self._mode.value}, but target is {target_mode.value}: {target}')
    self._source = source
    self._targets = targets
    self._work = False

  def _run_text(self):
    # FIXME optimize
    while self._work:
      buf = self._source.readline()
      if buf == '':
        break
      for target in self._targets:
        target.write(buf) # FIXME handle exceptions

  def _run_binary(self):
    while self._work:
      buf = self._source.read(self.buflen)
      if buf == b'':
        break
      for target in self._targets:
        target.write(buf) # FIXME handle exceptions

  def run(self):
    self._work = True
    try:
      if self._mode == IoModes.TEXT:
        self._run_text()
      elif self._mode == IoModes.BINARY:
        self._run_binary()
      else:
        raise RuntimeError(f'Invalid self._mode: {self._mode}')
    finally:
      self._work = False

  def stop(self):
    self._work = False

#####
## logging helper

class IoLogger:
  'File-like object which writes to a logger.'

  mode = 'w'

  log: Callable[[str], None]
  tag: str

  def __init__(self, logger: logging.Logger, level: int, tag: str):
    super().__init__()
    self.log = logger[level] # type: ignore
    self.tag = tag

  def write(self, buf) -> int:
    self.log(f'[{self.tag}] {buf.rstrip()}') # type: ignore
    return len(buf)

#####
## run function and context manager implementations

class Run:
  'Run commands in subprocesses.'

  context: Context

  def __init__(self):
    super().__init__()
    self.context = Context()

  def __call__(
    self,
    argv: Union[str, Sequence[str]],
    env: Optional[Mapping[str, str]] = None,
    env_replace: Optional[bool] = None,
    cwd: Optional[str] = None,
    shell: Optional[bool] = None,
    stdin: Optional[IO] = None,
    stdout: Optional[Sequence[IO]] = None,
    stderr: Optional[Sequence[IO]] = None,
    enforce: Optional[bool] = None,
    enforce_code: Optional[int] = None,
    text: Optional[bool] = None,
    encoding: Optional[str] = None,
  ) -> Result:
    'Run a command in a subprocess.'

    # allow argv to be a string or list. Popen allows strings only if shell=True
    if not shell and isinstance(argv, str):
      argv = shlex.split(argv)

    # collect arguments passed by the caller
    caller_args: Mapping[str, Any] = dict(
      env = env,
      env_replace = env_replace,
      cwd = cwd,
      shell = shell,
      stdin = stdin,
      stdout = stdout,
      stderr = stderr,
      enforce = enforce,
      enforce_code = enforce_code,
      text = text,
      encoding = encoding,
    )

    # collect arguments set by context managers
    context_args: Mapping[str, Any] = vars(self.context)

    # construct the list of arguments this call will use. prefer arguments
    # passed explicitly by the caller. use arguemnts from the context
    # when omitted by the caller.
    # FIXME pytype incorrectly reports context_args and caller_args as undefined
    args = attr({
      k: context_args[k] if caller_args[k] is None else caller_args[k] # type: ignore
      for k in context_args # type: ignore
    })

    # setup environment variables
    if args.env and not args.env_replace:
      _ = args.env
      args.env = dict(os.environ)
      args.env.update(_)

    # setup i/o
    out_buf: IO
    err_buf: IO

    if args.text:
      if not args.encoding:
        args.encoding = sys.getdefaultencoding()
      out_buf = io.StringIO()
      err_buf = io.StringIO()
    else:
      args.encoding = None
      out_buf = io.BytesIO()
      err_buf = io.BytesIO()

    stdouts = [out_buf] # list of file-like objects to receive stdout in real time
    if args.stdout:
      stdouts.extend(args.stdout)

    stderrs = [err_buf] # list of file-like objects to receive stderr in real time
    if args.stderr:
      stderrs.extend(args.stderr)

    # prepare to spawn subprocess and stdout/stderr reader threads
    proc: Optional[subprocess.Popen] = None
    threads: Sequence[Tee] = []

    try:

      # spawn process
      proc = subprocess.Popen(
        argv,
        env = args.env, 
        cwd = args.cwd,
        shell = args.shell,
        stdin = args.stdin,
        stdout = subprocess.PIPE,
        stderr = subprocess.PIPE,
        encoding = args.encoding,
      )

      # spawn stdout/stderr reader threads
      threads = [
        Tee.spawn(proc.stdout, stdouts, name=f'Tee <{argv[0]} stdout>'),
        Tee.spawn(proc.stderr, stderrs, name=f'Tee <{argv[0]} stderr>'),
      ]

      # await the process exit code while allowing execution to return to the
      # interpreter every PROCESS_POLL_INTERVAL seconds
      while True:
        try:
          code = proc.wait(PROCESS_POLL_INTERVAL)
          break # process has exited
        except subprocess.TimeoutExpired:
          continue # process is still running

      proc = None

      # join reader threads
      for thread in threads:
        while thread.is_alive():
          thread.join()
        if thread.error:
          logger.error(f'Exception from stdio thread {thread}')
          logger.error(''.join(traceback.format_exception(*thread.error)))

      threads = []

      # prepare the result
      result = Result(
        argv,
        code,
        out_buf.getvalue(),
        err_buf.getvalue(),
        self.context,
      )

      # enforce process exit code
      if args.enforce and code != args.enforce_code:
        raise Error(args.enforce_code, result)

      # done
      return result

    finally:

      # cleanup threads
      for thread in threads:
        thread.stop()
        thread.join(STDIO_JOIN_TIMEOUT)
        if thread.is_alive():
          logger.warn(f'Unable to join stdio thread: {thread}')

      # cleanup stdio buffers
      out_buf.close()
      err_buf.close()

      # cleanup proc
      if proc:
        proc.kill()

  @contextmanager
  def quash(self) -> Iterator[None]:
    'Do not enforce exit code while in this context.'

    prev = self.context.enforce
    self.context.enforce = False
    try:
      yield
    finally:
      self.context.enforce = prev

  @contextmanager
  def enforce(self, enforce_code: int = 0) -> Iterator[None]:
    'Enforce exit code `enforce_code` while in this context.'

    prev = dict(
      enforce = self.context.enforce,
      enforce_code = self.context.enforce_code,
    )
    self.context.enforce = True
    self.context.enforce_code = enforce_code
    try:
      yield
    finally:
      vars(self.context).update(prev)

  @contextmanager
  def cwd(self, cwd: str) -> Iterator[None]:
    'Run in directory `cwd` while in this context.'

    prev = self.context.cwd
    self.context.cwd = cwd
    try:
      yield
    finally:
      self.context.cwd = prev

  @contextmanager
  def shell(self) -> Iterator[None]:
    "Run all commands with the user's shell while in this context."

    prev = self.context.shell
    self.context.shell = True
    try:
      yield
    finally:
      self.context.shell = prev

  @contextmanager
  def log(self, logger: logging.Logger, log_level: int = logging.DEBUG) -> Iterator[None]:
    'Send stdout and stderr to a logger while in this context.'

    prev: Mapping[str, Optional[Sequence[IO]]] = dict(
      stdout = self.context.stdout,
      stderr = self.context.stderr,
    )
    # setup stdout
    self.context.stdout = []
    if prev['stdout'] is not None:
      self.context.stdout.extend(prev['stdout'])
    self.context.stdout.append(cast(IO, IoLogger(logger, log_level, 'stdout')))
    # setup stderr
    self.context.stderr = []
    if prev['stderr'] is not None:
      self.context.stderr.extend(prev['stderr'])
    self.context.stderr.append(cast(IO, IoLogger(logger, log_level, 'stderr')))
    try:
      yield
    finally:
      vars(self.context).update(prev)

run = Run()
