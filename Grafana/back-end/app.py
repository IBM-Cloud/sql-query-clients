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
"""WSGI-based web app
(Python 3.8 compatible)

https://stackoverflow.com/questions/32799808/python-web-application-project-structure-and-docker-support

1. able to process and store connection to Cloud SQL server [json database file]
2. able to process `table` and `time-series` request and return data
3. handle empty request string
4. handle empty returned data
5. able to handle request in concurrent -> thread-specific or coroutine-specific sqlClient object
6. able to handle NaN data and convert to empty string before returning
7. support special functions: $__timeFilter() and $__timeFilter(aiops) -
   assumes the time column is a number, i.e. long type or timestamp type
8. allow caching based on `key` and sql_stmt
9. columns detection in SELECT statement:
    SELECT name
    SELECT fake as name
    SELECT ts_explode(...) AS (name1, name2)
10. support special functions: $__source (HIVE table and COS URL)
11. add streaming time-series and multi-times series: $__source_test(TS), $__source_test(MTS)
12. can handle multiple queries at once
13. handle 'hide=True' when user don't want to run a query
14. add 'get_result' option to allow not returning any result back - good for chained queries
15. add '--time-out' option [to pass in the value (in seconds) before timeout when
    the webapp is launched as a service in IBM CloudEngine for example]
16. add '--ssl' option [to run HTTPS Webserver]
17. support using $__source in CREATE TABLE statement
18. $__timeFilter(string) - now accept 'string' if the time colum is represented as a string
19. a 'time' column is now automatically converted to datetime - if it's stored in string
20. able to detect column name correctly even inside a nested SELECT statement [Feb 12, 2021]
21. able to detect and reject 'SELECT *'
22. add new macro: '$__timeFilterColumn(col-name, [type])' - user can explicitly specify
    the column containing timestamp-data, and need to provide its type
    (string or long/timestamp or empty) [Feb 12, 2021]

CHANGED BEHAVIOR:
    * [grafana] revise conf. setting so that $__source is optional - with tooltips to explain why user should provide
    * [grafana] add $__dest to use the default one - $__dest(csv): $__dest, $__dest(), $__dest(csv)
    $__dest(parquet), $__dest(arvo, a/b/c)
    * add $__source_prev, $__source_prev(), $__source_prev(A), $__source_prev(B) to refer to the
    data source as the output from a previous query, or a given query based on its `refId` A or B.
    * avoid re-create sqlClient in a panel with multiple queries
    * use status code 403, rather than 401, for error: newer Grafana 7.3.x for some reasons
    maps 401 to 400 and the original message is lost
    * check `should_sql_stmt_be_run` move to outside the loop --> faster for a panel
    with multiple queries
    (the check is not vigorous - sql is compared before any transformation done so that
    adjacent spaces are also considered)
    * HTTPS/SSL is added (--ssl)

code:

    $__dest[( format [, suffix] )]

TODO:
    * add the capability to reference to a variable - so that the dashboard can be udpated based on the
    value(s) user selected for that variable
    * add $__get_schema(hivetable), $__get_schema(COS://URL, format), $__get_schema($__source)

BUG fixes:
    1. when metrics name is not a string
"""
try:
    # A gevent-based server is actually not asynchronous, but massively multi-threaded.
    import gevent
    from gevent import monkey

    monkey.patch_all()
except:
    print("No concurrency")
    pass
import sys
from time import sleep
from bottle import Bottle, HTTPResponse, run, request, response, route, abort
from bottle import json_dumps
from calendar import timegm
from datetime import date, datetime
import math
import random
import os
import re
import regex
import numpy as np
from enum import Enum

import ibm_botocore

from IPython import embed

try:
    import cPickle as pickle
except ImportError:
    import pickle
from pandas.io.json import build_table_schema

import json
import sqlparse
from sqlparse.sql import IdentifierList, Identifier
from sqlparse.tokens import Keyword
import logging
import pandas as pd
import threading
from joblib import Memory


sys.path.insert(0, "../../Python/")
try:
    from cloud_utilities.sql_query import SQLClient
    from cloud_utilities.sql_magic import format_sql
    from cloud_utilities.cos import ParsedUrl
except ImportError:
    from ibmcloudsql.sql_query_ts import SQLClientTimeSeries as SQLClient
    from ibmcloudsql.sql_magic import format_sql
    from ibmcloudsql.cos import ParsedUrl
from ibmcloudsql.exceptions import (
    CosUrlNotFoundException,
    CosUrlInaccessibleException,
    SqlQueryCrnInvalidFormatException,
    RateLimitedException,
)


logger = logging.getLogger()
# since Python 3.3
logging.basicConfig(
    # level=logging.DEBUG,
    level=logging.INFO,
    format="%(asctime)s [%(threadName)-12.12s] [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler("debug.log"), logging.StreamHandler()],
)

DEBUG = False
MAX_TRIES = 100


def get_parser():
    import argparse

    parser = argparse.ArgumentParser(description="Process backend webapp")
    parser.add_argument(
        "--time-out",
        "-t",
        dest="time_out",
        help="the time-out of request in seconds (default: unlimited)",
    )
    parser.add_argument(
        "--ssl", dest="ssl", action="store_true", help="run as HTTPS web server"
    )

    args = parser.parse_args()
    return args


lock = threading.Lock()
lock_savejob = threading.Lock()

# command-line argument
cmd_args = get_parser()

cachedir = "_cache_dir"
memory = Memory(cachedir, verbose=0)


def query_data(key, key_refId, sql_stmt, rerun=False, sqlClient=None):
    """return data + job_id"""
    if cmd_args.time_out is None:
        # no time-out
        # df = sqlClient.run_sql(sql_stmt)
        df = None
        if rerun:
            if sqlClient is None:
                sqlClient = grafanaPluginInstances.get_sqlclient(key, thread_safe=True)
            res = sqlClient.execute_sql(sql_stmt, get_result=True)
            df, job_id = res.data, res.job_id
        else:
            df, job_id = _query_data_with_result(key, sql_stmt, sqlClient)
        if isinstance(df, str):
            df = None
        return df, job_id
    else:
        # with time-out
        if rerun:
            # not support - need to implement a mechanism in that an rerun query with timeout
            # would not lead to another rerun (i.e. automatically switch off the rerun
            # flag at Grafana plugin level) --> so that the next one to retrieve the data only
            assert 0
        else:
            job_id = grafanaPluginInstances.get_job_id(key, key_refId)
            if job_id is None:
                job_id = sqlClient.submit_sql(sql_stmt)
                grafanaPluginInstances.save_job_id(key, key_refId, job_id)
            job_status = sqlClient.wait_for_job(job_id, sleep_time=10)
            df = None
            if job_status == "completed":
                df = sqlClient.get_result(job_id)
        # check if job_id is present
        # if so, check if job status is completed
        #  - if so, get the data
        # if not, wait until time-out
        #  if time-out and still no result, send the error message back to wait a little bit and launch again
        # TODO: add a time-start here
        # WARNING: multi-queries lead to fail of returning job-list (429 error) --> need to consult Torsten to fix on their side
        # while not sqlClient.has_available_slot():
        #    # TODO - add a time-window check here (subtracting time-start)
        #    # when it is closed to service timeout, e.g. 10min for CloudFunction or CodeEngine
        #    # returns the proper message asking to rerun again
        #    # NOTE: better if the time-out is known - as there is no way to know how the time-out is configured for now
        #    # e.g. on-premise there is no time-out necessary
        #    time.sleep(4)  # seconds
        # if rerun:
        #     # doesn't support rerun on a system with time-out
        #     assert(0)
        #     sqlClient = grafanaPluginInstances.get_sqlclient(key, thread_safe=True)
        #     res = sqlClient.execute_sql(sql_stmt, get_result=True)
        #     df, job_id = res.data, res.job_id
        # else:
        #     df, job_id = _query_data_with_result(key, sql_stmt)
        # sqlClient = grafanaPluginInstances.get_sqlclient(key, thread_safe=True)
        # df = sqlClient.get_result(job_id)
        # print("SQL URL: ", sqlClient.sql_ui_link())
        return df, job_id


