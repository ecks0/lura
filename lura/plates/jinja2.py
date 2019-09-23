import jinja2 as _jinja2
import os
from lura.plates import base

class Expander(base.Expander):
  '''
  Expand templates using Jinja2.

  The following extensions are enabled:

  - jinja2.ext.do
  - jinja2.ext.loopcontrols

  The following environment settings are used:

  - trim_blocks
  - lstrip_blocks
  - FileSystemLoader for cwd
  '''

  extensions = [
    'jinja2.ext.do',
    'jinja2.ext.loopcontrols',
  ]

  def __init__(self, cwd=None):
    super().__init__()
    cwd = os.getcwd() if cwd is None else cwd
    self.engine = _jinja2.Environment(
      trim_blocks = True,
      lstrip_blocks = True,
      loader = _jinja2.FileSystemLoader(cwd),
      extensions = self.extensions,
    )

  def expandss(self, env, tmpl):
    return self.engine.from_string(tmpl).render(env)

  def expandsf(self, env, tmpl, dst, encoding=None):
    with open(dst, 'w', encoding=encoding) as fd:
      fd.write(self.engine.from_string(tmpl).render(env))
