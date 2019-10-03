import sys
import threading
from lura import LuraError
from copy import deepcopy
from lura import threads
from lura import logs
from lura.iter import always
from lura.time import poll
from lura.system.config.coordinator import Coordinator
from multiprocessing import pool
from time import sleep

log = logs.get_logger(__name__)
pause = 0.05

class ThreadPool(threads.Thread):

  def __init__(self, fn, args, workers):
    super().__init__()
    self.fn = fn
    self.args = args
    self.workers = workers

  def run(self):
    with pool.ThreadPool(self.workers) as p:
      res = p.map(self.fn, self.args)
      return res

class ThreadExecutor:

  def __init__(self):
    super().__init__()

  def _wait_for_threads(self, configs):
    def test():
      return all(bool(_.system) for _ in configs)
    if not poll(test, timeout=1, pause=0.001):
      raise LuraError('Threads did not start within 1 second')

  def _run(self, fn, deploy, *args):
    configs = [deepcopy(deploy.config) for _ in range(0, len(deploy.systems))]
    coord = Coordinator(configs, deploy.synchronize, deploy.fail_early)
    items = zip(configs,  deploy.systems, always(coord), always(args))
    pool = ThreadPool.spawn(fn, items, deploy.workers)
    self._wait_for_threads(configs)
    try:
      if not coord.poll('ready', timeout=10, pause=pause):
        raise RuntimeError('Workers did not ready within 10 seconds')
      coord.notify('ready')
      while not (coord.poll('done', retries=0) or coord.cancelled):
        if coord.poll('sync', retries=0):
          coord.notify('sync')
        sleep(pause)
      if not coord.cancelled:
        coord.notify('done')
      pool.join()
      return pool.result
    except BaseException:
      if pool.isAlive():
        coord.cancelled = True
        for cond in 'sync', 'done':
          coord.notify(cond)
        pool.join()
      raise

  def _apply(self, item):
    config, system, coord, (force) = item
    try:
      config.apply(system, coordinator=coord, force=force)
    except Exception:
      return sys.exc_info()

  def apply(self, deployment):
    return self._run(self._apply, deployment, deployment.force)

  def _delete(self, item):
    config, system, coord, (force, purge) = item
    try:
      config.delete(system, coordinator=coord, force=force, purge=purge)
    except Exception:
      return sys.exc_info()

  def delete(self, deployment):
    return self._run(
      self._delete, deployment, deployment.force, deployment.purge)

  def _is_applied(self, item):
    config, system, coord, _ = item
    try:
      return config.is_applied(system, coordinator=coord)
    except Exception:
      return sys.exc_info()

  def is_applied(self, deployment):
    return self._run(self._is_applied, deploymnet)
