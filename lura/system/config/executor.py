import sys
import threading
from lura import LuraError
from copy import deepcopy
from lura import threads
from lura import logs
from lura import utils
from lura.iter import always
from lura.time import poll
from lura.system.config import coordinator
from multiprocessing import pool
from time import sleep

log = logs.get_logger(__name__)

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

class ThreadExecutor(utils.Kwargs):

  coordinator_type       = coordinator.Coordinator
  threads_start_timeout  = 2.0
  threads_start_interval = 0.01
  threads_ready_timeout  = 2.0
  threads_ready_interval = 0.01
  run_loop_interval      = 0.05

  def __init__(self, **kwargs):
    super().__init__(**kwargs)

  def _wait_for_start(self, configs):
    test = lambda: all(bool(_.system) for _ in configs)
    timeout = self.threads_start_timeout
    pause = self.threads_start_interval
    if not poll(test, timeout=timeout, pause=pause):
      raise TimeoutError(f'Threads did not start within {timeout} seconds')

  def _wait_for_ready(self, coord):
    timeout = self.threads_ready_timeout
    pause = self.threads_ready_interval
    if not coord.poll('ready', timeout=timeout, pause=pause):
      raise RuntimeError(f'Threads did not ready within {timeout} seconds')

  def _run_loop(self, configs, coord):
    self._wait_for_start(configs)
    self._wait_for_ready(coord)
    coord.notify('ready')
    while not (coord.poll('done', retries=0) or coord.cancelled):
      if coord.poll('sync', retries=0):
        coord.notify('sync')
      sleep(self.run_loop_interval)
    if not coord.cancelled:
      coord.notify('done')

  def _run(self, fn, deploy):
    configs = [deepcopy(deploy.config) for _ in range(0, len(deploy.systems))]
    coord = self.coordinator_type(
      configs, deploy.synchronize, deploy.fail_early)
    items = zip(
      configs,
      deploy.systems,
      always(coord),
      always(deploy.args),
      always(deploy.kwargs),
    )
    pool = ThreadPool.spawn(fn, items, deploy.workers)
    try:
      self._run_loop(configs, coord)
      pool.join()
      return pool.result
    except BaseException:
      if pool.isAlive():
        coord.cancel()
        pool.join()
      raise

  def _apply(self, item):
    config, system, coord, args, kwargs = item
    try:
      config.apply(system, *args, coordinator=coord, **kwargs)
    except Exception:
      return sys.exc_info()

  def apply(self, deploy):
    return self._run(self._apply, deploy)

  def _delete(self, item):
    config, system, coord, args, kwargs = item
    try:
      config.delete(system, *args, coordinator=coord, **kwargs)
    except Exception:
      return sys.exc_info()

  def delete(self, deploy):
    return self._run(self._delete, deploy)

  def _is_applied(self, item):
    config, system, coord, args, kwargs = item
    try:
      return config.is_applied(system, *args, coordinator=coord, **kwargs)
    except Exception:
      return sys.exc_info()

  def is_applied(self, deploy):
    return self._run(self._is_applied, deploy)
