import os
import shlex
import shutil
import subprocess as subp
import sys
from lura import LuraError
from lura.plates import jinja2
from lura.time import Timer
from tempfile import mkdtemp
from time import sleep

shjoin = subp.list2cmdline

def shell_path():
  proc = subp.Popen(
    'echo $SHELL', shell=True, stdout=subp.PIPE,
    encoding=sys.getdefaultencoding())
  with proc:
    proc.wait()
    return proc.stdout.read().rstrip()

class SudoTimeout(LuraError):
  def __init__(self, *args, **kwargs):
    super().__init__(*args, *kwargs)

class SudoHelper:
  '''
  A helper for implementing `popen()`-like or `run()`-like interfaces that
  support invoking commands with sudo. See the `popen()` function in this
  module for a usage example.
  '''

  shell = shell_path()
  timeout = 7.0
  sleep_interval = 0.1

  def __init__(self, password, user=None, group=None, login=None):
    super().__init__()
    self.user = user
    self.group = group
    self.password = password
    self.login = login
    self.timer = None
    self.temp_dir = None
    self.ok_path = None
    self.fifo_path = None
    self.askpass_path = None
    self.fifo = None

  @property
  def _timed_out(self):
    return self.timer.time > self.timeout

  def _update_argv(self, argv):
    argv_is_str = True
    if not isinstance(argv, str):
      argv_is_str = False
      argv = shjoin(argv)
    user_argv = argv
    argv = ['sudo']
    if self.password:
      argv.append('-A')
    if self.user:
      argv.extend(('-u', self.user))
    if self.group:
      argv.extend(('-g', self.group))
    if self.login:
      argv.append('-i')
    argv.extend((self.shell, '-c'))
    argv.append(f'touch {shlex.quote(self.ok_path)} && {user_argv}')
    return shjoin(argv) if argv_is_str else argv

  def _askpass_create(self):
    env = self.__dict__.copy()
    env['shell'] = self.shell
    env['quote'] = shlex.quote
    jinja2.expandsf(env, self._askpass_tmpl, self.askpass_path)
    os.chmod(self.askpass_path, 0o700)

  def _check_for_ok(self):
    return os.path.isfile(self.ok_path)

  def _fifo_create(self):
    os.mkfifo(self.fifo_path)
    os.chmod(self.fifo_path, 0o600)

  def _fifo_open(self):
    while not self._timed_out:
      if self._check_for_ok():
        return
      try:
        self.fifo = os.open(self.fifo_path, os.O_NONBLOCK | os.O_WRONLY)
        return
      except OSError:
        pass
      sleep(self.sleep_interval)
    else:
      raise SudoTimeout('Timeout opening sudo fifo')

  def _fifo_write(self):
    if self._check_for_ok():
      return
    password = self.password.encode()
    pos = 0
    end = len(password)
    while not self._timed_out:
      try:
        pos += os.write(self.fifo, password[pos:])
        if pos == end:
          return
        continue
      except BlockingIOError:
        pass
      sleep(self.sleep_interval)
    else:
      raise SudoTimeout('Timeout writing sudo fifo')

  def _fifo_close(self):
    if self.fifo is not None:
      os.close(self.fifo)
      self.fifo = None

  def _handle_fifo(self):
    self._fifo_open()
    try:
      self._fifo_write()
    finally:
      self._fifo_close()

  def _await_ok(self):
    while not self._timed_out:
      if self._check_for_ok():
        return
      else:
        sleep(self.sleep_interval)
    else:
      raise SudoTimeout('Timeout awaiting sudo ok (incorrect password?)')

  def prepare(self, argv):
    if self.ok_path is not None:
      self.cleanup()
    self.temp_dir = mkdtemp()
    self.ok_path = os.path.join(self.temp_dir, 'ok')
    argv = self._update_argv(argv)
    if self.password:
      self.fifo_path = os.path.join(self.temp_dir, 'fifo')
      self.askpass_path = os.path.join(self.temp_dir, 'askpass')
      self._fifo_create()
      self._askpass_create()
    return argv, self.askpass_path

  def wait(self):
    if self.ok_path is None:
      raise ValueError(f'prepare() must be called before wait()')
    try:
      if self._check_for_ok():
        return
      self.timer = Timer(start=True)
      if self.password:
        self._handle_fifo()
      self._await_ok()
    finally:
      self.cleanup()

  def cleanup(self):
    if self.temp_dir and os.path.isdir(self.temp_dir):
      shutil.rmtree(self.temp_dir)
    self.timer = None
    self.temp_dir = None
    self.fifo_path = None
    self.ok_path = None
    self.askpass_path = None

SudoHelper._askpass_tmpl = '''#!{{ quote(shell) }}
cat < {{ quote(fifo_path) }}
'''

def popen(
  argv, *args, sudo_user=None, sudo_group=None, sudo_password=None,
  sudo_login=None, env=None, **kwargs
):
  sudo_helper = SudoHelper(
    user=sudo_user, group=sudo_group, password=sudo_password, login=sudo_login)
  argv, askpass_path = sudo_helper.prepare(argv)
  try:
    if askpass_path:
      if env is None:
        env = dict(os.environ)
      env['SUDO_ASKPASS'] = askpass_path
    proc = subp.Popen(argv, *args, env=env, **kwargs)
    sudo_helper.wait()
    return proc
  finally:
    sudo_helper.cleanup()
