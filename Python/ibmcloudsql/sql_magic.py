# ------------------------------------------------------------------------------
# Copyright IBM Corp. 2020
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ------------------------------------------------------------------------------

import sqlparse
from functools import wraps
import re
try:
    from exceptions import UnsupportedStorageFormatException
except Exception:
    from .exceptions import UnsupportedStorageFormatException

def format_sql(sql_stmt):
    """format SQL string to ensure proper content for string comparison

    Parameters
    ----------
    sql_stmt: str
    """
    url = re.search(r'(cos)://[^\s]*', sql_stmt)
    mapping = {}
    key_template = "key_{num}"
    index = 0
    while url:
        key = key_template.format(num=index)
        mapping[key] = url.group(0)
        sql_stmt = re.sub(r'(cos)://[^\s]*',
                          "{" + key + "}",
                          sql_stmt.rstrip(),
                          count=1)
        url = re.search(r'(cos)://[^\s]*', sql_stmt)
        index = index + 1
    sql_stmt = sqlparse.format(
        sql_stmt,
        keyword_case="upper",
        strip_comments=True,
        reindent=True,
    )
    sql_stmt = sql_stmt.format(**mapping)
    return sql_stmt

def print_sql(sql_stmt):
    print(format_sql(sql_stmt))

class TimeSeriesTransformInput():
    """
    This class contains methods that supports the transformation of a user-friendly arguments in time-series functions
    to IBM CloudSQL compatible values.
    """
    @classmethod
    def transform_sql(cls, f):
        """
        Generate SQL string

        Notes
        -----
        Syntax: https://cloud.ibm.com/docs/sql-query
        """
        @wraps(f)
        def wrapped(*args, **kwargs):
            self = args[0]
            self._sql_stmt = TimeSeriesTransformInput.ts_segment_by_time(self._sql_stmt)
            result = f(*args, **kwargs)
            return result
        return wrapped

    @classmethod
    def ts_segment_by_time(cls, sql_stmt):
        """
        Revise arguments of TS_SEGMENT function to comply with IBM CloudSQL

        Notes
        -----
        The TS_SEGMENT supported by IBM CloudSQL accepts value in number, which is not user-friendly
        for units like hour, days, minutes. SQLMagic alllows constructing SQL query string using
        the below values.

        1. values: `per_hour`, `hour`, `per_day`, `day`, `per_week`, `week`

        .. code-block:: console

            ts_segment_by_time(ts, per_hour, per_hour)
            ts_segment_by_time(ts, hour, hour)

        2. or values: using  ISO 8601 https://en.wikipedia.org/wiki/ISO_8601#Durations
            P[n]Y[n]M[n]DT[n]H[n]M[n]S or P[n]W

        Examples
        --------

        .. code-block:: python

            ts_segment_by_time(ts, PT1H, PT1H)

        into

        .. code-block:: python

            ts_segment_by_time(ts, 3600000, 3600000)

        as ts_segment_by_time operates at mili-seconds level, hour=60*60*1000 miliseconds
        """
        sql_stmt = re.sub(r'ts_segment_by_time', 'TS_SEGMENT_BY_TIME', sql_stmt, flags=re.IGNORECASE)
        def handle_str_str(sql_stmt):
            h = re.compile(r'TS_SEGMENT_BY_TIME[\s]?\(([a-zA-Z0-9]+)[\s]?,[\s]?(?P<window>[a-zA-Z][a-zA-Z_0-9]+)[\s]?,[\s]?(?P<step>[a-zA-Z][a-zA-Z_0-9]+)', re.MULTILINE)
            return h
        def handle_str_number(sql_stmt):
            h = re.compile(r'TS_SEGMENT_BY_TIME[\s]?\(([a-zA-Z0-9]+)[\s]?,[\s]?(?P<window>[a-zA-Z][a-zA-Z_0-9]+)[\s]?,[\s]?(?P<step>[0-9]+)', re.MULTILINE)
            return h
        def handle_number_str(sql_stmt):
            h = re.compile(r'TS_SEGMENT_BY_TIME[\s]?\(([a-zA-Z0-9]+)[\s]?,[\s]?(?P<window>[0-9]+)[\s]?,[\s]?(?P<step>[a-zA-Z][a-zA-Z_0-9]+)', re.MULTILINE)
            return h
        def handle_result(h, sql_stmt):
            result = h.search(sql_stmt)
            while result:
                start_end = {}
                num = {}
                for i in [2, 3]:
                    if not result.group(i).isdigit():
                        if result.group(i).strip().lower() in ["per_hour", "hour"]:
                            num[i] = 60
                        elif result.group(i).strip().lower() in ["per_day", "day"]:
                            num[i] = 60*24
                        elif result.group(i).strip().lower() in ["per_week", "week"]:
                            num[i] = 60*24*7
                        else:
                            try:
                                import isodate
                                x = isodate.parse_duration(result.group(i).strip())
                                num[i] = int(x.total_seconds()/60)  # (minute)
                            except ISO8601Error:
                                print("%s unsupported" % result.group(i))
                                assert(0)
                        num[i] = num[i] * 60 * 1000 # (milliseconds)
                    else:
                        num[i] = result.group(i)
                    start_end[i] = result.span(i)
                sql_stmt = sql_stmt[:start_end[2][0]] + str(num[2]) + sql_stmt[start_end[2][1]:start_end[3][0]] + \
                    str(num[3]) +  sql_stmt[start_end[3][1]:]
                result = h.search(sql_stmt)
            return sql_stmt

        h = handle_str_str(sql_stmt)
        sql_stmt = handle_result(h, sql_stmt)
        h = handle_number_str(sql_stmt)
        sql_stmt = handle_result(h, sql_stmt)
        h = handle_str_number(sql_stmt)
        sql_stmt = handle_result(h, sql_stmt)
        return sql_stmt

