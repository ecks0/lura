import jinja2
import os
from typing import Any, Mapping, MutableMapping

class Jinja2:
  'Jinja2 template expander.'

  defaults: MutableMapping[str, Any] = dict(
    trim_blocks = True,
    lstrip_blocks = True,
    extensions = (
      'jinja2.ext.do',
      'jinja2.ext.loopcontrols',
    ),
  )

  _engine: jinja2.Environment

  def __init__(self, **kwargs: Any) -> None:
    super().__init__()
    for k, v in self.defaults.items():
      kwargs.setdefault(k, v)
    self._engine = jinja2.Environment(**kwargs)        

  def expands(self, template: str, env: Mapping[Any, Any]) -> str:
    return self._engine.from_string(template).render(env)

  def expandf(self, path: str, env: Mapping[Any, Any]) -> str:
    with open(path) as pathf:
      return self._engine.from_string(pathf.read()).render(env)
