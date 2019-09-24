from abc import abstractmethod

class Expander:

  def __init__(self, *args, **kwargs):
    super().__init__()

  def bind(self, env):
    return BoundExpander(self, env)

  @abstractmethod
  def expandss(self, env, tmpl):
    'Expand a `str` to a `str`.'

    pass

  @abstractmethod
  def expandsf(self, env, tmpl, dst, encoding=None):
    'Expand a `str` to a file.'

    pass

  def expandfs(self, env, src, encoding=None):
    'Expand a file to a `str`.'

    with open(src, 'r', encoding=encoding) as fd:
      tmpl = fd.read()
    return self.expandss(env, tmpl)

  def expandff(self, env, src, dst, encoding=None):
    'Expand a file to a file.'

    with open(src, 'r', encoding=encoding) as fd:
      tmpl = fd.read()
    self.expandsf(env, tmpl, dst, encoding=encoding)

class BoundExpander:
  'Binds an expander to an environment.'

  def __init__(self, expander, env):
    super().__init__()
    self.expander = expander
    self.env = env

  def expandss(self, tmpl):
    return self.expander.expandss(self.env, tmpl)

  def expandsf(self, tmpl, dst):
    return self.expander.expandsf(self.env, tmpl, dst)

  def expandfs(self, src):
    return self.expander.expandfs(self.env, src)

  def expandff(self, src, dst):
    return self.expander.expandff(self.env, src, dst)
