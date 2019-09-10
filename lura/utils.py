'Miscellaneous helpers.'

import os
import types
from lura.attrs import attr
from collections import MutableMapping, MutableSequence
from copy import deepcopy
from distutils.util import strtobool

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

def asbool(val):
  'Turn something (including strings via `strtobool`) into a `bool`.'

  if val == '':
    return False
  return bool(strtobool(val)) if isinstance(val, str) else bool(val)

def remap(src, cls=attr):
  '''
  Recursively convert all MutableMappings found in src to type cls. If
  src is a MutableMapping, then src will also be converted to type cls. This
  is used for mass-converting the mapping type used in a deeply-nested data
  structure, such as converting all dicts to attrs.

  :param [MutableSequence, MutableMapping] src: source collection
  :param type cls: target MutableMapping type
  :returns: a new collection
  :rtype MutableMapping:
  '''
  types = (MutableSequence, MutableMapping)
  if isinstance(src, MutableMapping):
    return cls((
      (k, remap(v, cls)) if isinstance(v, types) else (k, v)
      for (k, v) in src.items()
    ))
  elif isinstance(src, MutableSequence):
    return src.__class__(
      remap(_, cls) if isinstance(_, types) else _
      for _ in src
    )
  else:
    raise ValueError(f'src must be MutableSequence or MutableMapping: {src}')

def scrub(obj, tag='[scrubbed]'):
  'Scrub anything that looks like a password in `MutableMapping` `obj`.'

  from collections.abc import MutableMapping, Sequence
  for name, value in obj.items():
    if isinstance(value, str) and 'pass' in name.lower():
      obj[name] = tag
    elif isinstance(value, bytes) and 'pass' in name.lower():
      obj[name] = tag.encode()
    elif isinstance(value, MutableMapping):
      scrub(value)
    elif isinstance(value, Sequence):
      for item in value:
        if isinstance(value, MutableMapping):
          scrub(value)
  return obj

def common(data, count=None):
  'Return the count most common values found in list data.'

  counts = ((data.count(value), value) for value in set(data))
  common = sorted(counts, reverse=True)
  if count is None:
    return common
  return common[:min(len(data), count)]

class StrUtil(str):
  'Subclass of string offering extra operations.'

  def lines(self):
    'Strip this object of right newlines and return a split on `os.linesep`.'

    return self.rstrip(os.linesep).splitlines()

  def json(self):
    'Parse this object as a json object.'

    from lura.formats import json
    return json.loads(self)

  def jsons(self):
    'Parse this object as a sequence of json objects, one per line.'

    from lura.formats import json
    return [json.loads(blob) for line in self.lines()]

  def yaml(self):
    'Parse this object as a yaml object.'

    from lura.formats import yaml
    return yaml.loads(self)

  def prefix(self, prefix):
    'Return self with each line prefixed with `prefix`.'

    return os.linesep.join(f'{prefix}{line}' for line in self.split(os.linesep))

  def pipe(self, **kwargs):
    'Spawn a process and write this object to the process stdin.'

    raise NotImplementedError()

  def print(self):
    'Print this object.'

    print(self)

strutil = StrUtil
