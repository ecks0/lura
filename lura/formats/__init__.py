from . import csv
from . import json
from . import pickle
from . import yaml

csv = csv.Format()
json = json.Format()
pickle = pickle.Format()
yaml = yaml.Format()

exts = dict(
  csv = csv,
  jsn = json,
  json = json,
  pickle = pickle,
  pckl = pickle,
  yaml = yaml,
  yml = yaml,
)

def for_ext(ext):
  if ext not in exts:
    raise ValueError(f'No format for file extension: {ext}')
  return exts[ext]

def for_path(path):
  ext = path.rsplit('.', 1)[-1]
  if ext not in exts:
    raise ValueError(f'No format for file extension: {path}')
  return exts[ext]
