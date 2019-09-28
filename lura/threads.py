import sys
import threading
from lura.attrs import attr
from multiprocessing.pool import ThreadPool

def map(thread_count, func, items, chunksize=None):
  with ThreadPool(thread_count) as p:
    return p.map(func, items, chunksize=chunksize)

def imap(thread_count, func, items, chunksize=1):
  with ThreadPool(thread_count) as p:
    return p.imap(func, items, chunksize=chunksize)

pool = attr(
  map = map,
  imap = imap,
)

class Thread(threading.Thread):

  @classmethod
  def spawn(cls, *args, **kwargs):
    thread = cls(*args, **kwargs)
    thread.start()
    return thread

  def __init__(
    self, group=None, target=None, name=None, args=(), kwargs={}, *,
    daemon=None, reraise=True
  ):
    super().__init__(group=group, name=name, daemon=daemon, target=self.__work)
    self._thread_target = target
    self._thread_args = args
    self._thread_kwargs = kwargs
    self._thread_reraise = reraise
    self._thread_result = None
    self._thread_error = None

  def __work(self):
    try:
      self._thread_target = self._thread_target or self.work
      self._thread_result = self._thread_target(
        *self._thread_args, **self._thread_kwargs)
    except Exception:
      self._thread_error = sys.exc_info()
      if self._thread_reraise:
        raise

  def start(self):
    if not (self._thread_target or getattr(self, 'work', None)):
      raise ValueError(
        'No target was given and instance has no "work" attribute')
    super().start()

  @property
  def result(self):
    return self._thread_result

  @property
  def error(self):
    return self._thread_error
