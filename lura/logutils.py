'''
Logging helper utilities.

Features:

- A filter to provide additional log message formatting fields.

- Pre-defined log formats using additional log message formatting fields.

- Helpers to retrieve log levels by name or by number.

- Helper to add new log levels.

- Package-level configurator with reasonable defaults.

- Custom Logger implementation

  - Each line of a multi-line log message is itself treated as an independent
    log message.

  - Exceptions are sent through formatters rather than being printed bare.

  - setConsoleFormat() method to set log formats for all stream handlers
    writing to stdout or stderr.
  
  - Log level constants are set on the class.
'''

import logging
import logging.config
import os
import sys
import time
import traceback
import yaml as pyyaml
from collections import defaultdict
from io import StringIO
from lura.attrs import attr
from types import TracebackType
from typing import (
  Any, Callable, Dict, Mapping, MutableMapping, Optional, Tuple, Type, Union
)

#####
## handy values

def getLogger(name: str) -> logging.Logger:
  return logging.getLogger(name)

ExcInfo = Union[Tuple[Type[BaseException], BaseException, TracebackType], Tuple[None, None, None]]

# log format presets (these depend on ExtraInfoFilter)
formats = attr(
  bare    = '%(message)s',
  runtime = '%(x_runtime)-12.3f %(message)s',
  user    = '%(x_runtime)-8.3f %(x_char)s %(message)s',
  hax     = '%(x_runtime)-8.3f %(x_modules)20s %(x_char)s %(message)s',
  daemon  = '%(asctime)s %(x_module)10s %(x_char)s %(message)s',
  verbose = '%(asctime)s %(x_runtime)12.3f %(name)s %(x_char)s %(message)s',
)

logging.formats = formats # type: ignore

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
  name_to_char: MutableMapping[int, str] = defaultdict(
    lambda: default_char, # type: ignore
    DEBUG    = '+',
    INFO     = '|',
    WARNING  = '>',
    ERROR    = '*',
    CRITICAL = '!',
  )

  def filter(self, record: logging.LogRecord) -> bool:
    modules = record.name.split('.')
    record.x_modules = '.'.join(modules[-2:]) # type: ignore
    record.x_module = modules[-1] # type: ignore
    record.x_char = self.name_to_char.get(record.levelname) # type: ignore
    record.x_runtime = time.time() - self.initialized # type: ignore
    return True

class MultiLineFormatter(logging.Formatter):
  '''
  Format messages containing lineseps as though each line were a log
  message.
  '''

  def format(self, record: logging.LogRecord) -> str:
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

class Logger(logging.getLoggerClass()): # type: ignore
  '''
  Logger subclass with the following changes:

  - __getitem__(log_level) -> callable log method for log_level

  - setConsoleFormat(format, datefmt) will set the format for any stream
    handler writing to stdout or stderr

  - log level constants are set on the class, and will be updated by
    logutils.add_level()

  - exceptions are sent through formatters rather than printed bare
  '''

  def __getitem__(self, level: int) -> Callable:
    'Return the log method for the given log level number.'

    name = logging._levelToName[level].lower()
    return getattr(self, name)

  def setConsoleFormat(self, format: str, datefmt: Optional[str] = None) -> None:
    'Set the output format on any handler for stdout or stderr.'

    datefmt = datefmt or default_datefmt
    formatter = MultiLineFormatter(format, datefmt)
    std = (sys.stdout, sys.stderr)
    for handler in self.handlers:
      if hasattr(handler, 'stream') and handler.stream in std:
        handler.setFormatter(formatter)

  def _log(
    self,
    level: int,
    msg: str,
    *args: Any,
    exc_info: Optional[ExcInfo] = None,
    **kwargs: Any
  ) -> None:
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

def number_for_name(name: str) -> int:
  return logging._nameToLevel[name]

def name_for_number(number: int) -> str:
  return logging._levelToName[number]

def build_log_method(number) -> Callable:
  '''
  Build a log method for a log level to be dynamically added to
  logutils.Logger.
  '''

  def log_method(self, *args: Any, **kwargs: Any):
    if self.isEnabledFor(number):
      self._log(*args, **kwargs)
  return log_method

def add_level(name: str, number: int, char: Optional[str] = None) -> None:
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
    ExtraInfoFilter.name_to_char[number] = char

#####
## application-level configurator

def yaml(string: str):
  return pyyaml.safe_load(string)

class Configurator:
  '''
  Build and apply a logging dictConfig using features of logutils.

  - Creates a filter `extra_info` as `ExtraInfoFilter`

  - Creates a formatter `multiline` as `MultiLineFormatter` using `format`
    and `datefmt`

  - Creates a handler 'stderr` as `StreamHandler` for `sys.stderr` using the
    `extra_info` filter and the `multiline` formatter

  - Sets the `level` and `stderr` handler for a package's root logger
  '''

  package: str
  format: str
  datefmt: str
  level: int

  def __init__(
    self,
    package: str,
    format: str,
    datefmt: str,
    level: int = logging.INFO
  ) -> None:

    super().__init__()
    self.package = package
    self.format = format
    self.datefmt = datefmt
    self.level = level

  @property
  def filters(self) -> Dict[str, Any]:
    filters = yaml('extra_info: {}')
    filters['extra_info']['()'] = ExtraInfoFilter
    return filters

  @property
  def formatters(self) -> Dict[str, Any]:
    formatters = yaml(f'''
      multiline:
        format: '{self.format}'
        datefmt: '{self.datefmt}'
    ''')
    formatters['multiline']['()'] = MultiLineFormatter
    return formatters

  @property
  def handlers(self) -> Dict[str, Any]:
    return yaml('''
      stderr:
        class: logging.StreamHandler
        stream: ext://sys.stderr
        filters: [extra_info]
        formatter: multiline
    ''')

  @property
  def loggers(self) -> Dict[str, Any]:
    return yaml(f'''
      {self.package}:
        handlers: [stderr]
        level: {name_for_number(self.level)}
    ''')

  @property
  def config(self) -> Dict[str, Any]:
    config = yaml('''
      version: 1
      disable_existing_loggers: false
    ''')
    config['filters'] = self.filters
    config['formatters'] = self.formatters
    config['handlers'] = self.handlers
    config['loggers'] = self.loggers
    return config

  def configure(self) -> None:
    logging.config.dictConfig(self.config)

def configure(
  package: str,
  format: str = formats.hax,
  datefmt: str = default_datefmt,
  level: int = logging.INFO
) -> logging.Logger:
  Configurator(package, format, datefmt, level=level).configure()
  return logging.getLogger(package)