class TimeSeriesSchema():
    """
    The class tracks the columns that is useful in time-series handling.
    Currently, it tracks column names whose values are in UNIX time format
    """
    def __init__(self):
        # the list of column in unix-tme format
        """9999999999999 (13 digits) means Sat Nov 20 2286 17:46:39 UTC
        999999999999 (12 digits) means Sun Sep 09 2001 01:46:39 UTC
        99999999999 (11 digits) means Sat Mar 03 1973 09:46:39 UTC
        100000000000000 (15 digits) means Wed Nov 16 5138 09:46:40
        https://stackoverflow.com/questions/23929145/how-to-test-if-a-given-time-stamp-is-in-seconds-or-milliseconds
        """
        self._unixtime_columns = []

    @property
    def columns_in_unixtime(self ):
        """Return the name of columns whose values are in UNIX timestamp"""
        return self._unixtime_columns
    @columns_in_unixtime.setter
    def columns_in_unixtime(self, column_list):
        """Assign the name of columns whose values are in UNIX timestamp"""
        self._unixtime_columns = column_list


class SQLMagic(TimeSeriesSchema):
    """
    The class supports constructing a full SQL query statement

    """

    def __init__(self):
        super().__init__()
        # contain the sql string that we can evoke using run() or submit()
        self._sql_stmt = ""
        self._has_stored_location = False
        self._has_with_clause = False
        self._has_select_clause = False
        self.supported_format_types = ["PARQUET", "CSV", "JSON"]
        self._has_from_clause = False

    def print_sql(self):
        """print() sql string"""
        print_sql(self.get_sql())

    @TimeSeriesTransformInput.transform_sql
    def get_sql(self):
        """Return the current sql string"""
        return format_sql(self._sql_stmt)

    def reset_(self):
        """Reset and returns the current sql string"""
        res = self.get_sql()
        self._sql_stmt = ""
        self._has_stored_location = False
        self._has_with_clause = False
        self._has_select_clause = False
        self._has_from_clause = False
        return res

    def with_(self, table_name, sql_stmt):
        """WITH <table> AS <sql> [, <table AS <sql>]"""
        if "WITH" not in self._sql_stmt:
            self._sql_stmt = self._sql_stmt + " WITH " + table_name + " AS (" + sql_stmt  + "\n) "
            self._has_with_clause = True
        else:
            self._sql_stmt = self._sql_stmt + ", " + table_name + " AS (" + sql_stmt  + "\n) "
        return self

    def select_(self,  columns):
        """
        SELECT <columns>

        Parameters
        ---------------
        columns: str
            a string representing a comma-separated list of columns
        """
        assert(self._has_select_clause is False)
        self._sql_stmt = self._sql_stmt + "SELECT " + columns
        self._has_select_clause = True
        return self

    def from_table_(self, table, alias=None):
        """
        FROM <table> [AS alias] [, <table> [AS alias]]
        """
        if self._has_from_clause:
            self._sql_stmt += ", "
        else:
            self._sql_stmt += " FROM "
        self._sql_stmt += table
        if alias:
            # NOTE: it's ok for not using 'AS'
            # self._sql_stmt += " AS " + alias.strip()
            self._sql_stmt += " " + alias.strip()
        self._has_from_clause = True
        return self

    def from_cos_(self, cos_url, format_type="parquet", alias=None):
        """
        FROM <cos-url> AS type [AS alias] [, <cos-url> AS type [AS alias]]
        """
        if self._has_from_clause:
            self._sql_stmt += ", "
        else:
            self._sql_stmt += " FROM "
        self._sql_stmt += cos_url + " STORED AS " + format_type.strip()
        if alias:
            self._sql_stmt += " " + alias.strip()
        self._has_from_clause = True
        return self

    def from_view_(self, sql_stmt):
        """
        FROM (<sql>)
        """
        self._sql_stmt = self._sql_stmt + " FROM  ( \n" + sql_stmt + " \n) "
        return self

    def where_(self, condition):
        """
        WHERE <condition> [, <condition>]
        """
        if "WHERE" not in self._sql_stmt:
            self._sql_stmt = self._sql_stmt + " WHERE " + condition
        else:
            self._sql_stmt = self._sql_stmt + ", " + condition
        self._has_from_clause = False
        return self

    def join_cos_(self, cos_url, condition, type="inner", alias=None):
        """
        [type] JOIN <cos-url> [AS alias]
        """
        table = cos_url
        return self.join_table_(table, condition, type=type, alias=alias)

    def join_table_(self, table, condition, type="inner", alias=None):
        """
        [type] JOIN <table> [AS alias] ON <condition>

        NOTE: [type] is a value in the list below

        .. code-block:: python

            ["INNER", "CROSS", "OUTER", "LEFT", "LEFT OUTER", "LEFT SEMI",
            "RIGHT", "RIGHT OUTER", "FULL", "FULL OUTER", "ANTI", "LEFT ANTI"]
        """
        self.supported_join_types = ["INNER", "CROSS", "OUTER", "LEFT", "LEFT OUTER", "LEFT SEMI",
                "RIGHT", "RIGHT OUTER", "FULL", "FULL OUTER", "ANTI", "LEFT ANTI"]
        import re
        type = re.sub(' +', ' ', type)
        if type.upper() not in self.supported_join_types:
            msg = "Wrong 'type', use a value in " + str(self.supported_join_types)
            raise ValueError(msg)

        if alias is None:
            self._sql_stmt = self._sql_stmt + " " + type + " JOIN " + table + " ON " + condition
        else:
            self._sql_stmt = self._sql_stmt + " " + type + " JOIN " + table + " AS " + alias + " ON " + condition
        return self

    def order_by_(self, columns):
        """
        ORDER BY <columns>

        Parameters
        ---------------
        condition: str
            a string representing a comma-separated list of columns
        """
        self._sql_stmt = self._sql_stmt + " ORDER BY " + columns
        return self

    def group_by_(self, columns):
        """
        GROUP BY <columns>
        """
        if "GROUP BY" not in self._sql_stmt:
            self._sql_stmt = self._sql_stmt + " GROUP BY " + columns
        else:
            self._sql_stmt = self._sql_stmt + ", " + columns
        return self

    def store_at_(self, cos_url, format_type="CSV"):
        """
        INTO <cos-url> STORED AS <type>
        """
        if self._has_stored_location is False:
            self._sql_stmt = self._sql_stmt + " INTO " + cos_url
            self._has_stored_location = True
        else:
            assert(0)
        if len(format_type) > 0 and format_type.upper() in self.supported_format_types:
            self._sql_stmt = self._sql_stmt + " STORED AS " + format_type.upper()
        else:
            if format_type.upper() not in self.supported_format_types:
                raise UnsupportedStorageFormatException("ERROR: unsupported type {}".format(format_type))
        return self

    # def store_as_(self, format_type="parquet"):
    #     if "INTO " not in self._sql_stmt:
    #         self._sql_stmt = self._sql_stmt + " INTO {cos_out} STORED AS " + format_type.upper()
    #     else:
    #         self._sql_stmt = self._sql_stmt + " STORED AS " + format_type.upper()
    #     return self

    def partition_by_(self, columns):
        """
        PARTITIONED BY <columns>
        """
        if " PARTITION " not in self._sql_stmt and " PARTITIONED " not in self._sql_stmt:
            self._sql_stmt += " PARTITIONED BY " + str(columns)
        else:
            assert(0)
        return self

    def partition_objects_(self, num_objects):
        """
        PARTITIONED INTO <num>  OBJECTS
        """
        if "PARTITION" not in self._sql_stmt:
            self._sql_stmt = self._sql_stmt + " PARTITIONED INTO " + str(num_objects) + " OBJECTS"
        else:
            assert(0)
        return self

    def partition_rows_(self, num_rows):
        """
        PARTITIONED INTO <num> ROWS
        """
        if "PARTITION" not in self._sql_stmt:
            self._sql_stmt = self._sql_stmt + " PARTITIONED INTO " + str(num_rows) + " ROWS"
        else:
            assert(0)
        return self

    @TimeSeriesTransformInput.transform_sql
    def format_(self):
        """Perform string replacement needed so that the final result is a SQL statement that is accepted by IBM Spark SQL
        """
        return self
