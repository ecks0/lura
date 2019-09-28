import logging
import logging.config
import os
import time
from collections import defaultdict
from io import StringIO
from lura.attrs import attr

class ExtraInfoFilter(logging.Filter):
  '''
  Provides additional fields to log records:

  - `short_name` a reasonably short name
  - `shortest_name` the shortest reasonably useful name
  - `short_levelname` a symbol associated with a level
  - `run_time` number of seconds the logging system has been initialized
  '''

  initialized = time.time()

  map_short_level = defaultdict(
    lambda: '=',
    DEBUG    = '+',
    INFO     = '|',
    WARNING  = '>',
    ERROR    = '*',
    CRITICAL = '!',
  )

  def filter(self, record):
    _ = record.name.split('.')
    record.short_name = '.'.join(_[-2:])
    record.shortest_name = _[-1]
    record.short_levelname = self.map_short_level.get(record.levelname)
    record.run_time = time.time() - self.initialized
    return True

class MultiLineFormatter(logging.Formatter):
  '''
  Format messages containing lineseps as though each line were a log
  message.
  '''

  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)

  def format(self, record):
    if not isinstance(record.msg, str) or os.linesep not in record.msg:
      record.message = super().format(record)
      return record.message
    msg = record.msg
    with StringIO() as buf:
      for line in record.msg.split(os.linesep):
        record.msg = line
        buf.write(super().format(record) + os.linesep)
      record.message = buf.getvalue().rpartition(os.linesep)[0]
    record.msg = msg
    return record.message

class Logging:
  '''
  An API for the configuration and maintenance of an application's or
  library's root logger.

  `MultiLineFormatter` and `ExtraInfoFilter` are used by default.
  '''

  # for convenience
  NOTSET   = logging.NOTSET
  DEBUG    = logging.DEBUG
  INFO     = logging.INFO
  WARNING  = logging.WARNING
  WARN     = logging.WARN
  ERROR    = logging.ERROR
  CRITICAL = logging.CRITICAL
  FATAL    = logging.FATAL

  # log format presets
  formats = attr(
    bare    = '%(message)s',
    classic = '%(asctime)s %(levelname)-8s %(short_name)s %(message)s',
    hax     = '%(run_time)-8.3f %(short_name)19s %(short_levelname)s %(message)s',
    runtime = '%(run_time)-12.3f %(message)s',
    verbose = '%(asctime)s %(run_time)12.3f %(name)s %(short_levelname)s %(message)s',
  )

  default_datefmt = '%Y-%m-%d %H:%M:%S'

  def __init__(
    self,
    std_logger,
    std_format = None,
    std_datefmt = None,
  ):
    super().__init__()
    self.std_logger = std_logger
    self.std_format = std_format or self.formats.bare
    self.std_datefmt = std_datefmt or self.default_datefmt
    self.config = None
    self.configure()

  def configure(self):
    if self.config is not None:
      return
    self._config_logging()
    self._config_levels()

  def _config_logging(self):
    self.config = self._build_config()
    logging.config.dictConfig(self.config)
    for level, name in logging._levelToName.items():
      setattr(logging.Logger, name, level)

  def _config_levels(self):
    if 'NOISE' not in logging._levelToName.values():
      self.add_level('NOISE', 5, ':')

  def _build_config(self):
    import yaml
    config = yaml.safe_load(f'''
      version: 1
      disable_existing_loggers: false
      filters:
        short_name: {{}}
      formatters:
        standard:
          format: '{self.std_format}'
          datefmt: '{self.std_datefmt}'
      handlers:
        stderr:
          class: logging.StreamHandler
          stream: ext://sys.stderr
          filters: ['short_name']
          formatter: standard
      loggers:
        {self.std_logger}:
          handlers: ['stderr']
          level: INFO
    ''')
    config['filters']['short_name']['()'] = ExtraInfoFilter
    config['formatters']['standard']['()'] = MultiLineFormatter
    return config

  def _build_logger_log_method(self, level):
    def log_level(self, msg, *args, **kwargs):
      if self.isEnabledFor(level):
        self._log(level, msg, args, **kwargs)
    return log_level

  def get_logger(self, name=None):
    return logging.getLogger(name or self.std_logger)

  getLogger = get_logger

  def get_level(self):
    'Get standard logger log level.'

    return self.get_logger().getEffectiveLevel()

  def set_level(self, level):
    'Set standard logger log level.'

    if isinstance(level, str):
      level = getattr(self, level.upper())
    logger = self.get_logger()
    logger.setLevel(level)

  def get_level_name(self, number):
    return logging._levelToName[number]

  def add_level(self, name, number, short_name=None):
    if number in logging._levelToName.keys():
      msg = 'Log level number {} already used by {}'
      raise ValueError(msg.format(number, self.get_level_name(number)))
    elif name in logging._levelToName.values():
      raise ValueError(f'Log level name {name} already in use')
    logging.addLevelName(number, name)
    setattr(logging, name, number)
    setattr(logging.Logger, name, number)
    setattr(type(self), name, number)
    setattr(
      logging.Logger, name.lower(), self._build_logger_log_method(number))
    if short_name is not None:
      ExtraInfoFilter.map_short_level[name] = short_name

  def set_format(self, format, datefmt=None, logger=None):
    'Sets the format for all handlers of a logger.'

    datefmt = datefmt or self.default_datefmt
    logger = logger or self.std_logger
    logger = self.get_logger(logger)
    formatter = MultiLineFormatter(format, datefmt)
    for handler in logger.handlers:
      handler.setFormatter(formatter)

  def add_file_handler(self, path, level=None, logger=None, append=True):
    logger = logger or self.std_logger
    if isinstance(path, str):
      if not append and os.path.isfile(path):
        os.unlink(path)
      handler = logging.FileHandler(path)
    else:
      handler = logging.StreamHandler(path)
    if level is not None:
      if isinstance(level, str):
        level = getattr(self, level)
      handler.setLevel(level)
    formatter = MultiLineFormatter(*self.formats.verbose)
    handler.setFormatter(formatter)
    handler.addFilter(ExtraInfoFilter())
    self.get_logger(logger).addHandler(handler)
    return handler

  def remove_handler(self, handler, logger=None):
    logger = logger or self.std_logger
    self.get_logger(logger).removeHandler(handler)

def method_for_level(self, level):
  # FIXME it works but could use some love
  name = logging._levelToName[level].lower()
  return getattr(self, name)

logging.Logger.method_for_level = method_for_level
logging.Logger.__getitem__ = method_for_level
