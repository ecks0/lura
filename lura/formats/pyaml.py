import io
import pyaml
from enum import Enum
from typing import Any, Optional, TextIO

class Pyaml:
  '''
  Yaml format implemented using pyaml.
  
  This class uses the `pyaml` module, which produces output that the `yaml`
  module would consider to be incorrect (e.g. '123' is printed 123, an integer
  and not a string), however the output is much more suitable for human
  consumption.
  '''

  def loads(
    self,
    data: str,
    **kwargs: Any
  ) -> Any:

    raise NotImplementedError()

  def loadf(
    self,
    path: str,
    encoding: Optional[str] = None,
    **kwargs: Any
  ) -> Any:

    raise NotImplementedError()

  def loadfd(
    self,
    fd: TextIO,
    encoding: Optional[str] = None,
    **kwargs: Any
  ) -> Any:

    raise NotImplementedError()

  def dumps(
    self,
    data: Any,
    **kwargs: Any,
  ) -> str:

    with io.StringIO() as buf:
      self.dumpfd(buf, data)
      return buf.getvalue()

  def dumpf(
    self,
    path: str,
    data: Any,
    encoding: Optional[str] = None,
    **kwargs: Any
  ) -> None:

    with open(path, 'w', encoding=encoding) as fd:
      self.dumpfd(fd, data)

  def dumpfd(
    self,
    fd: TextIO,
    data: Any,
    **kwargs: Any
  ) -> None:
  
    pyaml.p(data, file=fd, sort_dicts=False)
