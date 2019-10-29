import logging
from lura import logutils

logutils.configure(
  package = __name__,
  format = logutils.formats.daemon,
  level = logging.WARN,
)

del logging
del logutils
