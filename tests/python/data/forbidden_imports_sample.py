import enum as en
from dataclasses import dataclass
from datetime import date
from datetime import datetime

do_something_with_date = date(2023, 1, 1)
do_something_with_datetime = datetime(2023, 1, 1, 1, 1)
do_something_with_dataclass = dataclass()
do_something_with_enum = en.Enum('foo', 'bar')
