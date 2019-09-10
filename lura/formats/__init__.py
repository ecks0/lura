from .json import Json
from .pickle import Pickle
from .yaml import Yaml
from .csv import Csv

json = Json()
pickle = Pickle()
yaml = Yaml()
csv = Csv()

from lura.attrs import attr

exts = attr(
  csv = csv,
  jsn = json,
  json = json,
  pickle = pickle,
  pckl = pickle,
  yaml = yaml,
  yml = yaml,
)

del attr

def for_ext(ext):
  if ext not in exts:
    raise ValueError(f'No format for file extension: {ext}')
  return exts[ext]

def for_path(path):
  ext = path.split('.')[-1]
  if ext not in exts:
    raise ValueError(f'No format for file extension: {path}')
  return exts[ext]
