import os
import re
import subprocess
from distutils.util import strtobool

shjoin = subprocess.list2cmdline

def prefix(string, prefix, linesep=os.linesep):
  'Return `string` with each line prefixed with `prefix`.'

  return linesep.join(f'{prefix}{line}' for line in string.split(linesep))

def as_bool(val):
  'Use `strtobool` to parse `str`s into `bool`s.'

  if val == '':
    return False
  return bool(strtobool(val)) if isinstance(val, str) else bool(val)

def camel_to_snake(string):
  return re.sub('(?!^)([A-Z]+)', r'_\1', string).lower()
