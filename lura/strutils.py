import os

def prefix(string, prefix, linesep=os.linesep):
  'Return `string` with each line prefixed with `prefix`.'

  return linesep.join(f'{prefix}{line}' for line in string.split(linesep))
