from lura import LuraError
from lura import logs
from lura import utils
from lura.system.config import executor

logger = logs.get_logger(__name__)

class Deployment(utils.Kwargs):

  synchronize = True
  fail_early  = True
  workers     = None
  executor    = executor.ThreadExecutor
  log_level   = logger.INFO

  def __init__(self, **kwargs):
    self._reset()
    super().__init__(**kwargs)
    if self.workers is not None:
      self.workers = min(self.workers, len(systems) or 1)

  def _reset(self):
    self.config = None
    self.systems = None
    self.args = None
    self.kwargs = None

  def _format_result(self, res):
    ok = [
      (self.systems[_], res[_])
      for _ in range(0, len(res)) if not utils.isexc(res[_])
    ]
    err = [
      (self.systems[_], res[_])
      for _ in range(0, len(res)) if utils.isexc(res[_])
    ]
    return ok, err

  def _run(self, method, config, systems, args, kwargs):
    self.config = config
    self.systems = systems
    self.args = args
    self.kwargs = kwargs
    try:
      res = method(self)
      ok, err = self._format_result(res)
      return ok, err
    finally:
      self._reset()

  def apply(self, config, systems, *args, **kwargs):
    log = logger[self.log_level]
    log(f'Applying deployment {config.name}')
    ok, err = self._run(self.executor().apply, config, systems, args, kwargs)
    if err:
      log(f'Applied deployment {config.name} with errors')
    else:
      log(f'Applied deployment {config.name}')
    return ok, err

  def delete(self, config, systems, *args, **kwargs):
    try:
      log = logger[self.log_level]
      log(f'Deleting deployment {config.name}')
      ok, err = self._run(self.executor().delete, config, systems, args, kwargs)
      if err:
        log(f'Deleted deployment {config.name} with errors')
      else:
        log(f'Deleted deployment {config.name}')
      return ok, err
    finally:
      self._reset()

  def is_applied(self, config, systems, *args, **kwargs):
    try:
      ok, err = self._run(
        self.executor().is_applied, config, systems, args, kwargs)
      return ok, err
    finally:
      self._reset()
