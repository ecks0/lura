import hashlib

class Settings:

  __slots__ = ('buflen',)

  buflen: int

  def __init__(self) -> None:
    super().__init__()
    self.buflen = 256 * 1024

settings = Settings()

def hash(buf: bytes, alg: str = 'sha512') -> str:
  'Hash bytes.'

  algs = hashlib.algorithms_guaranteed
  if not alg in algs:
    raise ValueError(f'Algorithm {alg} not in {algs}')
  impl = getattr(hashlib, alg)()
  impl.update(buf)
  return str(impl.hexdigest())

def hashs(buf: str, alg: str ='sha512') -> str:
  'Hash a string.'

  return hash(buf.encode(), alg=alg)

def hashf(path: str, alg: str = 'sha512') -> str:
  'Hash a file.'

  algs = hashlib.algorithms_guaranteed
  if not alg in algs:
    raise ValueError(f'Algorithm {alg} not in {algs}')
  impl = getattr(hashlib, alg)()
  with open(path, 'rb') as fd:
    while True:
      buf = fd.read(settings.buflen)
      if buf == b'':
        break
      impl.update(buf)
  return str(impl.hexdigest())
       
class HashError(ValueError):

  def __init__(self, path: str, alg: str, expected: str, received: str) -> None:
    msg = f'{path}: {alg} expected {expected}, got {received}'
    super().__init__(msg)
    self.path = path
    self.alg = alg
    self.expected = expected
    self.received = received

def checkf(path: str, alg: str, sum: str) -> None:
  'Raise `HashError` if the sum of `path` for `alg` does not match `sum`.'

  sum2 = hashf(path, alg)
  if sum != sum2:
    raise HashError(path, alg, sum, sum2)
