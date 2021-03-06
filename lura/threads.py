import logging
import sys
import threading
import time
from lura.utils import ExcInfo
from typing import Any, Callable, Mapping, Optional, Sequence

log = logging.getLogger(__name__)

class Thread(threading.Thread):
  '''
  Thread subclass with the following features:

 - Captures the result or exc_info generated by the target callable.
 - spawn() static method for creating and starting threads.
 - improved join() method
 '''

  @classmethod
  def spawn(cls, *args: Any, **kwargs: Any) -> 'Thread':
    thread = cls(*args, **kwargs)
    thread.start()
    return thread

  _thread_func: Callable
  _thread_args: Sequence[Any]
  _thread_kwargs: Mapping[str, Any]
  _thread_result: Optional[Any]
  _thread_error: Optional[ExcInfo]

  def __init__(
    self,
    group: Optional[Any] = None,
    target: Optional[Callable] = None,
    name: Optional[str] = None,
    args: Sequence[Any] = (),
    kwargs: Mapping[str, Any] = {},
    daemon: Optional[bool] = None,
  ) -> None:
    super().__init__(group=group, name=name, daemon=daemon)
    if target is None:
      target = self.run
    self._thread_func = target # type: ignore
    self._thread_args = args
    self._thread_kwargs = kwargs
    self._thread_result = None
    self._thread_error = None
    self.run = self._thread_work # type: ignore

  @property
  def result(self) -> Optional[Any]:
    return self._thread_result

  @property
  def error(self) -> Optional[ExcInfo]:
    return self._thread_error
  
  def _thread_work(self) -> None:
    try:
      self._thread_result = self._thread_func(
        *self._thread_args,
        **self._thread_kwargs
      )
    except Exception:
      self._thread_error = sys.exc_info()

  def join(self, timeout: Optional[float] = None) -> None:
    if timeout is None:
      while self.is_alive(): super().join()
      return
    while self.is_alive():
      start = time.time()
      super().join(timeout)
      timeout -= time.time() - start
      if timeout < 0:
        return
      
  def run(self) -> None:
    
    raise NotImplementedError()

