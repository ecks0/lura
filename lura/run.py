import os
import shlex
import sys
import threading
from collections.abc import Sequence
from getpass import getpass
from io import StringIO
from lura import fmt
from lura import logs
from lura.attrs import attr, ottr, wttr
from lura.io import LogWriter, Tee, flush, tee
from lura.shell import shell_path, shjoin, whoami
from lura.sudo import popen as sudo_popen
from lura.utils import scrub
from ptyprocess import PtyProcessUnicode
from subprocess import PIPE, Popen as subp_popen

log = logs.get_logger('lura.run')

class Info:
  'Base class for Error and Result.'

  members = ('args', 'argv', 'code', 'stdout', 'stderr')

  def __init__(self, *args):
    super().__init__()
    if len(args) == 1 and isinstance(args[0], Info):
      for _ in self.members:
        setattr(self, _, getattr(args[0], _))
    elif len(args) == len(self.members):
      for i in range(len(self.members)):
        setattr(self, self.members[i], args[i])
    else:
      msg = f'Invalid arguments, expected {self.members}, got {args}'
      raise ValueError(msg)

  def as_dict(self, type=ottr):
    return type(((name, getattr(self, name)) for name in self.members))

  def format(self, fmt='yaml'):
    from lura.fmt import formats
    tag = 'run.{}'.format(type(self).__name__.lower())
    return formats[fmt].dumps({tag: self.as_dict()})

  def print(self, fmt='yaml', file=None):
    file = sys.stdout if file is None else file
    file.write(self.format(fmt=fmt))
    flush(file)

  def log(self, logger, level='DEBUG', fmt='yaml'):
    log = getattr(logger, level.lower())
    for line in self.format(fmt=fmt).split('\n'):
      log(line)

class Result(Info):
  'Returned by run().'

  def __init__(self, *args):
    super().__init__(*args)

class Error(RuntimeError, Info):
  'Raised by run().'

  def __init__(self, *args):
    Info.__init__(self, *args)
    msg = f'Process exited with code {self.code}: {self.args})'
    RuntimeError.__init__(self, msg)

def _run_stdio(proc, argv, args, stdout, stderr):
  log.noise('_run_stdio()')
  out, err = StringIO(), StringIO()
  stdout.append(out)
  stderr.append(err)
  try:
    for thread in (Tee(proc.stdout, stdout), Tee(proc.stderr, stderr)):
      thread.join()
    return run.result(args, argv, proc.wait(), out.getvalue(), err.getvalue())
  finally:
    proc.kill()
    out.close()
    err.close()

def _run_popen(argv, args, env, cwd, shell, stdout, stderr, **kwargs):
  log.noise('_run_popen()')
  proc = subp_popen(
    args if shell else argv, env=env, cwd=cwd, shell=shell, stdout=PIPE,
    stderr=PIPE, text=True)
  return _run_stdio(proc, argv, args, stdout, stderr)

def _run_pty(argv, args, env, cwd, shell, stdout, **kwargs):
  log.noise('_run_pty()')
  if shell:
    argv = [run.default_shell, '-c', args]
    args = shjoin(argv)
  proc = PtyProcessUnicode.spawn(argv, env=env, cwd=cwd)
  proc_reader = attr(read=lambda: f'{proc.readline()[:-2]}\n')
  out = StringIO()
  stdout.append(out)
  try:
    try:
      tee(proc_reader, stdout)
    except EOFError:
      pass
    return run.result(args, argv, proc.wait(), out.getvalue(), '')
  finally:
    try:
      proc.kill(9)
    except Exception:
      log.exception('Unhandled exception when finally killing pty process')
    out.close()

