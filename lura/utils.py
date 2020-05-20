from lura import strings
from traceback import format_exception
from types import TracebackType
from typing import Tuple, Type, Optional, Union

# type alias for the result of sys.exc_info()
ExcInfo = Union[Tuple[Type[BaseException], BaseException, TracebackType], Tuple[None, None, None]]

def format_exc_info(exc_info: ExcInfo, prefix: Optional[str] = None) -> str:
  res = '\n'.join(format_exception(*exc_info)).rstrip()
  if prefix:
    res = strings.prefix(res, prefix)
  return res
