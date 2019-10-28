import types
from collections import MutableMapping
from collections import MutableSequence
from lura.attrs import attr

# FIXME this needs a different name
def deepcopy(obj, map_cls=attr, seq_cls=None):
  types = (MutableMapping, MutableSequence)
  if isinstance(obj, MutableMapping):
    cls = map_cls or type(obj)
    return cls(
      (k, deepcopy(v, map_cls, seq_cls))
      if isinstance(v, types)
      else (k, v)
      for (k, v) in obj.items()
    )
  elif isinstance(obj, MutableSequence):
    cls = seq_cls or type(obj)
    return cls(
      deepcopy(item, map_cls, seq_cls)
      if isinstance(item, types)
      else item
      for item in obj
    )
  else:
    raise ValueError(f'obj is not a MutableMapping or MutableSequence: {obj}')

class Kwargs:

  def __init__(self, *args, **kwargs):
    super().__init__()
    vars(self).update(kwargs)

def isexc(o):
  '''
  `True` if `o` is a tuple as returned by `sys.exc_info()`, else
  `False`.
  '''

  return isinstance(o, tuple) and len(o) == 3 and (
    isinstance(o[0], type) and
    isinstance(o[1], o[0]) and
    isinstance(o[2], types.TracebackType)
  )
