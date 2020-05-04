import ast
import io
import csv as pycsv
from typing import Any, Callable, Optional, Mapping, Sequence, TextIO, cast

class Csv:
  '''
  Csv format with type inference.

  Load support is implemented by `csv.DictReader`.

  Dump functions are currently not implemented.

  Load-time type inference is implemented by `ast.literal_eval()` and can
  be disabled:

  1. for all fields by passing infer=False to the load function
  2. for a particular field by passing a type conversion callable for the
     field via `typemap` (e.g. `lambda _: _` to return the naked value).
  '''

  def loads(
    self,
    data: str,
    **kwargs: Any
  ) -> Sequence[Mapping[str, Any]]:

    with io.StringIO(data) as buf:
      return self.loadfd(buf, **kwargs)

  def loadf(
    self,
    path: str,
    encoding: Optional[str] = None,
    **kwargs: Any
  ) -> Sequence[Mapping[str, Any]]:

    with open(path, 'r', encoding=encoding) as fd:
      return self.loadfd(fd, **kwargs)

  def loadfd(
    self,
    fd: TextIO,
    **kwargs: Any
  ) -> Sequence[Mapping[str, Any]]:
  
    infer = cast(bool, kwargs.get('infer', True))
    typemap = cast(Mapping[str, Callable], kwargs.get('typemap', {}))
    fieldnames = cast(Sequence[str], kwargs.get('fieldnames', []))
    restkey = cast(Optional[str], kwargs.get('restkey'))
    restval = cast(Optional[str], kwargs.get('restval'))
    dialect = cast(str, kwargs.get('dialect', 'excel'))
    reader = pycsv.DictReader(
      fd, fieldnames=fieldnames, restkey=restkey, restval=restval, dialect=dialect)
    rows = []
    for row in reader:
      for field in row:
        row[field] = self._value(field, row[field], infer, typemap)
      rows.append(row)
    return rows

  def dumps(
    self,
    data: Any,
    **kwargs: Any,
  ) -> str:
    
    raise NotImplementedError()

  def dumpf(
    self,
    path: str,
    data: Any,
    encoding: Optional[str] = None,
    **kwargs: Any
  ) -> None:
  
    raise NotImplementedError()

  def dumpfd(
    self,
    fd: TextIO,
    data: Any,
    **kwargs: Any
  ) -> None:
  
    raise NotImplementedError()

  def _value(
    self,
    name: str,
    value: Any,
    infer: bool,
    typemap: Mapping[str, Callable]
  ) -> Any:

    if typemap and name in typemap:
      # always use the mapped type if present
      return typemap[name](value)
    if not infer:
      # return the naked value if not inferring
      return value
    try:
      # evaluate the value as a literal
      return ast.literal_eval(value)
    except (ValueError, SyntaxError):
      # return the naked value if it can't be eval'd
      return value
