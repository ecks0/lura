import yaml as yaml_
from lura.attrs import ottr
from lura.fmt import myaml
from lura.fmt.base import Format
from lura.io import dump

class DictLoaderMixin:
  'Yaml loader mixin which uses a user-defined dict type.'

  def __init__(self, dict_type):
    object.__init__(self)
    self.dict_type = dict_type

  def construct_yaml_map(self, node):
    data = self.dict_type()
    yield data
    value = self.construct_mapping(node)
    data.update(value)

  def construct_mapping(self, node, deep=False):
    if not isinstance(node, yaml_.MappingNode):
      msg = f'Expected MappingNode but found {node.id}'
      raise yaml_.constructor.ConstructError(None, None, msg, node.start_mark)
    self.flatten_mapping(node)
    mapping = self.dict_type()
    for key_node, value_node in node.value:
      key = self.construct_object(key_node, deep=deep)
      try:
        hash(key)
      except TypeError as exc:
        raise yaml_.constructor.ConstructError(
          'While building mapping',
          node.start_mark,
          f'found unhashable key ({exc})',
          key_node.start_mark,
        )
      value = self.construct_object(value_node, deep=deep)
      mapping[key] = value
    return mapping

class Loader(DictLoaderMixin, yaml_.Loader):

  default_dict_type = ottr

  def __init__(self, *args, **kwargs):
    yaml_.Loader.__init__(self, *args, **kwargs)
    DictLoaderMixin.__init__(self, self.default_dict_type)
    self.add_constructor(
      'tag:yaml.org,2002:map', type(self).construct_yaml_map
    )
    self.add_constructor(
      'tag:yaml.org,2002:omap', type(self).construct_yaml_map
    )

class SafeLoader(DictLoaderMixin, yaml_.SafeLoader):

  default_dict_type = ottr

  def __init__(self, *args, **kwargs):
    yaml_.SafeLoader.__init__(self, *args, **kwargs)
    DictLoaderMixin.__init__(self, self.default_dict_type)
    self.add_constructor(
      'tag:yaml.org,2002:map', type(self).construct_yaml_map
    )
    self.add_constructor(
      'tag:yaml.org,2002:omap', type(self).construct_yaml_map
    )

# These dumpers are included for completeness, but are not currently used.
# The myaml module is used for dumping data structures as yaml.

class DictDumperMixin:
  'Yaml dumper mixin which uses a user-defined dict type.'

  def __init__(self):
    object.__init__(self)

  def represent_custom_dict(self, data):
    return self.represent_mapping('tag:yaml.org,2002:map', data.iteritems())

class Dumper(DictDumperMixin, yaml_.Dumper):

  default_dict_type = ottr

  def __init__(self, *args, **kwargs):
    yaml_.Dumper.__init__(self, *args, **kwargs)
    DictDumperMixin.__init__(self)
    self.add_representer(
      self.default_dict_type, type(self).represent_custom_dict
    )

class SafeDumper(DictDumperMixin, yaml_.SafeDumper):

  default_dict_type = ottr

  def __init__(self, *args, dict_type=ottr, **kwargs):
    yaml_.SafeDumper.__init__(self, *args, **kwargs)
    DictDumperMixin.__init__(self, dict_type)
    self.add_representer(
      self.default_dict_type, type(self).represent_custom_dict
    )

class Yaml(Format):
  '''
  Thin wrapper for yaml. This class configures the yaml module to use
  ordered dictionaries for backing dicts, prints yaml which is more
  human-readable, and auto-quotes fields containing ``{{`` and ``}}``
  for compatibility with Ansible.
  '''

  # This class uses a modified version of the myaml module to implement
  # the dump*() methods.

  def loads(self, data):
    'Load yaml from string ``data``.'

    return yaml_.load(data, Loader=Loader)

  def loadf(self, src):
    'Load yaml from file ``src``.'

    with open(src, encoding='utf-8') as fd:
      return self.loads(fd.read())

  def dumps(self, data):
    'Return dict ``data`` as yaml.'

    return myaml.dump(data)

  def dumpf(self, data, dst, encoding='utf-8'):
    'Write dict ``data`` as yaml to file ``dst`` using ``encoding``.'

    return dump(dst, myaml.dump(data), encoding=encoding)

  def dumpfd(self, data, fd):
    'Write dict ``data`` as yaml to file descriptor ``fd``.'

    fd.write(self.dumps(data))
    if hasattr(fd, 'flush') and callable(fd.flush):
      fd.flush()
