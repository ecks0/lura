import click
import os
import sys
import subprocess as subp
import time
import threading
from lura import logs
from lura.crypto import decrypt
from lura.io import mkfifo, slurp, touch
from lura.shell import shell_path, shjoin
from tempfile import TemporaryDirectory

class TimeoutExpired(RuntimeError):

  def __init__(self, sudo):
    self.sudo_argv = shjoin(sudo._sudo_argv())
    self.askpass_argv = sudo._askpass_argv()
    msg = f'Timed out waiting for sudo: {self.sudo_argv}'
    super().__init__(msg)

class Sudo:

  log = logs.get_logger(f'{__name__}.Sudo')
  shell = shell_path()

  TimeoutExpired = TimeoutExpired

  def __init__(self):
    self.tls = threading.local()

  def _command_argv(self):
    return ' '.join((
      shjoin(['touch', self.tls.ok_path]),
      '&& exec',
      shjoin(self.tls.argv),
    ))

  def _sudo_argv(self):
    tls = self.tls
    sudo_argv = f'sudo -A -u {tls.user}'.split()
    if tls.group is not None:
      sudo_argv += ['-g', tls.group]
    if tls.login:
      sudo_argv.append('-i')
    sudo_argv += [self.shell, '-c', self._command_argv()]
    return sudo_argv

  def _askpass_argv(self):
    return shjoin([
      sys.executable,
      '-m',
      __name__,
      'askpass',
      self.tls.fifo_path,
      str(float(self.tls.timeout)),
    ])

  def _check_ok(self):
    return os.path.isfile(self.tls.ok_path)

  def _make_fifo(self):
    mkfifo(self.tls.fifo_path)

  def _open_fifo(self):
    tls = self.tls
    try:
      tls.fifo = os.open(tls.fifo_path, os.O_NONBLOCK | os.O_WRONLY)
      return True
    except OSError:
      return False

  def _write_fifo(self, timeout):
    tls = self.tls
    fifo = tls.fifo
    sleep_interval = tls.sleep_interval
    password = tls.password.encode()
    i = 0
    end = len(password)
    start = time.time()
    elapsed = lambda: time.time() - start
    while True:
      try:
        i += os.write(fifo, password[i:])
        if i == end:
          return True
      except BlockingIOError:
        pass
      if self._check_ok():
        return True
      if timeout < elapsed():
        raise TimeoutExpired(self)
      time.sleep(sleep_interval)

  def _close_fifo(self):
    try:
      os.close(self.tls.fifo)
    except Exception:
      self.log.exception('Error while closing pipe (write) to sudo askpass')
    self.tls.fifo = None

  def _wait_for_sudo(self):
    tls = self.tls
    timeout = tls.timeout
    sleep_interval = tls.sleep_interval
    ok_path = tls.ok_path
    start = time.time()
    elapsed = lambda: time.time() - start
    while True:
      if self._open_fifo():
        try:
          if self._write_fifo(timeout - elapsed()):
            break
        finally:
          self._close_fifo()
      if self._check_ok():
        return True
      if timeout < elapsed():
        raise TimeoutExpired(self)
      time.sleep(sleep_interval)
    while True:
      if not os.path.isfile(ok_path):
        if timeout < elapsed():
          raise TimeoutExpired(self)
        time.sleep(sleep_interval)

  def _make_askpass(self):
    askpass_path = self.tls.askpass_path
    with open(askpass_path, 'w') as fd:
      fd.write(f'#!{self.shell}\nexec {self._askpass_argv()}\n')
    os.chmod(askpass_path, 0o700)

  def _reset(self):
    tls = self.tls
    try:
      tls.state_dir_context.__exit__(None, None, None)
    except Exception:
      self.log.exception('Exception while deleting sudo state temp dir')
    for _ in list(tls.__dict__.keys()):
      delattr(tls, _)

  def _popen(self):
    tls = self.tls
    tls.env['SUDO_ASKPASS'] = tls.askpass_path
    self._make_fifo()
    self._make_askpass()
    process = subp.Popen(
      self._sudo_argv(), env=tls.env, stdin=tls.stdin, stdout=tls.stdout,
      stderr=tls.stderr
    )
    if not self._wait_for_sudo():
      process.kill()
      raise RuntimeError('Timed out waiting for sudo')
    return process

  def popen(
    self,
    argv,
    env = None,
    stdout = None,
    stderr = None,
    stdin = None,
    user = None,
    group = None,
    login = None,
    password = None,
    timeout = None,
    sleep_interval = None,
  ):
    try:
      tls = self.tls
      tls.state_dir_context = TemporaryDirectory()
      tls.state_dir = tls.state_dir_context.__enter__()
      tls.argv = argv
      tls.env = {} if env is None else env
      tls.stdin = stdin
      tls.stdout = stdout
      tls.stderr = stderr
      tls.user = 'root' if user is None else user
      tls.group = group
      tls.login = login
      tls.password = password
      tls.timeout = 5 if timeout is None else timeout
      tls.sleep_interval = 0.1 if sleep_interval is None else sleep_interval
      tls.askpass_path = os.path.join(tls.state_dir, 'sudo_askpass')
      tls.fifo_path = os.path.join(tls.state_dir, 'sudo_askpass_pipe')
      tls.ok_path = os.path.join(tls.state_dir, 'sudo_ok')
      tls.sudo_ok = False
      tls.fifo = None
      return self._popen()
    finally:
      self._reset()

popen = Sudo().popen

@click.group()
def _cli():
  pass

@_cli.command('sudo')
@click.option('-u', '--user', help='Target user.')
@click.option('-g', '--group', help='Target group.')
@click.option('-i', '--login', help="Run target user's shell.")
@click.argument('argv', nargs=-1)
def _sudo(user, group, login, argv):
  from lura.sudo import popen
  file = os.environ['SUDO_FILE']
  key = os.environ['SUDO_KEY']
  ok = os.environ.get('SUDO_OK')
  if ok:
    del os.environ['SUDO_OK']
  password = decrypt(slurp(file, 'rb'), key.encode()).decode()
  #os.unlink(file)
  del os.environ['SUDO_FILE']
  del os.environ['SUDO_KEY']
  process = popen(
    argv,
    user = user,
    group = group,
    login = login,
    password = password,
    stdin = sys.stdin,
    stdout = sys.stdout,
    stderr = sys.stderr,
  )
  if ok:
    touch(ok)
  code = process.wait()
  sys.exit(code)

@_cli.command('askpass')
@click.argument('fifo')
@click.argument('timeout', type=float)
def _askpass(fifo, timeout):
  def on_timeout():
    try:
      raise RuntimeError(f'Timed out reading become password from fifo: {fifo}')
    except RuntimeError:
      traceback.print_exc()
    os._exit(1)
  mkfifo(fifo)
  threading.Timer(timeout, on_timeout).start()
  password = slurp(fifo)
  sys.stdout.write(password)
  sys.stdout.flush()
  os._exit(0)

if __name__ == '__main__':
  _cli()