def query_data_noresultback(key, sql_stmt, rerun=False, sqlClient=None):
    if cmd_args.time_out is None:
        # no time-out
        if rerun:
            # doesn't support rerun on a system with time-out
            if sqlClient is None:
                sqlClient = grafanaPluginInstances.get_sqlclient(key, thread_safe=True)
            res = sqlClient.execute_sql(sql_stmt, get_result=False)
            job_id = res.job_id
        else:
            job_id = _query_data_noresultback(key, sql_stmt, sqlClient)
    else:
        # with time-out
        if rerun:
            # doesn't support rerun on a system with time-out
            assert cmd_args.time_out is None
            if sqlClient is None:
                sqlClient = grafanaPluginInstances.get_sqlclient(key, thread_safe=True)
            res = sqlClient.execute_sql(sql_stmt, get_result=False)
            job_id = res.job_id
        else:
            job_id = _query_data_noresultback(key, sql_stmt, sqlClient)
    return job_id


@memory.cache(ignore=["sqlClient"])
def _query_data_with_result(key, sql_stmt, sqlClient=None):
    if sqlClient is None:
        sqlClient = grafanaPluginInstances.get_sqlclient(key, thread_safe=True)
    res = sqlClient.execute_sql(sql_stmt, get_result=True)
    # print("SQL URL: ", sqlClient.sql_ui_link())
    return res.data, res.job_id


@memory.cache(ignore=["sqlClient"])
def _query_data_noresultback(key, sql_stmt, sqlClient=None):
    """return job_id"""
    if sqlClient is None:
        sqlClient = grafanaPluginInstances.get_sqlclient(key, thread_safe=True)
    res = sqlClient.execute_sql(sql_stmt, get_result=False)
    # print("SQL URL: ", sqlClient.sql_ui_link())
    return res.job_id


# regex
regex_timeFilter = r"\$__timeFilter\s*\((\s*\w*\s*)\)"
p_timeFilter = re.compile(regex_timeFilter)
regex_timeFilterColumn = r"\$__timeFilterColumn\s*\((\s*\w*\s*),(\s*\w*\s*)\)"
p_timeFilterColumn = re.compile(regex_timeFilterColumn)

# regex
regex_source = r"(?<=(?i:FROM)\s)\s*\$__source(?!_)(\s*\(\s*\))?(?=[\b|\n|\s])?"
p_cos_in = re.compile(regex_source)
regex_source = r"(?<=(?i:USING)\s)\s*\$__source(?!_)(\s*\(\s*\))?(?=[\b|\n|\s])?"
p_cos_in_using = re.compile(regex_source)

# regex
regex_source = r"(?<=(?i:FROM)\s)\s*\$__source_test(\s*\(\s*\w*\s*\))?(?=[\b|\n|\s])?"
p_cos_in_test = re.compile(regex_source)

# regex
regex_source = r"(?<=(?i:FROM)\s)\s*\$__source_prev(\s*\(\s*\w*\s*\))(?=[\b|\n|\s])?"
p_cos_in_prev = re.compile(regex_source)

# regex
regex_source = r"(?i:INTO)\s*\$__dest(\s*\([\s|\w|,|/]*\))?(?=[\b|\n|\s])?"
p_cos_out = re.compile(regex_source)

# SELECT TS_EXPLODE(...) AS (real_col1, real_col2)
regex_ts_explode = (
    r"(?i)\s*(ts_explode)[\(|\w|\s|\)|\d|,]+[aA][sS]\s*\((.*)\s*,\s*(.*)\)"
)
p_ts_explode = re.compile(regex_ts_explode)

# SELECT fake_col AS real_col
regex_as_column = r"\s*[\w|\s]+[aA][sS]\s+(\w+)\s*$"
p_as_column = re.compile(regex_as_column)

# SELECT real_col
regex_column = r"^\s*(\w+)\s*$"
p_column = re.compile(regex_column)

# nested SELECT statement
regex_nested_select = r"(?i)\(((?>[^\(\)]+|(?R))*)\)"
p_nested_select = regex.compile(regex_nested_select)


def gen_key(id, name):
    """generate the key for finding the right sqlClient object"""
    # TODO - this may not work when the single webapp serves different Grafana instances
    # --> there is a chance that the same 'id' is shared by these Grafana instances.
    return str(id) + "-" + name


def gen_key_refId(dashboardId, panelId, refId):
    """generate the key for finding the right sqlClient object,
    using the given (dashboard, panel, sql-id)"""
    return "-".join([str(dashboardId), str(panelId), refId])


def json_serial(obj):
    """JSON serializer for objects not serializable by default json code"""

    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError("Type %s not serializable" % type(obj))


def find_column_mapping(sql_stmt, columns):
    """given the outer SELECT statement
    which may contain column defined as, e.g. first(my_col) as new_col,
    we want to find this mapping from 'my_col' to 'new_col'

    returns
    -------
    dict:
    """

    def get_mapping(stmt):
        """return single column or multiple columns"""
        # st AS column
        res = re.search(r"(?i)\s*([\w|\s]+)\(([^\)]+)\)\s*[a][s]\s+(\w+)\s*$", stmt)
        if res:
            return {res.group(2): res.group(3)}
        else:
            return {}

    mapping = {}
    parsed = sqlparse.parse(sql_stmt)
    try:
        stmt = parsed[0]
    except IndexError as e:
        print(sql_stmt)
        print(parsed)
        raise e
    # assert(stmt.get_type() == "SELECT")
    for token in stmt.tokens:
        if isinstance(token, IdentifierList):
            for identifier in token.get_identifiers():
                res = get_mapping(str(identifier))
                mapping.update(res)
        if isinstance(token, Identifier):
            res = get_mapping(str(token))
            mapping.update(res)
        if token.ttype is Keyword:  # from
            break
    return mapping


def parse_sql_columns(sql):
    columns = []
    columns = columns + get_columns_from_single_select(sql) + parse_inner_selects(sql)
    return columns


def parse_inner_selects(sql_stmt):
    """
    find each inner select statement, then parse the columns from each SELECT found
    """

    def find_nested_selects(stmt):
        x = p_nested_select.findall(sql_stmt)
        nested = []
        for y in x:
            y = y.strip()
            if re.search(r"(?i)^select", y):
                nested.append(y)
        return nested

    nested_selects = find_nested_selects(sql_stmt)
    columns = []
    for s in nested_selects:
        columns = columns + parse_sql_columns(s)
    return columns


def get_columns_from_single_select(sql):
    """get the list of columns in the 'SELECT' type query.
    Returns an empty list, if

      1. not a SELECT statement
      2. SELECT * is used
    """

    def get_columns(stmt):
        """return single column or multiple columns"""
        # st AS column
        # res = re.search(r"\s*[\w|\s]+[aA][sS]\s+(\w+)\s*$", stmt)
        res = p_as_column.search(stmt)
        if res:
            return res.group(1)
        # standalone column
        # res = re.search(r'^\s*(\w+)\s*$', stmt)
        res = p_column.search(stmt)
        if res:
            return res.group(1)
        res = p_ts_explode.search(stmt)
        if res:
            return [res.group(2), res.group(3)]
        return ""

    def append(columns, res):
        if isinstance(res, str):
            if len(res) > 0:
                columns.append(res)
        elif isinstance(res, list):
            for i in res:
                if len(i) > 0:
                    columns.append(i)
        return columns

    columns = []
    parsed = sqlparse.parse(sql)
    try:
        stmt = parsed[0]
    except IndexError as e:
        print(sql)
        print(parsed)
        raise e
    if stmt.get_type() != "SELECT":
        return columns
    for token in stmt.tokens:
        if isinstance(token, IdentifierList):
            for identifier in token.get_identifiers():
                res = get_columns(str(identifier))
                columns = append(columns, res)
        if isinstance(token, Identifier):
            res = get_columns(str(token))
            columns = append(columns, res)
        if token.ttype is Keyword:  # from
            break
    return columns


class SourceType(Enum):
    UNUSED = 1
    TABLE = 2
    COSURL = 3