def _run_sudo(
  argv, args, env, cwd, shell, stdout, stderr, sudo_user, sudo_group,
  sudo_password, sudo_login, sudo_timeout, **kwargs
):
  log.noise('_run_sudo()')
  proc = sudo_popen(
    args if shell else argv, env=env, cwd=cwd, shell=shell, stdout=PIPE,
    stderr=PIPE, text=True, sudo_user=sudo_user, sudo_group=sudo_group,
    sudo_password=sudo_password, sudo_login=sudo_login,
    sudo_timeout=sudo_timeout)
  return _run_stdio(proc, argv, args, stdout, stderr)

def lookup(name):
  log.noise(f'lookup({name})')
  default_value = run.defaults[name]
  context_value = run.context().get(name)
  if is_non_str_sequence(default_value):
    if context_value:
      value = []
      value.extend(default_value)
      value.extend(context_value)
      return value
    else:
      return list(default_value)
  elif context_value:
    return context_value
  else:
    return default_value

def merge_args(user_args):
  log.noise(f'merge_args()')
  stdio = ('stdout', 'stderr')
  for name in run.defaults:
    if name in stdio:
      continue
    if user_args.get(name) is None:
      user_args[name] = lookup(name)
  for name in stdio:
    user_value = user_args.get(name)
    default_value = lookup(name)
    if user_value:
      if not isinstance(user_value, Sequence):
        user_value = (user_value,)
      user_args[name] = []
      user_args[name].extend(user_value)
      user_args[name].extend(default_value)
    else:
      user_args[name] = default_value
  return attr(user_args)

def run(argv, **kwargs):
  log.noise('run()')
  kwargs = merge_args(kwargs)
  modes = ('popen', 'pty', 'sudo')
  if kwargs.mode not in modes:
    raise ValueError(f"Invalid mode '{kwargs.mode}'. Valid modes: {modes}")
  if isinstance(argv, str):
    args = argv
    argv = shlex.split(args)
  else:
    args = shjoin(argv)
  run_real = globals()[f'_run_{kwargs.mode}']
  result = run_real(argv, args, **kwargs)
  if kwargs.enforce is True and result.code != kwargs.enforce_code:
    raise run.error(result)
  return result

def is_non_str_sequence(obj):
  return not isinstance(obj, str) and isinstance(obj, Sequence)

class Context:
  'Base class for run contexts.'

  log = logs.get_logger('fuga.run.Context')

  def __init__(self, autosetvars=None):
    super().__init__()
    self.autosetvars = autosetvars
    self.context = run.context()
    self.previous = attr()
    self.name = type(self).__name__

  def _logcall(self, msg, *args, **kwargs):
    self.log.noise(f'{self.name}.{msg}', *args, **kwargs)

  def set(self, name, value, merge=True):
    'Set a context variable and save its previous value for unset().'

    self._logcall(f'set({name}, merge={merge})')
    assert(name not in self.previous)
    if is_non_str_sequence(value) and merge:
      self.previous[name] = list(self.context.setdefault(name, []))
      self.context[name].extend(value)
    else:
      self.previous[name] = self.context.get(name)
      self.context[name] = value

  def unset(self, name):
    'Restore a context variable to its original value.'

    self._logcall(f'unset({name})')
    value = self.previous[name]
    if value in (None, []):
      del self.context[name]
    elif is_non_str_sequence(value):
      self.context[name].clear()
      self.context[name].extend(value)
    else:
      self.context[name] = value
    del self.previous[name]

  def autoset(self):
    'Automatically assign context variable values from instance attributes.'

    if not self.autosetvars:
      self._logcall('autoset() nothing to set')
      return
    self._logcall('autoset()')
    for name in self.autosetvars:
      merge = True
      if not isinstance(name, str):
        name, merge = name
      self.set(name, getattr(self, name), merge)

  def autounset(self):
    'Restore all previous context variables to their original values.'

    if not self.previous:
      self._logcall('autounset() nothing to autounset')
      return
    self._logcall('autounset()')
    for name in list(self.previous):
      self.unset(name)

  def cleanup(self):
    'Cleanup any lingering values in run.context.'

    self._logcall('cleanup()')
    if not all(_ in (None, []) for _ in self.context.values()):
      self.log.info('run.context is not empty at run.Context cleanup')
      scrubbed = scrub(dict(self.context))
      msg = fmt.yaml.dumps(scrubbed)
      logs.lines(self.log.debug, msg, prefix='  ')
    self.context.clear()

  def push(self):
    'Increment the thread-global context count.'

    self._logcall('push()')
    self.context.count = self.context.setdefault('count', 0) + 1

  def pop(self):
    'Decrement the thread-global context count.'

    self._logcall('pop()')
    self.context.count -= 1
    if self.context.count == 0:
      del self.context['count']
      self.cleanup()

  def __enter__(self):
    self._logcall('__enter__()')
    self.push()
    self.autoset()

  def __exit__(self, *exc_info):
    self._logcall('__exit__()')
    self.autounset()
    self.pop()

