import io
import os
import shlex
import subprocess as subp
import sys
import threading
from contextlib import contextmanager
from deepmerge import always_merger
from lura import LuraError
from lura import formats
from lura import logs
from lura import threads
from lura.attrs import attr
from lura.attrs import ottr
from lura.shell import shell_path
from lura.shell import shjoin
from lura.sudo import SudoHelper

log = logs.get_logger(__name__)

merge = always_merger.merge

def tee(source, targets, cond=lambda: True):
  'Read from one source and write to many targets.'

  while cond():
    line = source.readline()
    if line == '':
      break
    for target in targets:
      target.write(line)

class Tee(threads.Thread):
  'Read from one source and write to many targets in a thread.'

  def __init__(self, source, targets):
    super().__init__(target=self.work, name='Tee')
    self.source = source
    self.targets = targets
    self._work = False

  def work(self):
    self._work = True
    tee(self.source, self.targets, lambda: self._work is True)

  def stop(self):
    self._work = False

class LogWriter:
  'A file-like object which logs data written to it.'

  # this is used to implement the `run.log(...)` context manager

  def __init__(self, logger, level, tag):
    super().__init__()
    self.log = getattr(logger, logs.get_level_name(level).lower())
    self.tag = tag

  def write(self, line):
    self.log(f'[{self.tag}] {line.rstrip()}')

class Result:
  'The value returned by `run()`.'

  #order = ('context', 'args', 'argv', 'code', 'stdout', 'stderr')
  order = ('args', 'argv', 'code', 'stdout', 'stderr')

  def __init__(self, context, code, stdout, stderr):
    super().__init__()
    self.args = context.args
    self.argv = context.argv
    self.code = code
    self.stdout = stdout
    self.stderr = stderr
    self.context = context
    context.pop('args')
    context.pop('argv')
    if context.sudo_password:
      context.sudo_password = '<scrubbed>'

  def as_dict(self):
    return ottr((_, getattr(self, _)) for _ in self.order)

  def format(self, fmt='yaml'):
    tag = 'run.{}'.format(type(self).__name__.lower())
    return formats.for_ext(fmt).dumps({tag: self.as_dict()})

  def print(self, fmt='yaml', file=None):
    file = sys.stdout if file is None else file
    file.write(self.format(fmt=fmt))

class Error(LuraError):
  'The error raised by `run()` when a process exits with the wrong code.'

  def __init__(self, result):
    msg = 'Process expected exit code {} but received code {}{}{}'.format(
      result.context.enforce_code, result.code, os.linesep, result.format())
    super().__init__(msg)
    self.result = result

