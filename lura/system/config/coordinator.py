import threading
from lura import threads
from lura import logs
from lura.attrs import ottr
from lura.time import poll

log = logs.get_logger(__name__)

class Coordinator:

  def __init__(self, configs, synchronize, fail_early):
    super().__init__()
    self.conditions = ottr(
      ready = threading.Condition(),
      sync = threading.Condition(),
      done = threading.Condition(),
    )
    self.configs = configs
    self.synchronize = synchronize
    self.fail_early = fail_early
    self.cancelled = None

  @property
  def active(self):
    return tuple(_ for _ in self.configs if _.system)

  def wait(self, cond, timeout=None):
    if cond == 'sync' and not self.synchronize:
      return
    with self.conditions[cond]:
      if not self.conditions[cond].wait(timeout):
        raise TimeoutError(
          f'Coordinator did not send "{cond}" within {timeout} seconds')

  def awaiting(self, cond):
    if cond == 'sync' and not self.synchronize:
      return False
    with self.conditions[cond]:
      return len(self.conditions[cond]._waiters) >= len(self.active)

  def poll(self, cond, timeout=-1, retries=-1, pause=0.05):
    test = lambda: self.awaiting(cond)
    return poll(test, timeout=timeout, retries=retries, pause=pause)

  def notify(self, cond):
    with self.conditions[cond]:
      self.conditions[cond].notify_all()

  def cancel(self):
    conds = self.conditions
    with conds.ready, conds.sync, conds.done:
      self.cancelled = True
      for cond in conds.values():
        cond.notify_all()