class Enforce(Context):

  def __init__(self, enforce_code):
    assert(isinstance(enforce_code, int))
    autosetvars = ('enforce_code', 'enforce')
    super().__init__(autosetvars)
    self.enforce_code = enforce_code
    self.enforce = True

class Quash(Context):

  def __init__(self):
    autosetvars = ('enforce')
    super().__init__(autosetvars)
    self.enforce = False

class Stdio(Context):

  def __init__(self, stdout, stderr=[], excl=False):
    autosetvars = [('stdio', not excl)]
    if stderr or excl:
      autosetvars.append(('stderr', not excl))
    super().__init__(autosetvars)
    self.stdout = stdout if isinstance(stdout, Sequence) else (stdout,)
    self.stderr = stderr if isinstance(stderr, Sequence) else (stderr,)

class Log(Stdio):

  def __init__(self, log, level='DEBUG'):
    super().__init__(
      LogWriter(log, level, '[stdout]'), LogWriter(log, level, '[stderr]'))

class Sudo(Context):

  def __init__(
    self, password=None, user=None, group=None, login=None, timeout=None
  ):
    autosetvars = (
      'sudo_user', 'sudo_password', 'sudo_group', 'sudo_login', 'sudo_timeout',
      'mode')
    super().__init__(autosetvars)
    self.sudo_user = user
    self.sudo_password = password
    self.sudo_group = group
    self.sudo_login = login
    self.sudo_timeout = timeout
    self.mode = 'sudo'

def getsudopass(prompt=None):
  log.noise('getsudopass()')
  return getpass(getsudopass.prompt if prompt is None else prompt)

getsudopass.prompt = f'[sudo] password for {whoami()}: '

def run_popen(argv, **kwargs):
  log.noise('run_popen()')
  kwargs['mode'] = 'popen'
  return run(argv, **kwargs)

def run_pty(argv, **kwargs):
  log.noise('run_pty()')
  kwargs['mode'] = 'pty'
  return run(argv, **kwargs)

def run_sudo(argv, **kwargs):
  log.noise('run_sudo()')
  kwargs['mode'] = 'sudo'
  return run(argv, **kwargs)

# modes
run.popen = run_popen
run.pty = run_pty
run.sudo = run_sudo

# results
run.result = Result
run.error = Error

# context managers
run.Enforce = Enforce
run.Quash = Quash
run.Stdio = Stdio
run.Log = Log
run.Sudo = Sudo

# misc
run.getsudopass = getsudopass
run.default_shell = shell_path()

# defaults
run.defaults = attr()
run.defaults.mode = 'popen'
run.defaults.env = None
run.defaults.cwd = None
run.defaults.shell = None
run.defaults.stdout = []
run.defaults.stderr = []
run.defaults.enforce_code = 0
run.defaults.enforce = True
run.defaults.sudo_user = None
run.defaults.sudo_group = None
run.defaults.sudo_password = None
run.defaults.sudo_login = None
run.defaults.sudo_timeout = 3

# context manager variable storage
run.context = lambda: wttr(run.context.tls.__dict__)
run.context.tls = threading.local()
