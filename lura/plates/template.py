from string import Template
from lura.plates import base

class Expander(base.Expander):
  'Expand templates using string.Template().'

  def __init__(self):
    super().__init__()

  def expandss(self, env, tmpl):
    return Template(tmpl).substitute(env)

  def expandsf(self, env, tmpl, dst, encoding=None):
    with open(dst, 'w', encoding=encoding) as fd:
      fd.write(Template(tmpl).substitute(env))
