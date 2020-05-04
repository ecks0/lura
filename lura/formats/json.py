import json as pyjson
from typing import Any, Callable, Optional, TextIO

class Encoder(pyjson.JSONEncoder):

  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)

  def default(self, item):
    if isinstance(item, set):
      return list(item)
    elif hasattr(item, '__str__'):
      return str(item)
    else:
      return repr(item)

class Json:
  'Json format.'

  object_pairs_hook: Callable = dict

  def loads(
    self,
    data: str,
    **kwargs: Any
  ) -> Any:

    kwargs.setdefault('object_pairs_hook', self.object_pairs_hook)
    return pyjson.loads(data, **kwargs)

  def loadf(
    self,
    path: str,
    encoding: Optional[str] = None,
    **kwargs: Any
  ) -> Any:

    with open(path, encoding=encoding) as fd:
      return self.loadfd(fd, **kwargs)

  def loadfd(
    self,
    fd: TextIO,
    **kwargs: Any
  ) -> Any:

    kwargs.setdefault('object_pairs_hook', self.object_pairs_hook)
    return pyjson.load(fd, **kwargs)

  def dumps(
    self,
    data: Any,
    **kwargs: Any,
  ) -> str:
    
    kwargs.setdefault('cls', Encoder)
    return pyjson.dumps(data, **kwargs)

  def dumpf(
    self,
    path: str,
    data: Any,
    encoding: Optional[str] = None,
    **kwargs: Any
  ) -> None:
  
    with open(path, 'w', encoding=encoding) as fd:
      self.dumpfd(fd, data, **kwargs)

  def dumpfd(
    self,
    fd: TextIO,
    data: Any,
    **kwargs: Any
  ) -> None:
  
    kwargs.setdefault('cls', Encoder)
    pyjson.dump(data, fd, **kwargs)

