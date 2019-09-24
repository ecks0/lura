'SSH client with sudo support.'

import fabric
import sys
from invoke import Responder
from lura import logs
from subprocess import list2cmdline as shjoin

log = logs.get_logger(__name__)

class Client:

  log_level = log.DEBUG

  def __init__(
    self, host, port=22, user=None, password=None, key_file=None,
    passphrase=None, timeout=60.0, auth_timeout=60.0, sudo_password=None
  ):
    # FIXME accept key data from buffer
    super().__init__()
    self.host = host
    self.port = port
    self.user = user
    self.timeout = timeout
    self.conn_kwargs = {
      'key_filename': key_file,
      'passphrase': passphrase,
      'auth_timeout': auth_timeout,
    }
    self.sudo_password = sudo_password
    self.conn = None

  def __enter__(self):
    self.connect()
    return self

  def __exit__(self, *exc_info):
    self.close()

  def _log(self, msg):
    _log = getattr(log, logs.get_level_name(self.log_level).lower())
    _log(f'[{self.host}] {msg}')

  def connect(self):
    self._log('Connecting')
    overrides = {}
    if self.sudo_password:
      overrides['sudo'] = {'password': self.sudo_password}
    config = fabric.Config(overrides=overrides)
    self.conn = fabric.Connection(
      host=self.host, user=self.user, port=self.port,
      connect_timeout=self.timeout, connect_kwargs=self.conn_kwargs,
      config=config)
    self._log('Connected')

  def is_closed(self):
    return self.conn is None

  def close(self):
    try:
      self._log('Closing')
      self.conn.close()
    except Exception:
      log.exception('Unhandled exceptionat close()')
    self.conn = None
    self._log('Closed')
    self.host = None

  disconnect = close

  def put(self, src, dst):
    self._log(f'put {src} -> {dst}')
    self.conn.put(src, remote=dst)

  def get(self, dst, src):
    self._log(f'get {dst} -> {src}')
    self.conn.get(src, local=dst)

  def run(
    self, argv, shell=False, pty=False, env={}, replace_env=False,
    encoding=None, stdin=None, stdout=None, stderr=None, enforce=True
  ):
    if not isinstance(argv, str):
      argv = shjoin(argv)
    self._log(f'run {argv}')
    return self.conn.run(
      argv, shell=shell, pty=pty, env=env, replace_env=replace_env,
      encoding=encoding, in_stream=stdin, out_stream=stdout,
      err_stream=stderr, warn=not enforce, hide=True)

  def sudo(
    self, argv, shell=False, pty=False, env={}, replace_env=False,
    encoding=None, stdin=None, stdout=None, stderr=None, enforce=True,
    user=None
  ):
    if not isinstance(argv, str):
      argv = shjoin(argv)
    self._log(f'sudo {argv}')
    return self.conn.sudo(
      argv, shell=shell, pty=pty, env=env, replace_env=replace_env,
      encoding=encoding, in_stream=stdin, out_stream=stdout,
      err_stream=stderr, warn=not enforce, hide=True,
      user=user)

  def forward(self, lport, rport, lhost=None):
    return self.conn.forward_local(lport, rport, lhost)
