import time
from lura.iters import BufferedIterator, always
from lura.utils import ExcInfo
from typing import Callable, Optional

def poll(
  test: Callable[[], bool], # returns True if poll condition is met else False
  timeout: float = -1.0,    # timeout in seconds
  retries: int = -1,        # max numbner of retries
  pause: float = 0.0        # pause between tests in seconds
) -> bool:
  'Poll for a condition.'

  timer: Optional['Timer'] = Timer(start=True) if timeout >= 0 else None
  tries = BufferedIterator(always(None) if retries < 0 else range(-1, retries))
  for _ in tries:
    if test():
      return True
    if timer is not None and timer.time >= timeout:
      break
    if pause > 0 and tries.has_next():
      time.sleep(pause)
  return False

class Timer:

  begin: Optional[float]
  end: Optional[float]

  def __init__(self, start: bool = False):
    super().__init__()
    self.begin = None
    self.end = None
    if start:
      self.start()

  def __enter__(self) -> 'Timer':
    self.start()
    return self

  def __exit__(self, *exc_info: ExcInfo) -> None:
    self.stop()

  def start(self) -> None:
    self.end = None
    self.begin = time.time()

  def stop(self) -> None:
    end = time.time()
    if self.begin is None:
      raise ValueError('Timer not started')
    self.end = end

  @property
  def started(self) -> bool:
    return self.begin is not None and self.end is None

  @property
  def time(self) -> float:
    now = time.time()
    if self.begin is None:
      raise ValueError('Timer not started')
    return (now if self.end is None else self.end) - self.begin
