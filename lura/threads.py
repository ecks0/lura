import threading
from lura.attrs import attr
from multiprocessing.pool import ThreadPool

def map(thread_count, func, items, chunksize=None):
  with ThreadPool(thread_count) as p:
    return p.map(func, items, chunksize=chunksize)

def imap(thread_count, func, items, chunksize=None):
  with ThreadPool(thread_count) as p:
    return p.imap(func, items, chunksize=chunksize)

pool = attr(
  map = map,
  imap = imap,
)

class Thread(threading.Thread):

  def __init__(
    self,
    group=None,
    target=None,
    name=None,
    args=(),
    kwargs={},
    *,
    daemon=None,
  ):
    super().__init__(group=group, name=name, daemon=daemon, target=self.work_)
    self.target_ = target
    self.args_ = args
    self.kwargs_ = kwargs
    self.result = None
    self.error = None

  def work_(self):
    try:
      self.result = self.target_(*self.args_, **self.kwargs_)
    except Exception:
      self.error = sys.exc_info()
