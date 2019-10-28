from .log import Logging

logs = Logging(
  std_logger = __name__,
  std_format = Logging.formats.hax,
  std_level  = Logging.INFO,
)

del Logging

from .run import run
