import json as json_
from lura.attrs import ottr
from lura.format.base import Format
from lura.io import dump

class Json(Format):
  '''
  Thin wrapper for json. This class configures the json module to use
  ordered dictionaries for backing dicts, and indented json. This class
  supports dumping sets (as lists).
  '''

  class Encoder(json_.JSONEncoder):
    'Custom json encoder which support sets.'

    def __init__(self, *args, **kwargs):
      super().__init__(*args, **kwargs)

    def default(self, _):
      if isinstance(_, set):
        return list(_)
      return super().default(_)

  def __init__(self, indent=4, object_pairs_hook=ottr):
    super().__init__()
    self.indent = indent
    self.object_pairs_hook = object_pairs_hook

  def loads(self, data):
    'Load json from string ``data``.'

    return json_.loads(data, object_pairs_hook=self.object_pairs_hook)

  def loadf(self, src):
    'Load json from file ``src``.'

    with open(src, encoding='utf-8') as fd:
      return json_.load(fd, object_pairs_hook=self.object_pairs_hook)

  def dumps(self, data):
    'Return dict ``data`` as json.'

    return json_.dumps(data, indent=self.indent, cls=self.Encoder)

  def dumpf(self, data, dst, encoding='utf-8'):
    'Write dict ``data`` as json to file ``dst``.'

    data = json_.dumps(data, indent=self.indent, cls=self.Encoder)
    return dump(dst, data, encoding=encoding)

  def dumpfd(self, data, fd):
    'Write dict ``data`` as json to file descriptor ``fd``.'

    fd.write(self.dumps(data))
    if hasattr(fd, 'flush') and callable(fd.flush):
      fd.flush()
