from collections import Sequence
from lura import logs
from lura import net
from lura import utils
from lura import system
from lura.attrs import attr
from lura import system
from lura.system.config import exec

log = logger = logs.get_logger(__name__)

class Group(utils.Kwargs):

  synchronize     = True
  fail_early      = True
  workers         = None
  recycle_systems = False
  executor        = exec.ThreadExecutor
  log_level       = logger.INFO

  def __init__(
    self, hosts, port=22, user=None, password=None, key_file=None,
    passphrase=None, timeout=60.0, auth_timeout=60.0, sudo_password=None,
    sudo=False, **kwargs
  ):
    self._hosts = hosts
    self._system_args = attr(
      port=port, user=user, password=password, key_file=key_file,
      passphrase=passphrase, timeout=timeout, auth_timeout=auth_timeout,
      sudo_password=sudo_password, sudo=sudo)
    self._reset()
    super().__init__(**kwargs)
    if self.workers is not None:
      self.workers = min(self.workers, len(systems) or 1)

  def _reset(self):
    self.config = None
    self.systems = None
    self.args = None
    self.kwargs = None

  def _create_systems(self):
    log = logger[self.log_level]
    history = []
    systems = []
    for host in self._hosts:
      args = self._system_args.copy()
      if isinstance(host, str):
        args.host = host
      elif isinstance(host, Sequence) and len(host) == 2:
        args.name, args.host = host
      elif isinstance(host, system.System):
        systems.append(host)
        continue
      else:
        raise ValueError(f'Unknown type for host in hosts list: {host}')
      # FIXME
      if args.host == '127.0.0.1':
        args.host = 'localhost'
      addr = net.address(args.host)
      if addr is None:
        raise RuntimeError(f'Could not resolve hostname: {host}')
      elif addr in history:
        log(f'Duplicate host in hosts list: {host} ({addr})')
        continue
      history.append(addr)
      if args.host == 'localhost':
        sudo, sudo_password = args.get('sudo'), args.get('sudo_password')
        sys = system.Local(sudo=sudo, sudo_password=sudo_password)
      else:
        sys = system.Ssh(**args)
      systems.append(sys)
    return systems

  def _format_result(self, res):
    ok = [
      (self.systems[_], res[_])
      for _ in range(0, len(res))
      if not utils.isexc(res[_])
    ]
    err = [
      (self.systems[_], res[_])
      for _ in range(0, len(res))
      if utils.isexc(res[_])
    ]
    return ok, err

  def _run(self, method, config, args, kwargs):
    if isinstance(config, type):
      config = config()
    self.config = config
    self.systems = self._create_systems()
    self.args = args
    self.kwargs = kwargs
    try:
      res = method(self)
      ok, err = self._format_result(res)
      return ok, err
    finally:
      self._reset()

  def apply(self, config, *args, **kwargs):
    log = logger[self.log_level]
    ok, err = self._run(self.executor().apply, config, args, kwargs)
    return ok, err

  def delete(self, config, *args, **kwargs):
    try:
      log = logger[self.log_level]
      ok, err = self._run(self.executor().delete, config, args, kwargs)
      return ok, err
    finally:
      self._reset()

  def is_applied(self, config, systems, *args, **kwargs):
    try:
      ok, err = self._run(self.executor().is_applied, config, args, kwargs)
      return ok, err
    finally:
      self._reset()
