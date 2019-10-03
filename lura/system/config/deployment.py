from lura import logs
from lura import utils
from lura.system.config import executor

logger = logs.get_logger(__name__)

class Deployment(utils.Kwargs):

  synchronize = True
  fail_early  = True
  workers     = None
  log_level   = logger.INFO

  def __init__(self, **kwargs):
    self.config = None
    self.systems = None
    self.force = None
    self.purge = None
    super().__init__(**kwargs)
    if self.workers is not None:
      self.workers = min(self.workers, len(systems) or 1)

  def _format_result(self, res):
    ok = [self.systems[_] for _ in range(0, len(res)) if not res[_]]
    err = [(self.systems[_], res[_]) for _ in range(0, len(res)) if res[_]]
    return ok, err

  def apply(self, config, systems, force=False):
    self.config = config
    self.systems = systems
    self.force = force
    try:
      log = logger[self.log_level]
      log(f'Applying deployment {self.config.name}')
      res = executor.ThreadExecutor().apply(self)
      ok, err = self._format_result(res)
      if err:
        log(f'Applied deployment {self.config.name} with errors')
      else:
        log(f'Applied deployment {self.config.name}')
      return ok, err
    finally:
      self.config = None
      self.systems = None
      self.force = None

  def delete(self, config, systems, force=False, purge=False):
    self.config = config
    self.systems = systems
    self.force = force
    self.purge = purge
    try:
      log = logger[self.log_level]
      log(f'Deleting deployment {self.config.name}')
      res = executor.ThreadExecutor().delete(self)
      ok, err = self._format_results(res)
      if err:
        log(f'Deleted deployment {self.config.name} with errors')
      else:
        log(f'Deleted deployment {self.config.name}')
      return ok, err
    finally:
      self.config = None
      self.systems = None
      self.force = None
      self.purge = None

  def is_applied(self, config, systems):
    self.config = config
    self.systems = systems
    try:
      res = executor.ThreadExecutor().is_applied(self)
      ok, err = self._format_results(res)
      if err:
        raise RuntimeError('Some hosts failed with exceptions')
      return all(ok)
    finally:
      self.config = None
      self.systems = None
