from .json import Json
from .yaml import Yaml

json = Json()
yaml = Yaml()

from lura.attrs import attr

formats = attr(
  jsn = json,
  json = json,
  yaml = yaml,
  yml = yaml,
)

del attr
