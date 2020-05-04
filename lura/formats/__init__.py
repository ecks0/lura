from typing import Any, Optional, TextIO
from typing_extensions import Protocol

class Format(Protocol):
  'API implemented by format implementations.'

  def loads(
    self,
    data: str,
    **kwargs: Any
  ) -> Any:
  
    ...

  def loadf(
    self,
    path: str,
    encoding: Optional[str] = None,
    **kwargs: Any
  ) -> Any:
  
    ...

  def loadfd(
    self,
    fd: TextIO,
    **kwargs: Any
  ) -> Any:
  
    ...

  def dumps(
    self,
    data: Any,
    **kwargs: Any,
  ) -> str:
    
    ...

  def dumpf(
    self,
    path: str,
    data: Any,
    encoding: Optional[str] = None,
    **kwargs: Any
  ) -> None:
  
    ...

  def dumpfd(
    self,
    fd: TextIO,
    data: Any,
    **kwargs: Any
  ) -> None:
  
    ...

from .json import Json
from .pyaml import Pyaml
