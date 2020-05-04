import os
import re
import subprocess
from distutils.util import strtobool

def prefix(string: str, prefix: str, linesep: str = os.linesep) -> str:
  'Return `string` with each line prefixed with `prefix`.'

  return linesep.join(f'{prefix}{line}' for line in string.split(linesep))

def as_bool(val: str) -> bool:
  'Use `strtobool` to parse `str`s into `bool`s.'

  if val == '':
    return False
  return bool(strtobool(val))

def camel_to_snake(string: str) -> str:
  return re.sub('(?!^)([A-Z]+)', r'_\1', string).lower()
