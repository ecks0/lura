'Periodic task scheduler.'

import schedule
from abc import abstractmethod
from lura import logs
from lura import threads
from time import sleep

logger = logs.get_logger(__name__)

class Task(threads.Thread):
  '''
  This is a base class for scheduled tasks, which are ephemeral threads
  spawned at the appropriate time and then discarded by the `Scheduler`.

  Subclasses shall implement `run()` to perform the scheduled task.
  '''

  log_level = logger.INFO

  def __init__(self, scheduler, *args, **kwargs):
    for _ in kwargs:
      # don't allow these to be forwarded to the Thread ctor
      assert(_ not in ('target', 'args', 'kwargs'))
    super().__init__(*args, **kwargs)
    self._scheduler = scheduler

  def _on_error(self):
    '''
    This will be called from inside an `except` block (so you can call
    `sys.exc_info()`) when unhandled exceptions are encountered.
    '''

    pass

  @abstractmethod
  def run(self):
    pass

  def work(self):
    log = logger[self.log_level]
    try:
      log(f'{type(self).__name__} starting')
      self.run()
    except Exception:
      log(f'Unhandled exception in {type(self).__name__}', exc_info=True)
      self._on_error()
    finally:
      log(f'{type(self).__name__} stopping')

class Scheduler:
  '''
  Periodic task scheduler implemented using the `schedule` package.

  Pass the constructor a `schedule`, which is a list of pairs:

  `[(schedule.Job, lura.at.Task), ...]`

  Example:
  ```
  import schedule
  from lura import at

  class CycleLogFiles(at.Task): pass
  class StashLogFIles(at.Task): pass

  sched = [
    (schedule.every().day.at('00:15'), CycleLogFiles),
    (schedule.every().day.at('00:30'), StashLogFiles),
  ]

  scheduler = at.Scheduler(sched)
  scheduler.start()
  ```
  '''

  log_level = logger.INFO

  def __init__(self, schedule):
    super().__init__()
    self._schedule = schedule
    self._applied = False
    self._working = False

  def _on_error(self):
    '''
    This will be called from inside an `except` block (so you can call
    `sys.exc_info()`) when unhandled exceptions are encountered.
    '''

    pass

  def _format_task(self, job, task):
    if job.at_time is not None:
      return '%s every %s %s at %s' % (
        task.__name__,
        job.interval,
        job.unit[:-1] if job.interval == 1 else job.unit,
        job.at_time,
      )
    else:
      fmt = (
        '%(task)s every %(interval)s ' +
        'to %(latest)s ' if job.latest is not None else '' +
        '%(unit)s'
      )
      return fmt % dict(
        task = task.__name__,
        interval = job.interval,
        latest = job.latest,
        unit = job.unit[:-1] if job.interval == 1 else job.unit,
      )

  def _apply_schedule(self):
    log = logger[self.log_level]
    if self._applied:
      log('Asked to apply schedule when already applied')
      return
    for job, task in self._schedule:
      job.do(task.spawn)
      log('Scheduled ' + self._format_task(job, task))
    self._applied = True

  def work(self):
    self._working = True
    log = logger[self.log_level]
    log('Task scheduler starting')
    self._apply_schedule()
    try:
      import schedule
      while self._working:
        schedule.run_pending()
        sleep(1)
    except Exception:
      log.excetion('Unhanlded exception in task scheduler')
      self._on_error()
      raise
    finally:
      log('Task scheduler stopping')

  start = work

  def stop(self):
    self._working = False
