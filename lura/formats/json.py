import json
from io import StringIO
from lura.attrs import ottr
from lura.formats import base

class Encoder(json.JSONEncoder):

  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)

  def default(self, item):
    if isinstance(item, set):
      return list(item)
    elif hasattr(item, '__str__'):
      return str(item)
    else:
      return repr(item)

class Format(base.Format):
  '''
  This class loads json using ordered dictionaries, and `repr()`s unsupported
  types on dump rather than raising.
  '''

  object_pairs_hook = ottr

  def __init__(self):
    super().__init__()

  def loads(self, data, **kwargs):
    kwargs.setdefault('object_pairs_hook', self.object_pairs_hook)
    return json.loads(data, **kwargs)

  def loadf(self, src, encoding=None, **kwargs):
    with open(src, encoding=encoding) as fd:
      return self.loadfd(fd, **kwargs)

  def loadfd(self, fd, **kwargs):
    kwargs.setdefault('object_pairs_hook', self.object_pairs_hook)
    return json.load(fd, **kwargs)

  def dumps(self, data, **kwargs):
    kwargs.setdefault('cls', Encoder)
    return json.dumps(data, **kwargs)

  def dumpf(self, data, dst, encoding=None, **kwargs):
    with open(dst, 'w', encoding=encoding) as fd:
      self.dumpfd(data, fd, **kwargs)

  def dumpfd(self, data, fd, **kwargs):
    kwargs.setdefault('cls', Encoder)
    json.dump(data, fd, **kwargs)
    if hasattr(fd, 'flush') and callable(fd.flush):
      fd.flush()
