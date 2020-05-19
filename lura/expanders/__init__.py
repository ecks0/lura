from typing import Any, Mapping
from typing_extensions import Protocol

class Expander(Protocol):
  'Template expander protocol.'

  def expands(self, template: str, env: Mapping[Any, Any]) -> str:
    'Expand a string `template` using `env`.'

    return ''

  def expandf(self, path: str, env: Mapping[Any, Any]) -> str:
    'Expand a file at `path` using `env`.'

    return ''

from .jinja2 import Jinja2
