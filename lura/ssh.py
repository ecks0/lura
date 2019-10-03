'Ssh client with sudo support.'

import fabric
import os
import sys
from invoke import Responder
from lura import logs
from subprocess import list2cmdline as shjoin

logger = logs.get_logger(__name__)

class Client:

  log_level = logger.DEBUG

  def __init__(
    self, host, port=22, user=None, password=None, key_file=None,
    passphrase=None, timeout=60.0, auth_timeout=60.0, sudo_password=None
  ):
    # FIXME accept key data from buffer
    super().__init__()
    self._host = host
    self._port = port
    self._user = user
    self._timeout = timeout
    self._conn_kwargs = {
      'key_filename': key_file,
      'passphrase': passphrase,
      'auth_timeout': auth_timeout,
    }
    self._sudo_password = sudo_password
    self._conn = None

  def __del__(self):
    self.close()

  def __enter__(self):
    self.connect()
    return self

  def __exit__(self, *exc_info):
    self.close()

  def _connect(self):
    log = logger[self.log_level]
    log(f'[{self._host}] Connecting')
    overrides = {}
    if self._sudo_password:
      overrides['sudo'] = {'password': self._sudo_password}
    config = fabric.Config(overrides=overrides)
    self._conn = fabric.Connection(
      host=self._host, user=self._user, port=self._port,
      connect_timeout=self._timeout, connect_kwargs=self._conn_kwargs,
      config=config)
    log(f'[{self._host}] Connected')

  def connect(self):
    if self._conn is None:
      self._connect()

  def is_connected(self):
    return self._conn is not None

  def is_closed(self):
    return self._conn is None

  def _close(self):
    log = logger[self.log_level]
    log(f'[{self._host}] Closing')
    try:
      self._conn.close()
    finally:
      self._conn = None
      log(f'[{self._host}] Closed')
      self._host = None

  def close(self):
    if self._conn is not None:
      self._close()

  def put(self, src, dst):
    log = logger[self.log_level]
    self.connect()
    msg = os.linesep.join([
      f'[{self._host}] put:',
      f'[{self._host}]   src: {src}',
      f'[{self._host}]   dst: {dst}',
    ])
    log(msg)
    self._conn.put(src, remote=dst)

  def get(self, src, dst):
    log = logger[self.log_level]
    self.connect()
    msg = os.linesep.join([
      f'[{self._host}] get:',
      f'[{self._host}]   src: {src}',
      f'[{self._host}]   dst: {dst}',
    ])
    log(msg)
    self._conn.get(src, local=dst)

  def run(
    self, argv, shell=False, pty=False, env={}, replace_env=False,
    encoding=None, stdin=None, stdout=None, stderr=None, enforce=True
  ):
    log = logger[self.log_level]
    self.connect()
    if not isinstance(argv, str):
      argv = shjoin(argv)
    log(f'[{self._host}] run: {argv}')
    return self._conn.run(
      argv, shell=shell, pty=pty, env=env, replace_env=replace_env,
      encoding=encoding, in_stream=stdin, out_stream=stdout,
      err_stream=stderr, warn=not enforce, hide=True)

  def sudo(
    self, argv, shell=False, pty=False, env={}, replace_env=False,
    encoding=None, stdin=None, stdout=None, stderr=None, enforce=True,
    user=None, login=False
  ):
    log = logger[self.log_level]
    self.connect()
    if not isinstance(argv, str):
      argv = shjoin(argv)
    user_argv = argv
    argv = ['sudo']
    if login:
      argv.append('-i')
    if user:
      argv.extend(('-u', user))
    argv.append(user_argv)
    argv = ' '.join(argv)
    log(f'[{self._host}] sudo: {argv}')
    return self._conn.sudo(
      argv, shell=shell, pty=pty, env=env, replace_env=replace_env,
      encoding=encoding, in_stream=stdin, out_stream=stdout,
      err_stream=stderr, warn=not enforce, hide=True)

  def forward(self, lport, rport, lhost=None):
    self.connect()
    return self._conn.forward_local(lport, rport, lhost)

  connected = property(is_connected)
  closed = property(is_closed)
