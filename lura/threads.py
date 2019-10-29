import ctypes
import inspect
import logging
import sys
import threading
from lura.attrs import attr
from lura.time import poll
from time import sleep

log = logging.getLogger(__name__)

class Synchronize:
  '''
  As a decorator for functions or instance, class, or static methods:

  - functions will lock on the function
  - instance methods will lock on the instance
  - class methods will lock on the class
  - static methods will lock on the class

  As a context manager:

  The object to lock on is passed to the constructor as `wrapped`.

  Inspired by:

  http://blog.dscpl.com.au/2014/01/the-missing-synchronized-decorator.html
  '''

  lock = threading.RLock()
  lock_name = '__synchronize__'

  def __init__(self, wrapped=None, owner=None, type=threading.RLock):
    super().__init__()
    self.wrapped = wrapped
    self.owner = owner
    self.lock_type = type

  def get_lock(self, obj):
    if self.owner is not None:
      obj = self.owner
    ctx = vars(obj)
    if self.lock_name not in ctx:
      with self.lock:
        if self.lock_name not in ctx:
          setattr(obj, self.lock_name, self.lock_type())
    return ctx[self.lock_name]

  def __enter__(self):
    lock = self.get_lock(self.wrapped)
    lock.acquire()

  def __exit__(self, *exc_info):
    lock = self.get_lock(self.wrapped)
    lock.release()

  def __get__(self, obj, cls=None):
    # instance, class, and static methods will enter here
    if obj and cls:
      def wrapper_instance(*args, **kwargs):
        with self.get_lock(obj):
          return self.wrapped(obj, *args, **kwargs)
      return wrapper_instance
    elif cls:
      wrapped = self.wrapped.__get__(None, cls)
      def wrapper_class(*args, **kwargs):
        with self.get_lock(cls):
          return wrapped(*args, **kwargs)
      return wrapper_class
    else:
      assert(False)

  def __call__(self, *args, **kwargs):
    # functions will enter here
    with self.get_lock(self.wrapped):
      return self.wrapped(*args, **kwargs)

synchronize = Synchronize

def _async_raise(tid, exc_type):
  '''
  Raise an exception in thread with id `tid`. Return `True` if the exception
  was sent to the thread, or `False` if thead id `tid` was not found.
  '''

  if not inspect.isclass(exc_type):
    raise TypeError(f'exc_type is not a class: {exc_type}')
  res = ctypes.pythonapi.PyThreadState_SetAsyncExc(
    ctypes.c_long(tid), ctypes.py_object(exc_type))
  return res != 0

class Cancelled(RuntimeError):

  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)

class Thread(threading.Thread):

  cancel_poll_interval = 0.05

  @classmethod
  def spawn(cls, *args, **kwargs):
    thread = cls(*args, **kwargs)
    thread.start()
    return thread

  def __init__(
    self, group=None, target=None, name=None, args=(), kwargs={}, *,
    daemon=None, reraise=False
  ):
    super().__init__(
      group=group, name=name, daemon=daemon)
    self._thread_target = target
    self._thread_args = args
    self._thread_kwargs = kwargs
    self._thread_reraise = reraise
    self._thread_result = None
    self._thread_error = None

  def _thread_work(self):
    try:
      self._thread_result = self._thread_target(
        *self._thread_args, **self._thread_kwargs)
    except Exception:
      self._thread_error = sys.exc_info()
      if self._thread_reraise:
        raise

  def _thread_get_id(self):
    if not self.isAlive():
      return None
    if hasattr(self, '_thread_id'):
      return self._thread_id
    for tid, tobj in threading._active.items():
      if tobj is self:
        return tid
    return None

  def cancel(self, timeout=None, exc_type=Cancelled, force=False):
    '''
    Cancel by raising an exception in the running thread. This approach is
    not recommended as it is not reliable and can fail in surprising ways;
    however, it can work well when designed for. Two things to note:

    - If the thread is executing C code (`sleep()`, `socket.accept()`), the
      exception will not be raised until execution returns to the python
      interpreter.

    - Any C code running in the thread which invokes `PyErr_Clear` from the
      C api before returning will effectively clear the raised exception.

    When `force` is `False`, one exception will be raised in the thread. When
    `force` is `True`, the thread will be barraged with exceptions until it
    stops, or the timeout expires.

    In the former case, the thread will have an opportunity to handle (or
    discard) the raised exception before returning. In the latter case,
    any exception handlers will themselves be interrupted by the barrage of
    exceptions.

    See the original implementation notes for more details:

    http://tomerfiliba.com/recipes/Thread2/
    '''

    def cancel(tid):
      _async_raise(tid, exc_type)
      sleep(0)
      return not self.isAlive()

    tid = self._thread_get_id()
    if tid is None:
      if not self.isAlive():
        return True
      self.join(timeout)
      return self.isAlive()
    if not force:
      cancel(tid)
      self.join(timeout)
      return self.isAlive()
    timeout = -1 if timeout is None else timeout
    test = lambda: cancel(tid)
    return poll(test, timeout=timeout, pause=self.cancel_poll_interval)

  def run(self):
    '''
    If no target is passed to the constructor, this method is used as the
    target.
    '''

    raise NotImplementedError()

  def start(self):
    # FIXME !!!
    if not self._thread_target:
      self._thread_target = self.run
    self.run = self._thread_work
    super().start()

  @property
  def result(self):
    return self._thread_result

  @property
  def error(self):
    return self._thread_error