def RepresentsInt(s):
    try:
        int(s)
        return True
    except ValueError:
        return False


def process_macro_timeFilterColumn(p_timeFilter, sql_stmt, sdt_from, sdt_to):
    pattern = p_timeFilter.search(sql_stmt)
    while pattern:
        # the $__timeFilterColumn is used
        time_col = pattern.group(1).strip().lower()
        type_of_column = pattern.group(2).strip().lower()
        substr = ""

        # process for regular data
        if "string" == type_of_column:
            # the type is string
            # if {time_col} is in timestamp
            substr += """ to_timestamp({time_col}) BETWEEN to_timestamp("{dt_from}") and to_timestamp("{dt_to}")""".format(
                time_col=time_col, dt_from=sdt_from, dt_to=sdt_to
            )
        else:
            substr += """ cast({time_col}/1000 as long) BETWEEN to_unix_timestamp(to_timestamp("{dt_from}")) and to_unix_timestamp(to_timestamp("{dt_to}"))""".format(
                time_col=time_col, dt_from=sdt_from, dt_to=sdt_to
            )

        sql_stmt = p_timeFilter.sub(substr, sql_stmt, count=1)
        pattern = p_timeFilter.search(sql_stmt)
    return sql_stmt


def process_macro_data_source(p_reg, func_get_macro_mapping, key, sql_stmt):
    """
    process $__source macro
    Parameters
    ----------
    p_reg:
        pattern object to detect the present of the macro
    func_get_macro_mapping:
        a function that translate from a key to the right data source configured
    key: string
        the key that is used to identify the right data source
    sql_stmt: str
        the SQL string
    Returns
    -------
        the decoded SQL string
    """
    patterns = p_reg.findall(sql_stmt)
    try:
        substr = func_get_macro_mapping(key)
    except KeyError:
        # TODO: maybe we want to resend the credential each time - as when deploying to CodeEngine - the storage is not permanent?
        msg = "The webapp doesn't hold CloudSQL info - you may want to revalidate in the datasource setting"
        return (
            None,
            HTTPResponse(
                body=json.dumps({"error": msg}),
                status=403,
                headers={"Content-type": "application/json"},
            ),
        )
    if len(patterns) > 0 and len(substr) == 0:
        msg = "Can't use $__source (default value has not been configured yet)"
        raise HTTPResponse(
            body=json.dumps({"error": msg}),
            status=403,
            headers={"Content-type": "application/json"},
        )
    for pattern in patterns:
        pattern = p_reg.search(sql_stmt)
        if pattern:
            # the $__source is used
            sql_stmt = p_reg.sub(substr, sql_stmt, count=1)

    return sql_stmt


def revise_time_column(time_col, df):
    """
    the dataframe may has a column representing datetime, but it may be in string format
    we need to convert to the right format

    target: str, "time-series" or "table"
    """
    df.sort_values(by=time_col, inplace=True)

    if isinstance(df[time_col][0], str) and df[time_col][0].endswith("Z"):
        # remove 'Z' from datetime
        # and map to string representtion
        try:
            tmp = [
                str(x)
                for x in pd.to_datetime(df[time_col], format="%Y-%m-%dT%H:%M:%S.%fZ")
            ]
        except ValueError:
            tmp = [
                str(x)
                for x in pd.to_datetime(df[time_col], format="%Y-%m-%dT%H:%M:%SZ")
            ]
        df[time_col] = tmp
        # datetime64[ns] --> convert to 'ms'
        # df[time_col] = pd.to_datetime(df[time_col], format="%Y-%m-%dT%H:%M:%S.%fZ").values.astype('int64') // 10**6
        # .values.astype('int64') // 10**6
    return df


