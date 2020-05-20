import sys
import yaml

from typing import Any, Optional, TextIO

class Yaml:
  'Yaml format.'

  def loads(
    self,
    data: str,
    **kwargs: Any
  ) -> Any:
  
    kwargs.setdefault('Loader', yaml.SafeLoader)
    return yaml.load(data, **kwargs)

  def loadf(
    self,
    path: str,
    encoding: Optional[str] = None,
    **kwargs: Any
  ) -> Any:

    kwargs.setdefault('Loader', yaml.SafeLoader)
    if encoding is None:
      encoding = sys.getdefaultencoding()  
    with open(path, encoding=encoding) as pathf:
      return yaml.load(pathf, **kwargs)

  def loadfd(
    self,
    fd: TextIO,
    **kwargs: Any
  ) -> Any:
  
    kwargs.setdefault('Loader', yaml.SafeLoader)
    return yaml.load(fd, **kwargs)

  def dumps(
    self,
    data: Any,
    **kwargs: Any,
  ) -> str:

    return yaml.dump(data)

  def dumpf(
    self,
    path: str,
    data: Any,
    encoding: Optional[str] = None,
    **kwargs: Any
  ) -> None:
  
    if encoding is None:
      encoding = sys.getdefaultencoding()
    with open(path, 'w', encoding=encoding) as pathf:
      yaml.dump(data, pathf)

  def dumpfd(
    self,
    fd: TextIO,
    data: Any,
    **kwargs: Any
  ) -> None:
  
    yaml.dump(data, fd)
