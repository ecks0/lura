from collections import MutableMapping
from collections import MutableSequence
from lura import LuraError
from lura.attrs import attr

def deepcopy(obj, map_cls=attr, seq_cls=None):
  types = (MutableMapping, MutableSequence)
  if isinstance(obj, MutableMapping):
    cls = map_cls or type(obj)
    return cls(
      (k, copy(v, map_cls, seq_cls))
      if isinstance(v, types)
      else (k, v)
      for (k, v) in obj.items()
    )
  elif isinstance(obj, MutableSequence):
    cls = seq_cls or type(obj)
    return cls(
      copy(item, map_cls, seq_cls)
      if isinstance(item, types)
      else item
      for item in obj
    )
  else:
    raise ValueError(f'obj is not a MutableMapping or MutableSequence: {obj}')

class KwargError(LuraError): pass

class Kwargs:

  def __init__(self, **kwargs):
    super().__init__()
    cls = type(self)
    for arg in kwargs:
      if arg in self.__dict__.keys():
        raise KwargError(f'Internal attributes are forbidden: {arg}')
      if arg[0] == '_':
        raise KwargError(f'Attributes starting with _ are forbidden: {arg}')
      if not hasattr(cls, arg):
        raise KwargError(f'Class {cls.__name__} has no attribute: {arg}')
      self_attr = getattr(self, arg, None)
      if callable(self_attr) and not isinstance(self_attr, type):
        raise KwargError(f'Non-type callable attributes are forbidden: {arg}')
    for arg in kwargs:
      setattr(self, arg, kwargs[arg])