class CloudSQLDB(dict):
    def __init__(self, *arg, **kw):
        super(CloudSQLDB, self).__init__(*arg, **kw)
        self.db_file = "cloud_cos_db.json"
        self.sqlclient_file = "sqlclient_db.pkl"
        self.read()
        # holding fake time-series data source
        self._current_ts_df = {}
        self._current_mts_df = {}

    # @property
    # def data(self):
    #  return self._content
    def read(self):
        _content = None
        try:
            with open(self.db_file, "r") as read_file:
                _content = json.load(read_file)
        except FileNotFoundError:
            pass
        if _content:
            for k, v in _content.items():
                self[k] = v

    def save(self):
        if len(self.keys()) > 0:
            with open(self.db_file, "w") as write_file:
                json.dump(self, write_file)

    def get_sqlclient(self, key, thread_safe=False):
        apiKey = self[key]["apiKey"]
        instance_crn = self[key]["instance_crn"]
        target_cos_url = self[key]["target_cos_url"]
        if thread_safe is False:
            if key in grafanaPluginInstancesSqlClient.keys():
                sqlClient = grafanaPluginInstancesSqlClient[key]
                print("Found SqlClient... ", sqlClient)
            else:
                sqlClient = SQLClient(
                    api_key=apiKey,
                    instance_crn=instance_crn,
                    target_cos_url=target_cos_url,
                    max_tries=MAX_TRIES,
                )
                grafanaPluginInstancesSqlClient[key] = sqlClient
        else:
            sqlClient = SQLClient(
                api_key=apiKey,
                instance_crn=instance_crn,
                target_cos_url=target_cos_url,
                thread_safe=True,
                max_tries=MAX_TRIES,
            )
            print("Create thread-safe SqlClient... ", sqlClient)

        sqlClient.logon()
        return sqlClient

    def get_cos_source(self, key):
        # stored_using_table  = tmp_body.get('using_table').strip()
        if self[key]["using_table"]:
            table = self[key]["table"]
            if len(table.strip()) == 0:
                return ""
            else:
                return " {} ".format(table)
        else:
            try:
                cos_in = self[key]["source_cos_url"]
            except KeyError:
                return ""
            if len(cos_in.strip()) == 0:
                return ""
            else:
                format_type = self[key]["format_type"]
                return "{} STORED AS {}".format(cos_in, format_type)

    def get_cos_source_using(self, key):
        # stored_using_table  = tmp_body.get('using_table').strip()
        if self[key]["using_table"]:
            table = self[key]["table"]
            if len(table.strip()) == 0:
                return ""
            else:
                return " {} ".format(table)
        else:
            try:
                cos_in = self[key]["source_cos_url"]
            except KeyError:
                return ""
            if len(cos_in.strip()) == 0:
                return ""
            else:
                format_type = self[key]["format_type"]
                return "{} LOCATION {}".format(format_type, cos_in)

    def get_cos_dest(self, key, suffix, format_type):
        # stored_using_table  = tmp_body.get('using_table').strip()
        # if self[key]['target_cos_url'][-1] == '/':
        cos_out = "/".join([self[key]["target_cos_url"], suffix])
        cos_out = "INTO {} STORED AS {} ".format(cos_out, format_type)
        return cos_out

    def get_sts_random_data(self, key, dt_from, dt_to):
        values = """
        FROM VALUES -- timestamp, observation
        (1, 10), (2, 20), (3, 30), (4, 40),
        (5, 5), (6, 10), (7, 15), (8, 40),
        (9, 100), (10, 200), (11, 300), (12, 400)
        AS ds
      """
        # np.random.seed(2019)
        N = 30
        rng = pd.date_range(dt_from, dt_to, periods=N)
        df = pd.DataFrame(
            np.random.randint(20, size=(N, 2)),
            columns=["timestamp", "observation"],
            index=rng,
        )
        ##.rename(columns={df.index.name:'timestamp'})
        df = df.drop("timestamp", axis=1)
        # df.reset_index(inplace=True)
        # df.rename(columns={"index":"timestamp"})
        # df.index = pd.to_datetime(df['index']).astype(np.int64) // 10**6
        df.index = pd.to_datetime(df.index).astype(np.int64) // 10 ** 6
        if key not in self._current_ts_df:
            self._current_ts_df[key] = df
        else:
            idx_start = (
                pd.to_datetime(dt_from).to_datetime64().astype(np.int64) // 10 ** 6
            )
            idx_end = pd.to_datetime(dt_to).to_datetime64().astype(np.int64) // 10 ** 6
            # idx_start = df.iloc[0].name
            # idx_end = df.iloc[-1].name
            df = df.loc[(df.index > self._current_ts_df[key].iloc[-1].name)]
            self._current_ts_df[key] = self._current_ts_df[key].append(df)
            # NOTE : currently not removing old ones
            # self._current_ts_df[key] = self._current_ts_df[key].loc[(self._current_ts_df[key].index >= idx_start) & (self._current_ts_df[key].index <= idx_end)]
            # df = self._current_ts_df[key]
            df = self._current_ts_df[key].loc[
                (self._current_ts_df[key].index >= idx_start)
                & (self._current_ts_df[key].index <= idx_end)
            ]
        x = list(df.to_records(index=True))
        data = ", ".join([str(i) for i in x])
        assert len(data) > 0
        values = """
        VALUES -- timestamp, observation
        {}
        AS ds
      """.format(
            data
        )
        return values

    def get_mts_random_data(self, key, dt_from, dt_to):
        values = """
      FROM VALUES -- key, timestamp, observation
    (2017, 1 ,100),
    (2017, 1 ,50),
    (2017, 2 ,200),
    (2017, 2 ,300),
    (2018, 1 ,300),
    (2018, 1 ,100),
    (2018, 2 ,400) AS ds
      """
        # np.random.seed(2019)
        num_metrics = 2
        df = None
        for i in range(0, num_metrics + 1):
            N = np.random.randint(20, 30)
            rng = pd.date_range(dt_from, dt_to, periods=N)
            tmp_df = pd.DataFrame(
                np.hstack((np.random.randint(20, size=(N, 1)), np.array([[i] * N]).T)),
                columns=["observation", "key"],
                index=rng,
            )
            if df is None:
                df = tmp_df
            else:
                df = df.append(tmp_df, ignore_index=False)

        idx_start = pd.to_datetime(dt_from).to_datetime64().astype(np.int64) // 10 ** 6
        idx_end = pd.to_datetime(dt_to).to_datetime64().astype(np.int64) // 10 ** 6

        # millisecond
        df.index = pd.to_datetime(df.index).astype(np.int64) // 10 ** 6
        if key not in self._current_mts_df:
            self._current_mts_df[key] = df
        else:
            df = df.loc[(df.index > self._last_mts_idx_end)]
            self._current_mts_df[key] = self._current_mts_df[key].append(df)

            # NOTE : currently not removing old ones
            # self._current_mts_df[key] = self._current_mts_df[key].loc[(self._current_mts_df[key].index >= idx_start) & (self._current_mts_df[key].index <= idx_end)]
            # df = self._current_mts_df[key]
            df = self._current_mts_df[key].loc[
                (self._current_mts_df[key].index >= idx_start)
                & (self._current_mts_df[key].index <= idx_end)
            ]

        x = list(df.to_records(index=True))
        data = ", ".join([str(i) for i in x])
        assert len(data) > 0
        values = """
        VALUES -- timestamp, observation, key
        {}
        AS ds
      """.format(
            data
        )
        self._last_mts_idx_end = idx_end
        return values

    def get_job_id(self, key, refId):
        """return the job_id associated with a given `key`

        Return
        ------
        str: the job_id if found; otherwise return None
        """
        if "refId" not in self[key]:
            with lock_savejob:
                if "refId" not in self[key]:
                    self[key]["refId"] = {}
        if refId in self[key]["refId"]:
            return self[key]["refId"][refId]
        else:
            return None

    def save_job_id(self, key, refId, job_id):
        """save the job_id for the
        (query in the given dashboard/panel) ~ 'refId' and
        (datasource) ~ 'key'

        NOTE: The information will be used by `get_cos_source_prev`"""
        if "refId" not in self[key]:
            with lock_savejob:
                if "refId" not in self[key]:
                    self[key]["refId"] = {}
        self[key]["refId"][refId] = job_id

    def get_cos_source_prev(self, key, refId):
        """get COS URL from the output of a previous query

        Exceptions
        ----------
        KeyError"""
        sqlClient = self.get_sqlclient(key, thread_safe=True)
        job_id = self[key]["refId"][refId]
        job_info = sqlClient.get_job(job_id)
        res = "{} STORED AS {}".format(
            job_info["resultset_location"], job_info["resultset_format"]
        )
        return res

    def should_sql_stmt_be_run(self, key, refId, sql_stmt, sleep_time):
        """return True if it is safe to launch the query, i.e. no further change to it"""
        milliseconds_since_epoch = datetime.now().timestamp() * 1000
        if "query" not in self[key]:
            with lock:
                if "query" not in self[key]:
                    self[key]["query"] = {}
        if refId not in self[key]["query"]:
            with lock:
                if refId not in self[key]["query"]:
                    self[key]["query"][refId] = {}
        if sql_stmt not in self[key]["query"][refId]:
            with lock:
                if sql_stmt not in self[key]["query"][refId]:
                    self[key]["query"][refId][sql_stmt] = milliseconds_since_epoch
        elif milliseconds_since_epoch > self[key]["query"][refId][sql_stmt]:
            with lock:
                if milliseconds_since_epoch > self[key]["query"][refId][sql_stmt]:
                    self[key]["query"][refId][sql_stmt] = milliseconds_since_epoch
        sleep(sleep_time)  # seconds
        # if milliseconds_since_epoch == self[key]['query'][refId][sql_stmt]:
        #    # no new request to same query
        #    return True
        if milliseconds_since_epoch < self[key]["query"][refId][sql_stmt]:
            # there is a new request
            return False
        return True


# from cloud_utilities import test_credentials
# ref_cloud_apikey = test_credentials.apikey
# ref_instance_crn = test_credentials.instance_crn
# ref_target_cos_url = test_credentials.result_location

# store information of each datasource-plugin 'id'
grafanaPluginInstances = CloudSQLDB()
# store the object connecting to SQL Client service
grafanaPluginInstancesSqlClient = {}

# data_schema = {}

# default_sql_client = None
# aiOps = SQLClient(api_key=ref_cloud_apikey, instance_crn=ref_instance_crn, target_cos_url=ref_target_cos_url)
##aiOps = SQLClient(api_key=cloud_apikey_raghu, instance_crn=instnacecrn, target_cos_url=target_cos_url, max_concurrent_jobs=4)
# aiOps.logon()

# sqlClient = aiOps
# sqlClient.engine.sql_ui_link()
#
##dict_data = sqlClient.get_cos_summary("cos://s3.us-south.cloud-object-storage.appdomain.cloud/sql-query-cos-access-ts/jobid=a3475263-469a-4e22-b382-1d0ae8f1d1fa")
# df = sqlClient.list_results("a3475263-469a-4e22-b382-1d0ae8f1d1fa")
# print(df.to_string())
# with pd.option_context('display.max_rows', None, 'display.max_columns', None):  # more options can be specified also
#     print(df)

app = Bottle()

# FUNCTIONS = {'series A': math.sin, 'series B': math.cos}
FUNCTIONS = {"series A": math.sin, "series B": "series B"}

tabular_data = {
    "series A": [
        {
            "columns": [
                {"text": "Time", "type": "time"},
                {"text": "Country", "type": "string"},
                {"text": "Number", "type": "number"},
            ],
            "rows": [[1234567, "SE", 123], [1234567, "DE", 231], [1234567, "US", 321]],
            "type": "table",
        }
    ],
    "series B": [
        {
            "columns": [
                {"text": "Time", "type": "time"},
                {"text": "Country", "type": "string"},
                {"text": "Number", "type": "number"},
            ],
            "rows": [[1234567, "BE", 123], [1234567, "GE", 231], [1234567, "PS", 321]],
            "type": "table",
        }
    ],
}


def convert_to_time_ms(timestamp):
    """Convert a Grafana timestamp to unixtimestamp in milliseconds

    Args:
        timestamp (str): the request contains ``'range': {'from':
               '2019-06-16T08:00:05.331Z', 'to': '2019-06-16T14:00:05.332Z', ...``
    """
    return 1000 * timegm(
        datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%S.%fZ").timetuple()
    )


