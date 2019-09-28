import io
import os
import shlex
import subprocess as subp
import sys
import threading
from collections import MutableSequence
from contextlib import contextmanager
from deepmerge import always_merger
from lura import LuraError
from lura import formats
from lura import logs
from lura import threads
from lura.attrs import attr
from lura.attrs import deepcopy
from lura.attrs import ottr
from lura.sudo import SudoHelper
from lura.sudo import shell_path
from types import GeneratorType

log = logs.get_logger(__name__)

merge = always_merger.merge
shjoin = subp.list2cmdline

def tee(source, targets, cond=lambda: True):
  '`readline` from one source and `write` to many targets.'

  while cond():
    line = source.readline()
    if line == '':
      break
    for target in targets:
      target.write(line)

class Tee(threads.Thread):
  '`readline` from one source and `write` to many targets in a thread.'

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
    self.log = logger[level]
    self.tag = tag

  def write(self, line):
    self.log(f'[{self.tag}] {line.rstrip()}')

class Result:
  'The value returned by `run()`.'

  as_dict_members = ('args', 'argv', 'code', 'stdout', 'stderr')

  def __init__(self, context, code, stdout, stderr):
    super().__init__()
    self.args = context.args
    self.argv = context.argv
    self.code = code
    self.stdout = stdout
    self.stderr = stderr
    self.context = context
    del context['args']
    del context['argv']
    if context.sudo_password:
      context.sudo_password = '<scrubbed>'

  def as_dict(self):
    return ottr((_, getattr(self, _)) for _ in self.as_dict_members)

  def format(self, fmt='yaml'):
    tag = 'run.{}'.format(type(self).__name__.lower())
    return formats.for_ext(fmt).dumps({tag: self.as_dict()})

  def print(self, fmt='yaml', file=None):
    file = file or sys.stdout
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

  # kwargs that we accept
  _kwargs = (
    'pty', 'env', 'env_replace', 'cwd', 'shell', 'stdin', 'stdout', 'stderr',
    'encoding', 'enforce', 'enforce_code', 'sudo', 'sudo_user', 'sudo_group',
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
    encoding      = sys.getdefaultencoding(),
    enforce       = True,
    enforce_code  = 0,
    sudo          = False,
    sudo_user     = None,
    sudo_group    = None,
    sudo_password = None,
    sudo_login    = False,
  )

  default_shell = shell_path()

  # for stdio threads
  stdio_join_timeout = 0.5

  def __init__(self):
    super().__init__()
    # context managers set their values here
    self.context = {}

  def _subprocess(self, ctx):
    'Run with `subprocess.Popen`.'

    outbuf, errbuf = io.StringIO(), io.StringIO()
    stdout = [outbuf] + ctx.stdout
    stderr = [errbuf] + ctx.stderr
    argv = ctx.args if ctx.shell else ctx.argv
    proc = None
    threads = ()
    try:
      proc = subp.Popen(
        argv, env=ctx.env, cwd=ctx.cwd, shell=ctx.shell, stdout=subp.PIPE,
        stderr=subp.PIPE, stdin=ctx.stdin, encoding=ctx.encoding)
      if ctx.sudo:
        ctx.sudo_helper.wait()
      threads = (Tee.spawn(proc.stdout, stdout), Tee.spawn(proc.stderr, stderr))
      code = proc.wait()
      for thread in threads:
        thread.join()
      proc = None
      threads = ()
      return self.Result(ctx, code, outbuf.getvalue(), errbuf.getvalue())
    finally:
      for thread in threads:
        thread.stop()
        thread.join(self.stdio_join_timeout)
        if thread.is_alive():
          log.debug(f'Failed joining tee thread: {thread}')
      outbuf.close()
      errbuf.close()
      if proc:
        proc.kill()

  def _ptyprocess(self, ctx):
    'Run with `PtyProcessUnicode`.'

    if ctx.stdin:
      raise NotImplementedError('stdin not implemented for pty processes')
    if ctx.shell:
      ctx.argv = [self.default_shell, '-c', ctx.args]
      ctx.args = shjoin(ctx.argv)
    outbuf = io.StringIO()
    stdout = [outbuf] + ctx.stdout
    proc = None
    try:
      proc = PtyProcessUnicode.spawn(argv, env=ctx.env, cwd=ctx.cwd)
      if ctx.sudo:
        ctx.sudo_helper.wait()
      reader = attr(readline=lambda: f'{proc.readline()[:-2]}{os.linesep}')
      try:
        tee(reader, stdout)
      except EOFError:
        pass
      code = proc.wait()
      proc = None
      return self.Result(ctx, code, outbuf.getvalue(), '')
    finally:
      outbuf.close()
      if proc:
        try:
          proc.kill(9)
        except Exception:
          log.debug('Failed killing pty process', exc_info=True)

  def _check_args(self, kwargs):
    'Validate arg names in `self.defaults`, `self.context`, and `kwargs`.'

    def check_args(name, bundle):
      for arg in bundle:
        if arg not in self._kwargs:
          raise ValueError(f'Unknown argument in {name}: {arg}={bundle[arg]}')
    check_args('defaults', self.defaults)
    check_args('context', self.context)
    check_args('kwargs', kwargs)

  def _build_context(self, kwargs):
    defaults = deepcopy(self.defaults)
    context = deepcopy(self.context)
    return merge(defaults, merge(context, kwargs))

  def _env_setup(self, ctx):
    'Setup the environment the process will run in.'

    if ctx.env is None:
      ctx.env = {}
    if not ctx.env_replace:
      env = {}
      env.update(os.environ)
      env.update(ctx.env)
      ctx.env = env

  def _sudo_setup(self, ctx, argv):
    'Setup sudo, returning the new sudo argv.'

    ctx.sudo_helper = SudoHelper(
      user=ctx.sudo_user, group=ctx.sudo_group, password=ctx.sudo_password,
      login=ctx.sudo_login)
    argv, askpass_path = ctx.sudo_helper.prepare(argv)
    if askpass_path:
      ctx.env['SUDO_ASKPASS'] = askpass_path
    return argv

  def _sudo_cleanup(self, ctx):
    ctx.sudo_helper.cleanup()
    del ctx['sudo_helper']

  def _argv_setup(self, ctx, argv):
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
    ctx = self._build_context(kwargs)
    self._env_setup(ctx)
    if ctx.sudo:
      argv = self._sudo_setup(ctx, argv)
    try:
      self._argv_setup(ctx, argv)
      if ctx.pty:
        result = self._ptyprocess(ctx)
      else:
        result = self._subprocess(ctx)
      if ctx.enforce and result.code != ctx.enforce_code:
        raise self.Error(result)
      return result
    finally:
      if ctx.sudo:
        self._sudo_cleanup(ctx)

  __call__ = run

  @contextmanager
  def quash(self):
    'Do not enforce exit code while in this context.'

    old = self.context
    new = {'enforce': False}
    self.context = merge(deepcopy(old), new)
    try:
      yield
    finally:
      self.context = old

  @contextmanager
  def enforce(self, enforce_code=0):
    'Enforce exit code `enforce_code` while in this context.'

    old = self.context
    new = {'enforce': True, 'enforce_code': enforce_code}
    self.context = merge(deepcopy(old), new)
    try:
      yield
    finally:
      self.context = old

  @contextmanager
  def cwd(self, cwd):
    'Run in directory `cwd` while in this context.'

    old = self.context
    new = {'cwd': cwd}
    self.context = merge(deepcopy(old), new)
    try:
      yield
    finally:
      self.context = old

  @contextmanager
  def shell(self):
    "Run all commands with the user's shell while in this context."

    old = self.context
    new = {'shell': True}
    self.context = merge(deepcopy(old), new)
    try:
      yield
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
    self.context = merge(deepcopy(old), new)
    try:
      yield
    finally:
      self.context = old

  @contextmanager
  def std(self, stdout=None, stderr=None):
    '''
    Send stdout and/or stderr to the given file objects or lists of file
    objects while in this context.
    '''

    if stdout:
      if isinstance(stdout, (Sequence, GeneratorType)):
        stdout = list(stdout)
      else:
        stdout = [stdout]
    else:
      stdout = []
    if stderr:
      if isinstance(stderr, (Sequence, GeneratorType)):
        stderr = list(stderr)
      else:
        stderr = [stderr]
    else:
      stderr = []
    old = self.context
    new = {'stdout': stdout, 'stderr': stderr}
    self.context = merge(deepcopy(old), new)
    try:
      yield
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
    self.context = merge(deepcopy(old), new)
    try:
      yield
    finally:
      self.context = old

Run.Error = Error
Run.Result = Result

run = Run()