class Run(threading.local):
  'The implementation of `run()`.'

  default_shell_path = shell_path()

  # kwargs that we accept
  _kwargs = (
    'pty', 'env', 'env_replace', 'cwd', 'shell', 'stdin', 'stdout', 'stderr',
    'enforce', 'enforce_code', 'encoding', 'sudo', 'sudo_user', 'sudo_group',
    'sudo_password', 'sudo_login'
  )

  # default kwarg values
  defaults = dict(
    pty           = False,
    env           = None,
    env_replace   = False,
    cwd           = None,
    shell         = False,
    stdin         = None,
    stdout        = [],
    stderr        = [],
    enforce       = True,
    enforce_code  = 0,
    encoding      = sys.getdefaultencoding(),
    sudo          = False,
    sudo_user     = None,
    sudo_group    = None,
    sudo_password = None,
    sudo_login    = False,
  )

  def __init__(self):
    super().__init__()
    # context managers set their values here
    self.context = {}

  def _subprocess(self, ctx):
    'Run with `subprocess.Popen`.'

    argv = ctx.args if ctx.shell else ctx.argv
    proc = subp.Popen(
      argv, env=ctx.env, cwd=ctx.cwd, shell=ctx.shell, stdout=subp.PIPE,
      stderr=subp.PIPE, stdin=ctx.stdin, encoding=ctx.encoding)
    if ctx.sudo:
      ctx.sudo_helper.wait()
    outbuf, errbuf = io.StringIO(), io.StringIO()
    stdout = [outbuf] + ctx.stdout
    stderr = [errbuf] + ctx.stderr
    threads = (Tee.spawn(proc.stdout, stdout), Tee.spawn(proc.stderr, stderr))
    try:
      return self.Result(ctx, proc.wait(), outbuf.getvalue(), errbuf.getvalue())
    finally:
      outbuf.close()
      errbuf.close()
      if ctx.sudo:
        ctx.pop('sudo_helper')
      for thread in threads:
        thread.stop()
        thread.join()
      proc.kill()

  def _ptyprocess(self, ctx):
    'Run with `PtyProcessUnicode`.'

    if ctx.stdin:
      raise NotImplementedError('stdin not implemented for pty processes')
    if shell:
      ctx.argv = [self.default_shell_path, '-c', ctx.args]
      ctx.args = shjoin(ctx.argv)
    proc = PtyProcessUnicode.spawn(argv, env=ctx.env, cwd=ctx.cwd)
    if ctx.sudo:
      ctx.sudo_helper.wait()
    outbuf = io.StringIO()
    stdout = [outbuf] + ctx.stdout
    reader = attr(readline=lambda: f'{proc.readline()[:-2]}{os.linesep}')
    try:
      tee(reader, stdout)
    except EOFError:
      pass
    try:
      return self.Result(ctx, proc.wait(), outbuf.getvalue(), '')
    finally:
      outbuf.close()
      if ctx.sudo:
        ctx.pop('sudo_helper')
      try:
        proc.kill(9)
      except Exception:
        log.debug(
          'Unhandled exception while killing pty process', exc_info=True)

  def _check_args(self, kwargs):
    'Validate arg names in `self.defaults`, `self.context`, and `kwargs`.'

    def check_args(name, bundle):
      for arg in bundle:
        if arg not in self._kwargs:
          raise ValueError(f'Unknown argument in {name}: {arg}={bundle[arg]}')
    check_args('defaults', self.defaults)
    check_args('context', self.context)
    check_args('kwargs', kwargs)

  def _setup_args_argv(self, ctx, argv):
    'ctx.args is always a string, ctx.argv is always a list.'

    if isinstance(argv, str):
      ctx.args = argv
      ctx.argv = shlex.split(argv)
    else:
      ctx.args = shjoin(argv)
      ctx.argv = argv

  def run(self, argv, **kwargs):
    'Entry point for `run()`.'

    self._check_args(kwargs)
    ctx = attr(merge(self.defaults, merge(self.context, kwargs)))
    if ctx.env is None:
      ctx.env = {}
    if not ctx.env_replace:
      env = {}
      env.update(os.environ)
      env.update(ctx.env)
      ctx.env = env
    if ctx.sudo:
      ctx.sudo_helper = SudoHelper(
        user=ctx.sudo_user, group=ctx.sudo_group, password=ctx.sudo_password,
        login=ctx.sudo_login)
      argv, askpass_path = ctx.sudo_helper.prepare(argv)
      if askpass_path:
        ctx.env['SUDO_ASKPASS'] = askpass_path
    self._setup_args_argv(ctx, argv)
    if ctx.get('pty'):
      result = self._ptyprocess(ctx)
    else:
      result = self._subprocess(ctx)
    if ctx.enforce and result.code != ctx.enforce_code:
      raise self.Error(result)
    return result

  __call__ = run

  @contextmanager
  def quash(self):
    'Do not enforce exit code while in this context.'

    old = self.context
    new = {'enforce': False}
    self.context = merge(old, new)
    try:
      yield self
    finally:
      self.context = old

  @contextmanager
  def enforce(self, enforce_code=0):
    'Enforce the given exit code while in this context.'

    old = self.context
    new = {'enforce': True, 'enforce_code': enforce_code}
    self.context = merge(old, new)
    try:
      yield self
    finally:
      self.context = old

  @contextmanager
  def cwd(self, cwd):
    'Run in directory `cwd` while in this context.'

    old = self.context
    new = {'cwd': cwd}
    self.context = merge(old, new)
    try:
      yield self
    finally:
      self.context = old

  @contextmanager
  def sudo(
    self, sudo_user=None, sudo_group=None, sudo_password=None, sudo_login=None
  ):
    'Run with sudo while in this context.'

    old = self.context
    new = dict(
      sudo = True,
      sudo_user = sudo_user,
      sudo_group = sudo_group,
      sudo_password = sudo_password,
      sudo_login = sudo_login,
    )
    self.context = merge(old, new)
    try:
      yield self
    finally:
      self.context = old

  @contextmanager
  def log(self, logger, log_level=log.DEBUG):
    'Send stdout and stderr to a logger while in this context.'

    old = self.context
    new = {
      'stdout': [LogWriter(logger, log_level, 'out')],
      'stderr': [LogWriter(logger, log_level, 'err')],
    }
    self.context = merge(old, new)
    try:
      yield self
    finally:
      self.context = old

Run.Error = Error
Run.Result = Result

run = Run()