def create_data_points(func, start, end, length=1020):
    """
    A dummy function to produce sine and cosine data

    You should replace this with your SQL, CQL or Mongo Query language.
    Also, make sure your database has the correct indecies to increase perfomance

    Args:
      func (object) - A callable that accepts a number and returns a number
        start (str) - timestamp
        end (str) - timestamp
        length (int) - the number of data points

    """
    lower = convert_to_time_ms(start)
    upper = convert_to_time_ms(end)
    return [
        [func(i), int(i)]
        for i in [lower + x * (upper - lower) / length for x in range(length)]
    ]


def create_data_points_name_func(series_name_or_func, start, end, length=1020):
    """Generate fake data"""
    if isinstance(series_name_or_func, str):
        series_name = series_name_or_func
        lower = convert_to_time_ms(start)
        upper = convert_to_time_ms(end)
        if series_name == "series B":
            return [
                [random.randint(0, 100), int(i)]
                for i in [lower + x * (upper - lower) / length for x in range(length)]
            ]
    else:
        func = series_name_or_func
        return create_data_points(func, start, end, length=length)


@app.route("/", method="GET")
def index():
    return "<h1> Hello world</h1>"


@app.route("/login", method=["POST", "GET"])
def login():
    """handle 'testDataSource() - test connection to data source

    Returns
    -------
    str
        "OK"
    """
    if request.method == "GET":
        return "<h1>Testing login</h1>"
    logger.debug("========= PRINT REQUEST ============")
    logger.debug(request)
    logger.debug("========= END PRINT REQUEST ============")
    body = request.body.read().decode("utf-8")
    body = json.loads(body)
    import pprint

    logger.debug("========= PRINT body of REQUEST ============")
    pprint.pprint(body, width=1)
    logger.debug("========= END PRINT body of REQUEST ============")
    # apiKey = request.forms.get('apiKey')
    # instance_crn = request.forms.get('instance_crn')
    # result_location = request.forms.get('result_location')
    # target_cos_url = request.forms.get('target_cos_url')
    # instance_rate_limit = request.forms.get('instance_rate_limit')
    print("Handling /login request")

    key = gen_key(body.get("id"), body.get("name"))
    # always update
    data_exist = False
    if key in grafanaPluginInstances.keys():
        tmp_body = grafanaPluginInstances[key]
        stored_apiKey = tmp_body.get("apiKey").strip()
        stored_instance_crn = tmp_body.get("instance_crn").strip()
        stored_target_cos_url = tmp_body.get("target_cos_url").strip()
        stored_source_cos_url = tmp_body.get("source_cos_url", "").strip()
        stored_table = tmp_body.get("table", "").strip()
        stored_using_table = tmp_body.get("using_table")
        stored_instance_rate_limit = tmp_body.get("instance_rate_limit").strip()
        stored_format_type = tmp_body.get("format_type", "").strip()
        data_exist = True
        # grafanaPluginInstances[key]['apiKey'] = body.get('apiKey')
        # grafanaPluginInstances[key]['instance_crn'] = body.get('instance_crn')
        # grafanaPluginInstances[key]['apiKey'] = body.get('apiKey')
        # grafanaPluginInstances[key]['target_cos_url'] = body.get('target_cos_url')
        # grafanaPluginInstances[key]['source_cos_url'] = body.get('source_cos_url')
        # grafanaPluginInstances[key]['format_type'] = body.get('format_type')
        # grafanaPluginInstances[key]['instance_rate_limit'] = body.get('instance_rate_limit')

    # extract information
    if "instance_crn" not in body or len(body["instance_crn"]) == 0:
        msg = "Need CloudSQL CRN"
        raise HTTPResponse(
            body=json.dumps({"error": msg}),
            status=403,
            headers={"Content-type": "application/json"},
        )
    instance_crn = body.get("instance_crn").strip()
    if "apiKey" not in body or len(body["apiKey"]) == 0:
        msg = "Need apiKey"
        raise HTTPResponse(
            body=json.dumps({"error": msg}),
            status=403,
            headers={"Content-type": "application/json"},
        )
    apiKey = body.get("apiKey").strip()
    # result_location = body.get('result_location').strip()
    source_type = SourceType.UNUSED
    if "using_table" not in body:
        # TODO if this occur - go back and check why default value is not set in Grafana plugin
        body["using_table"] = False
    if body["using_table"] is False:
        if "source_cos_url" in body and len(body["source_cos_url"]) > 0:
            source_cos_url = body.get("source_cos_url").strip()
            format_type = body.get("format_type").strip()
            if source_cos_url is None or not ParsedUrl().is_valid_cos_url(
                source_cos_url
            ):
                msg = "Invalid COS URL for source"
                raise HTTPResponse(
                    body=json.dumps({"error": msg}),
                    status=403,
                    headers={"Content-type": "application/json"},
                )
            else:
                source_type = SourceType.COSURL

    else:
        if "table" in body and len(body["table"]) > 0:
            table = body.get("table").strip()
            source_type = SourceType.TABLE

    if "target_cos_url" not in body or len(body["target_cos_url"]) == 0:
        msg = "Need target COS URL"
        raise HTTPResponse(
            body=json.dumps({"error": msg}),
            status=403,
            headers={"Content-type": "application/json"},
        )
    target_cos_url = body.get("target_cos_url").strip()

    msg = "Need rate limit as an int > 0"
    e = HTTPResponse(
        body=json.dumps({"error": msg}),
        status=403,
        headers={"Content-type": "application/json"},
    )
    if "instance_rate_limit" not in body or len(body["instance_rate_limit"]) == 0:
        raise e
    elif not RepresentsInt(body["instance_rate_limit"]):
        raise e
    instance_rate_limit = body.get("instance_rate_limit").strip()
    # assert(ref_cloud_apikey == apiKey)
    # assert(ref_instance_crn == instance_crn)
    if target_cos_url is None or not ParsedUrl().is_valid_cos_url(target_cos_url):
        msg = "Invalid COS URL for target"
        raise HTTPResponse(
            body=json.dumps({"error": msg}),
            status=403,
            headers={"Content-type": "application/json"},
        )

    # print(apiKey)
    # print(instance_crn)
    # print(result_location)
    # print(target_cos_url)
    # print(instance_rate_limit)
    # logger.info(apiKey)

    if key not in grafanaPluginInstancesSqlClient.keys():
        # TODO: consider add max_concurrent_jobs info from `instance_rate_limit`
        sqlClient = SQLClient(
            api_key=apiKey,
            instance_crn=instance_crn,
            target_cos_url=target_cos_url,
            max_tries=MAX_TRIES,
        )
        grafanaPluginInstancesSqlClient[key] = sqlClient
        if DEBUG:
            print("Create new SQLClient: ", sqlClient)
        # grafanaPluginInstances.save_sqlclients()
    else:
        sqlClient = grafanaPluginInstancesSqlClient[key]
        try:
            sqlClient.logon()
            if sqlClient.logged_on is True:
                if DEBUG:
                    print("Found SQLClient: ", sqlClient)
        except AttributeError:
            # recreate
            sqlClient = SQLClient(
                api_key=apiKey,
                instance_crn=instance_crn,
                target_cos_url=target_cos_url,
                max_tries=MAX_TRIES,
            )
            grafanaPluginInstancesSqlClient[key] = sqlClient
            if DEBUG:
                print("Create new SQLClient: ", sqlClient)

    response.headers["Content-Type"] = "application/json"
    try:
        if data_exist and (
            stored_apiKey != apiKey
            or instance_crn != stored_instance_crn
            or stored_target_cos_url != target_cos_url
            or instance_rate_limit != stored_instance_rate_limit
        ):
            if DEBUG:
                print("HTTP input: ", instance_crn, "  \n", apiKey)
            sqlClient.configure(
                api_key=apiKey,
                instance_crn=instance_crn,
                target_cos_url=target_cos_url,
            )

        # test API key
        sqlClient.logon()

        print("SQL URL: ", sqlClient.sql_ui_link())

        # test SQL Query CRN
        # test COS OUT URL
        sql_stmt = """
       SELECT 1
      INTO {target_cos_url} STORED AS CSV
      """.format(
            target_cos_url=target_cos_url
        )
        sqlClient.run_sql(sql_stmt)

        # # test COS IN URL
        if source_type == SourceType.COSURL:
            df = sqlClient.get_schema_data(source_cos_url, type=format_type)
            if len(df) == 1 and df["name"][0] == "_corrupt_record":
                msg = "Check format for source COS URL"
                raise HTTPResponse(
                    body=json.dumps({"error": msg}),
                    status=403,
                    headers={"Content-type": "application/json"},
                )
        elif source_type == SourceType.TABLE:
            df = sqlClient.describe_table(table)
            if df is None:
                msg = "Check if table name is correct"
                raise HTTPResponse(
                    body=json.dumps({"error": msg}),
                    status=403,
                    headers={"Content-type": "application/json"},
                )
            # data_schema[source_cos_url] = sqlClient.get_schema_data(source_cos_url, type=format_type)

        print("Login ok")
        # response.status = 200
        response.status = "200 API Key valid"
        # return json.dumps({ 'status': 'success', 'message': 'Success',"data": {} }), 200
        theBody = "Login ok."
        response.body = theBody

        # safe to update
        grafanaPluginInstances[key] = body
        grafanaPluginInstances.save()

        return response
    except (ibm_botocore.exceptions.CredentialRetrievalError, AttributeError):
        # return BaseResponse(body='Invalid API key', status=401)
        msg = "Invalid API key"
        if DEBUG:
            print(msg)
        # response.body = json.dumps({'error':msg})
        raise HTTPResponse(
            body=json.dumps({"error": msg}),
            status=403,
            headers={"Content-type": "application/json"},
        )

    except CosUrlNotFoundException as e:
        msg = "Wrong COS URL (either source or target) authentication"
        raise HTTPResponse(
            body=json.dumps({"error": msg}),
            status=403,
            headers={"Content-type": "application/json"},
        )
    except SqlQueryCrnInvalidFormatException as e:
        msg = "Wrong Sql Query CRN"
        raise HTTPResponse(
            body=json.dumps({"error": msg}),
            status=403,
            headers={"Content-type": "application/json"},
        )
    except HTTPResponse as e:
        raise e
    except Exception as error:
        msg = "Unknown error: {}".format(str(type(error)))
        raise HTTPResponse(
            body=json.dumps({"error": msg}),
            status=403,
            headers={"Content-type": "application/json"},
        )


