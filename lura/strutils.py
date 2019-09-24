import os
from distutils.util import strtobool

def prefix(string, prefix, linesep=os.linesep):
  'Return `string` with each line prefixed with `prefix`.'

  return linesep.join(f'{prefix}{line}' for line in string.split(linesep))

def as_bool(val):
  'Use `strtobool` to parse `str`s into `bool`s.'

  if val == '':
    return False
  return bool(strtobool(val)) if isinstance(val, str) else bool(val)
