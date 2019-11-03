import logging
import logging.config
import os
import sys
import time
import traceback
import yaml
from collections import defaultdict
from io import StringIO
from lura.attrs import attr

#####
## handy values

# log format presets (these depend on ExtraInfoFilter)
formats = attr(
  bare    = '%(message)s',
  runtime = '%(x_runtime)-12.3f %(message)s',
  user    = '%(x_runtime)-8.3f %(x_char)s %(message)s',
  hax     = '%(x_runtime)-8.3f %(x_modules)20s %(x_char)s %(message)s',
  daemon  = '%(asctime)s %(x_module)10s %(x_char)s %(message)s',
  verbose = '%(asctime)s %(x_runtime)12.3f %(name)s %(x_char)s %(message)s',
)

logging.formats = formats

default_datefmt = '%Y-%m-%d %H:%M:%S'

#####
## utility classes

class ExtraInfoFilter(logging.Filter):
  '''
  Provides additional fields to log records:

  - modules - 'parent_module.calling_module'
  - module - 'calling_module'
  - runtime - number of seconds this class has been loaded as float
  - char - a single character uniquely identifying the log level
  '''

  initialized = time.time()
  default_char = ' '
  name_to_char = defaultdict(
    lambda: default_char,
    DEBUG    = '+',
    INFO     = '|',
    WARNING  = '>',
    ERROR    = '*',
    CRITICAL = '!',
  )

  def filter(self, record):
    modules = record.name.split('.')
    record.x_modules = '.'.join(modules[-2:])
    record.x_module = modules[-1]
    record.x_char = self.name_to_char.get(record.levelname)
    record.x_runtime = time.time() - self.initialized
    return True

class MultiLineFormatter(logging.Formatter):
  '''
  Format messages containing lineseps as though each line were a log
  message.
  '''

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

class Logger(logging.getLoggerClass()):
  '''
  Logger subclass with the following changes:

  - __getitem__(log_level) -> callable log method for log_level
  - setConsoleFormat(format, datefmt) will set the format for any stream
    handler writing to stdout or stderr
  - log level constants are set on the class, and will be updated by
    logutils.add_level()
  - exceptions are sent through formatters rather than being printed
    bare
  '''

  def __getitem__(self, level):
    'Return the log method for the given log level number.'

    name = logging._levelToName[level].lower()
    return getattr(self, name)

  def setConsoleFormat(self, format, datefmt=None):
    'Set the output format on any handler for stdout or stderr.'

    datefmt = datefmt or default_datefmt
    formatter = MultiLineFormatter(format, datefmt)
    std = (sys.stdout, sys.stderr)
    for handler in self.handlers:
      if hasattr(handler, 'stream') and handler.stream in std:
        handler.setFormatter(formatter)

  def _log(self, level, msg, *args, exc_info=None, **kwargs):
    if exc_info:
      if isinstance(exc_info, BaseException):
        exc_info = (type(exc_info), exc_info, exc_info.__traceback__)
      else:
        exc_info = sys.exc_info()
      tb = ''.join(traceback.format_exception(*exc_info)).rstrip()
      super()._log(level, msg, *args, **kwargs)
      super()._log(level, tb, *args, **kwargs)
    else:
      super()._log(level, msg, *args, **kwargs)

for level, name in logging._levelToName.items():
  setattr(Logger, name, level)

logging.setLoggerClass(Logger)

#####
## utilities

def number_for_name(name):
  return logging._nameToLevel[name]

def name_for_number(number):
  return logging._levelToName[number]

def build_log_method(number):
  def log_level(self, *args, **kwargs):
    if self.isEnabledFor(number):
      self._log(number, msg, args, **kwargs)
  return log_level

def add_level(self, name, number, char=None):
  '''
  Add a log level.

  - Sets the attribute `name` to `number` on module `logging`
  - Sets the attribute `name` to `number` on type `logging.Logging`
  - Creates a log method for the level and sets it on `logging.Logging` as
    attribute `name.lower()`
  - Sets `char` for `name` on `ExtraInfoFilter` when provided
  '''

  if name in logging._nameToLevel:
    raise ValueError(f'Level name {name} already in use')
  if number in logging._levelToName:
    raise ValueError(f'Level number {number} already in use')
  if char is not None:
    if char in ExtraInfoFilter.name_to_char.values():
      raise ValueError(f'Level char {char} already in use')
  logging.addLevelName(number, name)
  setattr(logging, name, number)
  setattr(Logger, name, number)
  setattr(Logger, name.lower(), build_log_method(number))
  if char is not None:
    ExtraInfoFilter.name_to_char[name] = char

#####
## logging configurator

class Configurator:
  '''
  Build and apply a dictConfig using features of `lura.logutils`.

  - Creates a filter `extra_info` as `ExtraInfoFilter`
  - Creates a formatter `multiline` as `MultiLineFormatter` using `format`
    and `datefmt`
  - Creates a handler 'stderr` as `StreamHandler` for `sys.stderr` using the
    `extra_info` filter and the `multiline` formatter
  - Sets the `level` and `stderr` handler for a package's root logger
  '''

  def __init__(self, package, format, datefmt, level=logging.INFO):
    super().__init__()
    self.package = package
    self.format = format
    self.datefmt = datefmt or default_datefmt
    self.level = level

  def yaml(self, str):
    return yaml.safe_load(str)

  @property
  def filters(self):
    filters = self.yaml('''
      extra_info: {}
    ''')
    filters['extra_info']['()'] = ExtraInfoFilter
    return filters

  @property
  def formatters(self):
    formatters = self.yaml(f'''
      multiline:
        format: '{self.format}'
        datefmt: '{self.datefmt}'
    ''')
    formatters['multiline']['()'] = MultiLineFormatter
    return formatters

  @property
  def handlers(self):
    return self.yaml('''
      stderr:
        class: logging.StreamHandler
        stream: ext://sys.stderr
        filters: [extra_info]
        formatter: multiline
    ''')

  @property
  def loggers(self):
    return self.yaml(f'''
      {self.package}:
        handlers: [stderr]
        level: {name_for_number(self.level)}
    ''')

  @property
  def config(self):
    config = self.yaml('''
      version: 1
      disable_existing_loggers: false
    ''')
    config['filters'] = self.filters
    config['formatters'] = self.formatters
    config['handlers'] = self.handlers
    config['loggers'] = self.loggers
    return config

  def configure(self):
    logging.config.dictConfig(self.config)

def configure(package, format, datefmt=None, level=logging.INFO):
  Configurator(package, format, datefmt, level=level).configure()