@app.hook("after_request")
def enable_cors():
    """
    Grafana makes AJAX call to the data source in either proxy-mode or direct-mode.

    In proxy-mode, Grafana uses its own backend server, and add CORS header to the request.

    In direct mode, Grafana  sends directly to the rest API app, so the request should contains the CORS request
    so that the browser allows Grafana to get the result.
    """
    print("after_request hook: enable_cors")
    for key in response.headers.keys():
        print(response.headers.getall(key))
    print("----------")
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Accept, Content-Type"


@app.hook("after_request")
def add_hostname_info():
    """when deploying the webapp via Docker container,
    it is good to know the location for debug purpose

     return the three-letter location name and the container number from the end of the hostname string.
    """
    print("after_request hook: add hostname-info")
    for key in response.headers.keys():
        print(key, ":    ", response.headers.getall(key))
    print("----------")
    env_host = str(os.environ.get("HOSTNAME"))
    hostname = re.findall("[a-z]{3}-\d$", env_host)
    if hostname:
        response.headers["SP-LOCATION"] = hostname
    return response
    pass


@app.post("/search")
def search():
    """Return a HTTPResponse containing a JSON array
    with the names of the data series available

    * headers that specify that this is response is JSON.

    Returns
    -------
    HTTPResponse
        list of name of the data series
    """
    print(request)
    return HTTPResponse(
        body=json_dumps(["series A", "series B"]),
        headers={"Content-Type": "application/json"},
    )


@app.post("/query")
def query():
    """Handle the query from Grafana

    This endpoint can return either
    * time-series data
    * a table for each series

    Grafana sends a request which specifies that it queries for the tabular data.
    The request is a JSON as

    .. console-block: python
        'targets': [{'target': 'series B', 'refId': 'A', 'type': 'table'}]

    Grafana expects the time-series data in the format

    *  datapoints are a list of value and unixtimestamp in milliseconds.

    .. console-block: python
        [
          {
            "target":"series A", // The field being queried for
            "datapoints":[
              [622,1450754160000],  // Metric value as a float , unixtimestamp in milliseconds
              [365,1450754220000]
            ]
          },
          {
            "target":"series B",
            "datapoints":[
              [861,1450754160000],
              [767,1450754220000]
            ]
          }
        ]


    Returns
    -------
    [type]
        [description]
    """
    # if key in grafanaPluginInstances.keys():
    #   body = grafanaPluginInstances[key]
    # else:
    #   grafanaPluginInstances[key] = body
    logger.debug("========= PRINT REQUEST ============")
    logger.debug(request)
    logger.debug("========= END PRINT REQUEST ============")
    body = request.body.read().decode("utf-8")
    body = json.loads(body)
    import pprint

    logger.debug("========= PRINT body of REQUEST ============")
    pprint.pprint(body, width=1)
    logger.debug("========= END PRINT body of REQUEST ============")
    # check to see if it's safe to launch
    query = body["targets"][0]
    id = query["id"]
    name = query["name"]
    key = gen_key(id, name)
    key_refId = gen_key_refId(body["dashboardId"], body["panelId"], query["refId"])
    sql_stmt = query["queryText"]
    sleep_time = max(2.0, min(15.0, 2 * len(body["targets"])))
    if not grafanaPluginInstances.should_sql_stmt_be_run(
        key, key_refId, sql_stmt, sleep_time
    ):
        # don't launch any
        body = json_dumps([])
        return HTTPResponse(body=body, headers={"Content-Type": "application/json"})

    # launch now
    # loop through all queries and process it
    resp_body = []
    sqlClient = None
    key = None
    for query in body["targets"]:
        if "hide" in query and query["hide"] is True:
            continue
        res, error_obj = process_query(query, body, sqlClient=sqlClient, old_key=key)
        if error_obj is not None:
            raise error_obj
        if isinstance(res, list):
            for r in res:
                resp_body.append(r)
        if res is None:
            # get_result <- False
            pass
        else:
            resp_body.append(res)
    body = json_dumps(resp_body)
    return HTTPResponse(body=body, headers={"Content-Type": "application/json"})


def process_query(fullquery, body, sqlClient=None, old_key=None):
    """
    Parameters
    ------------
    fullquery: dict
      The dict object with all information required to launch a query
    body: dict
      The body of the original full HTTP request
    sqlClient: SQLClient
      The object that can launch the sql stmt string
    old_key: str
      The key which tracks the given sqlClient object

    Returns
    --------
    returns a tuple (result, error_object)
    None, error_object --> error is detected
    result, None       --> result
    None, None         --> when result is not needed [intermediate result]

    NOTE: A result can be a dict{} : represent a single time-series data or single table data
    or a list of dict: represent multiple time-series data
    """
    # i = i-th query
    # fullquery = body["targets"][i]
    result = None

    data_type = "TableData"
    if "format" in fullquery and fullquery["format"] == "time_series":
        data_type = "TimeSeries"
    if "queryText" not in fullquery:
        # don't run further
        # TODO - return empty things
        return {}, None

    sql_stmt = fullquery["queryText"]
    if len(sql_stmt.strip()) == 0:
        return None, None
    logger.debug("========= PRINT sql_stmt ============")
    logger.debug(sql_stmt)
    logger.debug("========= END PRINT sql_stmt ============")
    id = fullquery["id"]
    name = fullquery["name"]
    key = gen_key(id, name)
    # TODO : calculate these and check if SQL query uses
    # 'DAY' 'MONTH' 'YEAR' to replace it with:
    #   DAY between day_from and day_to
    #   MONTH between month_from and month_to
    #   YEAR between year_from and year_to
    #
    from dateutil import parser

    dt_from = parser.parse(body["range"]["from"])
    dt_to = parser.parse(body["range"]["to"])
    sdt_from = body["range"]["from"]
    sdt_to = body["range"]["to"]

    if len(get_columns_from_single_select(sql_stmt)) == 0 and re.search(
        r"(?i)^\s*select", sql_stmt
    ):
        msg = "The 'SELECT *' is being used: Not accepted in the query with Id {}".format(
            fullquery["refId"]
        )
        return (
            None,
            HTTPResponse(
                body=json.dumps({"error": msg}),
                status=403,
                headers={"Content-type": "application/json"},
            ),
        )

    columns = parse_sql_columns(sql_stmt)
    columns_from_to = find_column_mapping(sql_stmt, columns)
    if len(columns) > 0:
        # find the column containing time - for time replacement
        # when $__timeFilter() is used
        time_col = columns[0]
        if "time_column" in fullquery:
            tmp = fullquery["time_column"].strip()
            if len(tmp) > 0:
                time_col = tmp
            if time_col not in columns:
                msg = "The name for time-column {} doesn't match with the column(s) in the query with Id {}".format(
                    time_col, fullquery["refId"]
                )
                return (
                    None,
                    HTTPResponse(
                        body=json.dumps({"error": msg}),
                        status=403,
                        headers={"Content-type": "application/json"},
                    ),
                )

        sql_stmt = process_macro_timeFilterColumn(
            p_timeFilterColumn, sql_stmt, sdt_from, sdt_to
        )
        patterns = p_timeFilter.findall(sql_stmt)
        for pattern in patterns:
            pattern = p_timeFilter.search(sql_stmt)
            if pattern:
                # the $__timeFilter is used
                appname = pattern.group(1).strip().lower()
                substr = ""

                # process for regular data
                type_of_column = appname
                if "string" == type_of_column:
                    # the type is string
                    # if {time_col} is in timestamp
                    substr += """ to_timestamp({time_col}) BETWEEN to_timestamp("{dt_from}") and to_timestamp("{dt_to}")""".format(
                        time_col=time_col, dt_from=sdt_from, dt_to=sdt_to
                    )
                else:
                    # flake8: noqa = E501
                    substr += """ cast({time_col}/1000 as long) BETWEEN to_unix_timestamp(to_timestamp("{dt_from}")) and to_unix_timestamp(to_timestamp("{dt_to}"))""".format(
                        time_col=time_col, dt_from=sdt_from, dt_to=sdt_to
                    )  # noqa = E501

                sql_stmt = p_timeFilter.sub(substr, sql_stmt, count=1)
    sql_stmt = process_macro_data_source(
        p_cos_in, grafanaPluginInstances.get_cos_source, key, sql_stmt
    )
    sql_stmt = process_macro_data_source(
        p_cos_in_using, grafanaPluginInstances.get_cos_source_using, key, sql_stmt
    )
    p_reg = p_cos_in_test
    patterns = p_reg.findall(sql_stmt)
    for pattern in patterns:
        pattern = p_reg.search(sql_stmt)
        if pattern.group(1) is None:
            # $__source_test
            ts_form = ""
        else:
            # $__source_test()
            ts_form = re.sub(r"\(|\)", "", pattern.group(1).strip().lower())
        substr = ""
        if ts_form in ["ts", ""]:  # single time-series"
            substr = grafanaPluginInstances.get_sts_random_data(key, dt_from, dt_to)
        if "mts" == ts_form:  # multipletime-series"
            substr = grafanaPluginInstances.get_mts_random_data(key, dt_from, dt_to)
        if pattern:
            # the $__source_test is used
            sql_stmt = p_reg.sub(substr, sql_stmt, count=1)
    # get source COS URL as the output of a previous query
    p_reg = p_cos_in_prev
    patterns = p_reg.findall(sql_stmt)
    for pattern in patterns:
        pattern = p_reg.search(sql_stmt)
        if pattern.group(1) is None:
            # $__source_prev
            msg = "Need to specify refId name in $__source_prev, e.g. $__source_prev(A)"
            return (
                None,
                HTTPResponse(
                    body=json.dumps({"error": msg}),
                    status=403,
                    headers={"Content-type": "application/json"},
                ),
            )
        else:
            # $__source_prev()
            prev_refId_name = re.sub(r"\(|\)", "", pattern.group(1).strip())
        substr = ""
        if len(prev_refId_name) == 0:
            msg = "Need to specify refId name in $__source_prev, e.g. $__source_prev(A)"
            return (
                None,
                HTTPResponse(
                    body=json.dumps({"error": msg}),
                    status=403,
                    headers={"Content-type": "application/json"},
                ),
            )
        # TODO
        # May extend here to allow reading data from another panel and/or dashboard
        key_refId = gen_key_refId(body["dashboardId"], body["panelId"], prev_refId_name)
        try:
            substr = grafanaPluginInstances.get_cos_source_prev(key, key_refId)
        except KeyError:
            msg = (
                "The name {} used in $__source_prev()"
                "does not exist or is not the prior sql statement in the chain"
            ).format(prev_refId_name)
            return (
                None,
                HTTPResponse(
                    body=json.dumps({"error": msg}),
                    status=403,
                    headers={"Content-type": "application/json"},
                ),
            )

        if pattern:
            # the $__source_test is used
            sql_stmt = p_reg.sub(substr, sql_stmt, count=1)
    # get target COS URL
    p_reg = p_cos_out
    patterns = p_reg.findall(sql_stmt)
    for _ in patterns:
        pattern = p_reg.search(sql_stmt)
        substr = ""
        if pattern.group(1) is None:
            # $__dest
            substr = ""
        else:
            # $__dest()
            # $__dest(<format> [,suffix])
            # Example:
            #     $__dest(parquet)
            #     $__dest(parquet, a/b/c)
            args_str = re.sub(r"\(|\)", "", pattern.group(1).strip())
            if len(args_str) > 0:
                arg_list = args_str.split(",")
                if len(arg_list) > 2:
                    msg = "$__dest() can't have more than two arguments"
                    return (
                        None,
                        HTTPResponse(
                            body=json.dumps({"error": msg}),
                            status=403,
                            headers={"Content-type": "application/json"},
                        ),
                    )
                if len(arg_list) == 1:
                    # must be format type
                    format_type = arg_list[0].upper()
                    suffix = ""
                else:
                    format_type = arg_list[0].upper()
                    suffix = arg_list[1].strip()

                if format_type not in ["PARQUET", "AVRO", "CSV", "JSON", "ORC"]:
                    pass
                    msg = "Invalid format of data used in $__dest macro"
                    return (
                        None,
                        HTTPResponse(
                            body=json.dumps({"error": msg}),
                            status=403,
                            headers={"Content-type": "application/json"},
                        ),
                    )
                substr = grafanaPluginInstances.get_cos_dest(key, suffix, format_type)
        if pattern:
            # the $__source_test is used
            sql_stmt = p_reg.sub(substr, sql_stmt, count=1)

    try:
        while True:
            try:
                sql_stmt = format_sql(sql_stmt)
                sql_stmt = sql_stmt.replace("\\'", '"')
                print(sql_stmt)
                # TODO: convert this to a function with
                # and decorate the function with @functools.lru_cache
                # https://docs.python.org/3.4/library/functools.html#functools.lru_cache
                df = None
                key_refId = gen_key_refId(
                    body["dashboardId"], body["panelId"], fullquery["refId"]
                )
                # for some reason Grafana sends twice, and this to prevent from running twice on Cloud SQL
                # there is a chance that a new query will be sent shortly which override the current
                # one - as we can't cancel a launched SQL Query --> so we put in the queue and
                # wait a little before before really launch it
                # if not grafanaPluginInstances.should_sql_stmt_be_run(key, key_refId, sql_stmt):
                #     break
                # TODO - consider allow users to request 'rerun
                rerun = False
                if sqlClient:
                    assert old_key == key
                if fullquery["get_result"] is False:
                    job_id = query_data_noresultback(
                        key, sql_stmt, rerun=rerun, sqlClient=sqlClient
                    )
                else:
                    df, job_id = query_data(
                        key, key_refId, sql_stmt, rerun=rerun, sqlClient=sqlClient
                    )
                    if df is None:
                        msg = "Query {}: no data returned or query failed due to timeout".format(
                            fullquery["refId"]
                        )
                        return (
                            None,
                            HTTPResponse(
                                body=json.dumps({"error": msg}),
                                status=403,
                                headers={"Content-type": "application/json"},
                            ),
                        )
                # a unique reference needs dashboardId + panelid + refid
                # TODO : When the webapp is shared by multiple instances of Grafana
                # --> maybe the dashboardId and panelId can be the same for those from
                # two Grafana instance --> need to resolve this
                grafanaPluginInstances.save_job_id(key, key_refId, job_id)
                break
            except RateLimitedException:
                sleep(10)
        if fullquery["get_result"] is False:
            return None, None

    except CosUrlInaccessibleException as e:
        msg = "Query {}: Check if you use the right data-source: {}".format(
            fullquery["refId"], str(e)
        )
        return (
            None,
            HTTPResponse(
                body=json.dumps({"error": msg}),
                status=403,
                headers={"Content-type": "application/json"},
            ),
        )
    except Exception as e:
        msg = "Query {}: unknown error {}".format(fullquery["refId"], str(e))
        return (
            None,
            HTTPResponse(
                body=json.dumps({"error": msg}),
                status=403,
                headers={"Content-type": "application/json"},
            ),
        )
    logger.info("RESULT is available")

    if df is None:
        # no data returned
        msg = "Query {}: No data returned: check the time rang".format(
            fullquery["refId"]
        )
        return (
            None,
            HTTPResponse(
                body=json.dumps({"error": msg}),
                status=403,
                headers={"Content-type": "application/json"},
            ),
        )

    # make NaN to empty string to so that client can understand
    df.replace(np.nan, "", regex=True, inplace=True)

    if data_type == "TimeSeries":
        # In TypeScript:
        # export type TimeSeriesValue = string | number | null;
        # export type TimeSeriesPoints = TimeSeriesValue[][];
        # export interface TimeSeries {
        #   target: string;
        #   datapoints: TimeSeriesPoints;
        #   unit?: string;
        # }
        # [TimeSeries] body must be a list, an element is a dict with 2 fields
        # . 'target' = name of a series
        # . 'datapoint' = the 2D data [row][col]
        # . 'unit' = (optional)
        # {'target': name, 'datapoints': datapoints})
        # DataFrame
        """
      https://github.com/grafana/grafana/blob/master/packages/grafana-data/src/dataframe/processDataFrame.ts
      {
        name: timeSeries.target || (timeSeries as any).name,
        refId: timeSeries.refId,
        meta: timeSeries.meta,
        fields,
        length: values.length, // # rows in DataFrame
      };
      which means we return a dict
      {
      'name': name,
      'refId': refId,
      'meta': any metadata,
      'length': numeric, // # rows in DataFrame
      'fields': [
        {
        'name': col-name, // e.g. 'Time'
        'type': 'fieldtype', //see above
        'config': {}, //optional
        'values': [list-of-values]
        },
        {
        'name': col-name, //e.g. 'Value'
        'type': 'fieldtype', //see above
          config: {
            unit: "a unit-here",
          },
        'values': [list-of-values]
        'labels': 'original a 'tag' attribute in timeSeries'
        }
      ]
      }

      """

        time_col = df.columns[0]
        if "time_column" in fullquery:
            tmp = fullquery["time_column"].strip()
            if len(tmp) > 0:
                time_col = tmp
        if time_col in columns_from_to:
            time_col = columns_from_to[time_col]
        df = revise_time_column(time_col, df)

        logger.debug("========= PRINT result of sql_stmt ============")
        logger.debug(type(df))
        logger.debug(".. .first 5 rows")
        logger.debug(df.head(5))
        logger.debug("========= END PRINT result of sql_stmt ============")

        name = "series" + fullquery["refId"]
        col_names = list(df.columns)

        index = col_names.index(time_col)
        # IMPORTANT: 2nd column must be timestamp
        if index != 1:
            tmp = col_names[1]
            col_names[1] = time_col
            col_names[index] = tmp

        if len(col_names) > 2:
            # process MTS (multi-time-series)
            metrics_col = df.columns[2]
            if "metrics_column" in fullquery:
                tmp = fullquery["metrics_column"].strip()
                if len(tmp) > 0:
                    metrics_col = tmp
            index = col_names.index(metrics_col)
            if index == 0:
                tmp = col_names[2]
                col_names[2] = metrics_col
                col_names[index] = tmp
            col_names = col_names[0:2]
            # try returning multiple time-series
            metrics = df[metrics_col].unique()
            result = []
            for met in metrics:
                name = met
                df_tmp = df[df[metrics_col].eq(met)]
                datapoints = df_tmp[col_names].values.tolist()
                result.append({"target": str(name), "datapoints": datapoints})
        else:
            # process STS (single TS)
            datapoints = df[col_names].values.tolist()
            # remember that an HTTP request can contain multiple queries, i.e. targets is a list
            # that's why the body result should be a list
            result = {"target": str(name), "datapoints": datapoints}

    elif data_type == "TableData":
        # [TableData] body must be a list, an element is a dict with 3 fields
        # .  'type': 'table' or 'timeseries'
        # .  'columns': a list of len = number of columns, each element is a dict of 2 entries:
        #        'text' : field-name, 'type': a string representatin of 'time',
        #        'string', 'number' [a value provided by FieldType in Grafana]
        # . 'rows' : a list, of len = number of rows, and each entry is a list of values in one row
        # 'series A': [{
        #      "columns":[
        #        {"text":"Time","type":"time"},
        #        {"text":"Country","type":"string"},
        #        {"text":"Number","type":"number"}
        #      ],
        #      "rows":[
        #        [1234567,"SE",123],
        #        [1234567,"DE",231],
        #        [1234567,"US",321]
        #      ],
        #      "type":"table"
        #      }],
        # body = json_dumps(tabular_data[series])
        time_col = ""
        if "time_column" in fullquery:
            tmp = fullquery["time_column"].strip()
            if len(tmp) > 0:
                time_col = tmp
            if time_col in columns_from_to:
                time_col = columns_from_to[time_col]
            df = revise_time_column(time_col, df)
        mdict = {}
        mdict["columns"] = []
        y = build_table_schema(df)
        for col in y["fields"]:
            if col["name"] == "index":
                continue
            x = {}
            x["text"] = col["name"]
            stype = ""
            if col["type"] in ["integer", "number"]:
                stype = "number"
            elif col["type"] in ["datetime"] or col["name"] == time_col:
                stype = "time"
            elif col["type"] in ["string"]:
                stype = "string"
            elif col["type"] in ["boolean"]:
                stype = "boolean"
            else:
                print("col: ", col["type"])
                logger.info("col: ", col["type"])
                assert 0
            x["type"] = stype
            mdict["columns"].append(x)
        mdict["rows"] = df.values.tolist()
        result = mdict
        if DEBUG:
            logger.debug("=====")
            logger.debug(".. print first 5 rows")
            # don't print too long result
            import pprint

            pprint.pprint(result["columns"], width=1)
            pprint.pprint(len(result["rows"]))
            # pprint.pprint(result['rows'][1:5], width=1, depth=1)

    return result, None


if __name__ == "__main__":
    # run(app=app, host='localhost', port=18081,debug=True)
    # run(app=app, host='localhost', port=18081, server='gevent')
    if cmd_args.ssl is False:
        run(app=app, host="0.0.0.0", port=18081, server="gevent")
    else:
        run(
            app=app,
            host="0.0.0.0",
            port=18081,
            server="gevent",
            certfile="cert.pem",
            keyfile="key.pem",
        )
    # run(app=app, host='0.0.0.0', port=18081, server='sslwebserver')  # asynchronous I/O
    # run(app=app, host='0.0.0.0', port=18081, server='wsgiref',  reloader=True)  # single-threaded
    # run(app=app, host='0.0.0.0', port=18081, server='wsgiref')  # single-threaded
