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
# flake8: noqa F522, E203
import re
import threading

from isodate import ISO8601Error

try:
    from .SQLQuery import SQLQuery
    from .sql_magic import print_sql
except Exception:
    from SQLQuery import SQLQuery
    from sql_magic import print_sql

lock = threading.Lock()


class SQLClientTimeSeries(SQLQuery):
    """This class augments SQLClient with time-series functionality
    """

    def __init__(
        self,
        api_key,
        instance_crn,
        target_cos_url=None,
        max_concurrent_jobs=4,
        max_tries=1,
        iam_max_tries=1,
        thread_safe=False,
        client_info="TimeSeries Cloud SQL Query Python",
    ):
        SQLQuery.__init__(
            self,
            api_key=api_key,
            instance_crn=instance_crn,
            target_cos_url=target_cos_url,
            max_concurrent_jobs=max_concurrent_jobs,
            max_tries=max_tries,
            iam_max_tries=iam_max_tries,
            thread_safe=thread_safe,
            client_info=client_info,
        )

    def _get_ts_datasource(
        self,
        table_name,
        key,
        time_stamp,
        observation,
        cos_out,
        granularity="raw",
        where_clause="",
        ops="avg",
        dry_run=False,
        keep_col_names: bool = True,
        cast_observation=None,
        num_objects=None,
        num_rows=None,
    ):
        """
        Prepare the data source for time-series in the next-query

        It will returns the data source in 3 columns: field_name, time_stamp, observation

        Parameters
        --------------
        table: str
            The catalog table name or the view-table that you generate from the WITH clause via :meth:`with_` method
        key: str
            The column name being used as the key, and is maped to `field_name`
        time_stamp: str
            The column name being used as timetick, and is mapped to `time_stamp`
        observation: str
            The column name being used as value, and is maped to `observation`
        cos_out: str
            The COS URL where the data is copied to - later as data source
        granularity: str
            There are 2 options:

            * a value in one of ["raw", "per_min", "per_<x>min", "per_sec", "per_<x>sec", "per_hour", "per_<x>hour"]
            with <x> is a number divided by 60, e.g. 10, 15
            * a value of "per_day"

            * a value that follows ISO 8601 'duration', e.g. PT1M, PT1S, PT2H
        ops: str
            The aggregation method: "avg", "sum", "max", "min", "count"
        dry_run: bool, optional
            This option, once selected as True, returns the internally generated SQL statement, and no job is queried.
        num_objects: None or int
            The number of objects to be created for storing the data. Using `num_objects` and `num_rows` are exclusive.
        num_rows: None or int
            The number of rows for each object to be created for storing the data. Using `num_objects` and `num_rows` are exclusive.
        keep_col_names: bool, optional (False)
            By default, all 3 original column names are maintained.
            If you set to false, they are mapped to `field_name` (for key),
            `time_stamp` and `observation`, respectively.
        cast_observation: str, optional=None
            The type to be casted for the `observation` column

        Returns
        ----------
        str
            The COS_URL where the data with 3 fields (key, time_stamp, observation)
            and can be digested into time-series via TIME_SERIES_FORMAT(key, timestick, value)

        Raises
        ------
        isodate.ISO8601Error:
            granularity input is not a valid ISO 8601-compliant value

        """
        tmp_cos = self.target_cos_url
        if num_objects is None and num_rows is None:
            print("provide at least `num_objects` or `num_rows`")
            assert 0
        if num_objects is not None and num_rows is not None:
            print("can't use both `num_objects` and `num_rows`")
            assert 0

        if granularity == "raw":
            pass
        elif granularity == "per_min":
            pass
        if time_stamp in self._unixtime_columns:
            #  -- convert unix-time in ms to sec
            time_info = "cast({time_stamp}/1000 as timestamp)".format(
                time_stamp=time_stamp
            )
        else:
            time_info = "{time_stamp}".format(time_stamp=time_stamp)
        if keep_col_names is True:
            key_col = "field_name as {key}".format(key=key)
            obs_col = "{observation}".format(observation=observation)
        else:
            key_col = "field_name, -- as {key}".format(key=key)
            obs_col = "{observation} as observation".format(observation=observation)

        if granularity == "raw":
            tmp_cos = cos_out

        if len(where_clause) == 0:
            extra_where = ""
        else:
            extra_where = "AND " + where_clause

        if num_objects:
            partition_clause = "PARTITIONED INTO {x} OBJECTS".format(x=num_objects)
        elif num_rows:
            partition_clause = "PARTITIONED EVERY {x} ROWS".format(x=num_rows)
        if cast_observation is None:
            select_stmt = """SELECT {key} as field_name,
                    {time_info} as time_stamp,
                    {observation} as observation
                FROM {table_name}
                WHERE isnotnull({key}) AND isnotnull({observation})
                {extra_where}
                INTO {cos_out} STORED AS PARQUET {partition_clause}
                """.format(
                table_name=table_name,
                cos_out=tmp_cos,
                key=key,
                observation=observation,
                time_info=time_info,
                extra_where=extra_where,
                partition_clause=partition_clause,
            )
        else:
            select_stmt = """SELECT {key} as field_name,
                    {time_info} as time_stamp,
                    cast({observation} AS {cast_observation}) as observation
                FROM {table_name}
                WHERE isnotnull({key}) AND isnotnull({observation})
                {extra_where}
                INTO {cos_out} STORED AS PARQUET {partition_clause}
                """.format(
                table_name=table_name,
                cos_out=tmp_cos,
                key=key,
                observation=observation,
                time_info=time_info,
                extra_where=extra_where,
                cast_observation=cast_observation,
                partition_clause=partition_clause,
            )
        if self._has_with_clause and not self._has_select_clause:
            self._sql_stmt = self._sql_stmt + select_stmt
        else:
            self._sql_stmt = select_stmt
        result = None
        if dry_run:
            print_sql(self._sql_stmt)
            select_container_id_full_location = "cos://dry_run/"
        else:
            result = self.execute_sql(self._sql_stmt)
            select_container_id_full_location = self.get_job(result.job_id)[
                "resultset_location"
            ]

        cos_in = ""
        if granularity == "raw":
            return result
        else:
            cos_in = select_container_id_full_location

        def query_day():
            """
            return:
                None or 'result'
            """
            nonlocal cos_in

            p = re.compile(r"per_[0-9]*day")
            p2 = re.compile(r"per_[0-9]+day")
            level = "raw"
            num_day = 1
            if p.match(granularity):
                level = "day"
                if p2.match(granularity):
                    temp = re.findall(r"\d+", granularity)
                    num_day = list(map(int, temp))[0]
                    assert 1 % num_day == 0
            else:
                if granularity[0:1].upper() == "P" and granularity[-1].upper() == "D":
                    level = "day"
                    try:
                        import isodate

                        x = isodate.parse_duration(granularity.strip())
                        num_day = int(x.total_seconds() / 60 / 60 / 24)  # (day)
                        assert 1 % num_day == 0
                    except ISO8601Error:
                        print("%s unsupported" % granularity)
                        assert 0
                else:
                    return None

            if level == "day":
                if num_day == 1:
                    sql_stmt = """
                    select
                        field_name,
                        to_date(time_stamp) as time_stamp_date,
                        {ops}(observation) as {observation}
                    from {cos_in} stored as parquet
                    group by field_name,  time_stamp_date
                    INTO {cos_out} STORED AS PARQUET {partition_clause}
                    """.format(
                        cos_in=cos_in,
                        cos_out=tmp_cos,
                        key=key,
                        observation=observation,
                        time_info=time_info,
                        partition_clause=partition_clause,
                        ops=ops,
                    )
                else:  # num_hour > 1
                    msg = "Can't use a day value > 1"
                    raise Exception(msg)
                    assert 0
                    sql_stmt = """
                    select
                        field_name,
                        to_date(time_stamp) as time_stamp_date,
                        (floor(hour(time_stamp)/{num_hour})) * {num_hour} as time_stamp_hour, -- within [current, current+{num_hour}) hour time-window
                        {ops}(observation) as {observation}
                    from {cos_in} stored as parquet
                    group by field_name,  time_stamp_date, time_stamp_hour
                    INTO {cos_out} STORED AS PARQUET {partition_clause}
                    """.format(
                        cos_in=cos_in,
                        cos_out=tmp_cos,
                        key=key,
                        observation=observation,
                        time_info=time_info,
                        num_hour=num_hour,
                        partition_clause=partition_clause,
                        ops=ops,
                    )
                if dry_run:
                    print_sql(sql_stmt)
                    result = None
                else:
                    result = self.execute_sql(sql_stmt)

                # Restore timestamp as single column
                if dry_run:
                    cos_in = "cos://dry_run/"
                else:
                    cos_in = self.get_job(result.job_id)["resultset_location"]
                if keep_col_names is True:
                    datetime_col = """to_timestamp(concat(date(time_stamp_date), " ", "00:00"), "yyyy-MM-dd HH:mm") as {time_stamp}""".format(
                        time_stamp=time_stamp
                    )
                else:
                    datetime_col = """to_timestamp(concat(date(time_stamp_date), " ", "00:00"), "yyyy-MM-dd HH:mm") as time_stamp"""
                sql_stmt = """
                select
                    {key_col},
                    {datetime_col},
                    {obs_col}
                from {cos_in} stored as parquet
                INTO {cos_out} STORED AS PARQUET {partition_clause}
                """.format(
                    cos_in=cos_in,
                    cos_out=cos_out,
                    key_col=key_col,
                    datetime_col=datetime_col,
                    obs_col=obs_col,
                    time_info=time_info,
                    partition_clause=partition_clause,
                )
                if dry_run:
                    print_sql(sql_stmt)
                    result = None
                else:
                    result = self.execute_sql(sql_stmt)
            return result

        def query_hour():
            """
            return:
                None or 'result'
            """
            nonlocal cos_in

            p = re.compile(r"per_[0-9]*hour")
            p2 = re.compile(r"per_[0-9]+hour")
            level = "raw"
            num_hour = 1
            if p.match(granularity):
                level = "hour"
                if p2.match(granularity):
                    temp = re.findall(r"\d+", granularity)
                    num_hour = list(map(int, temp))[0]
                    assert 24 % num_hour == 0
            else:
                if granularity[0:2].upper() == "PT" and granularity[-1].upper() == "H":
                    level = "hour"
                    try:
                        import isodate

                        x = isodate.parse_duration(granularity.strip())
                        num_hour = int(x.total_seconds() / 60 / 60)  # (hour)
                        assert 24 % num_hour == 0
                    except ISO8601Error:
                        print("%s unsupported" % granularity)
                        assert 0
                else:
                    return None

            if level == "hour":
                if num_hour == 1:
                    sql_stmt = """
                    select
                        field_name,
                        to_date(time_stamp) as time_stamp_date,
                        hour(time_stamp) as time_stamp_hour,
                        {ops}(observation) as {observation}
                    from {cos_in} stored as parquet
                    group by field_name,  time_stamp_date, time_stamp_hour
                    INTO {cos_out} STORED AS PARQUET {partition_clause}
                    """.format(
                        cos_in=cos_in,
                        cos_out=tmp_cos,
                        key=key,
                        observation=observation,
                        time_info=time_info,
                        num_hour=num_hour,
                        partition_clause=partition_clause,
                        ops=ops,
                    )
                else:  # num_hour > 1
                    sql_stmt = """
                    select
                        field_name,
                        to_date(time_stamp) as time_stamp_date,
                        (floor(hour(time_stamp)/{num_hour})) * {num_hour} as time_stamp_hour, -- within [current, current+{num_hour}) hour time-window
                        {ops}(observation) as {observation}
                    from {cos_in} stored as parquet
                    group by field_name,  time_stamp_date, time_stamp_hour
                    INTO {cos_out} STORED AS PARQUET {partition_clause}
                    """.format(
                        cos_in=cos_in,
                        cos_out=tmp_cos,
                        key=key,
                        observation=observation,
                        time_info=time_info,
                        num_hour=num_hour,
                        partition_clause=partition_clause,
                        ops=ops,
                    )
                if dry_run:
                    print_sql(sql_stmt)
                    result = None
                else:
                    result = self.execute_sql(sql_stmt)

                # Restore timestamp as single column
                if dry_run:
                    cos_in = "cos://dry_run/"
                else:
                    cos_in = self.get_job(result.job_id)["resultset_location"]
                if keep_col_names is True:
                    datetime_col = """to_timestamp(concat(date(time_stamp_date), " ", time_stamp_hour, ":00"), "yyyy-MM-dd HH:mm") as {time_stamp}""".format(
                        time_stamp=time_stamp
                    )
                else:
                    datetime_col = """to_timestamp(concat(date(time_stamp_date), " ", time_stamp_hour, ":00"), "yyyy-MM-dd HH:mm") as time_stamp"""
                sql_stmt = """
                select
                    {key_col},
                    {datetime_col},
                    {obs_col}
                from {cos_in} stored as parquet
                INTO {cos_out} STORED AS PARQUET {partition_clause}
                """.format(
                    cos_in=cos_in,
                    cos_out=cos_out,
                    key_col=key_col,
                    obs_col=obs_col,
                    datetime_col=datetime_col,
                    time_info=time_info,
                    partition_clause=partition_clause,
                )
                if dry_run:
                    print_sql(sql_stmt)
                    result = None
                else:
                    result = self.execute_sql(sql_stmt)
            return result

        def query_min():
            """
            return:
                None or 'result'
            """
            nonlocal cos_in

            p = re.compile(r"per_[0-9]*min")
            p2 = re.compile(r"per_[0-9]+min")
            level = "raw"
            num_min = 1
            if p.match(granularity):
                level = "minute"
                if p2.match(granularity):
                    temp = re.findall(r"\d+", granularity)
                    num_min = list(map(int, temp))[0]
                    assert 60 % num_min == 0
            else:
                if granularity[0:2].upper() == "PT" and granularity[-1].upper() == "M":
                    level = "minute"
                    try:
                        import isodate

                        x = isodate.parse_duration(granularity.strip())
                        num_min = int(x.total_seconds() / 60)  # (minute)
                        assert 60 % num_min == 0
                    except ISO8601Error:
                        print("%s unsupported" % granularity)
                        assert 0
                else:
                    return None

            if level == "minute":
                sql_stmt = """
                select
                    field_name,
                    to_date(time_stamp) as time_stamp_date,
                    hour(time_stamp) as time_stamp_hour,
                    (floor(minute(time_stamp)/{num_min})) * {num_min} as time_stamp_minute, -- within [current, current+{num_min}) minute time-window
                    {ops}(observation) as {observation}
                from {cos_in} stored as parquet
                group by field_name,  to_date(time_stamp), hour(time_stamp), (floor(minute(time_stamp)/{num_min})) * {num_min}
                INTO {cos_out} STORED AS PARQUET {partition_clause}
                """.format(
                    cos_in=cos_in,
                    cos_out=tmp_cos,
                    key=key,
                    observation=observation,
                    time_info=time_info,
                    num_min=num_min,
                    partition_clause=partition_clause,
                    ops=ops,
                )
                if dry_run:
                    print_sql(sql_stmt)
                    result = None
                else:
                    result = self.execute_sql(sql_stmt)

                # Restore timestamp as single column
                if dry_run:
                    cos_in = "cos://dry_run/"
                else:
                    cos_in = self.get_job(result.job_id)["resultset_location"]
                if keep_col_names is True:
                    datetime_col = """to_timestamp(concat(date(time_stamp_date), " ", time_stamp_hour, ":", time_stamp_minute), "yyyy-MM-dd HH:mm") as {time_stamp}""".format(
                        time_stamp=time_stamp
                    )
                else:
                    datetime_col = """to_timestamp(concat(date(time_stamp_date), " ", time_stamp_hour, ":", time_stamp_minute), "yyyy-MM-dd HH:mm") as time_stamp"""
                sql_stmt = """
                select
                    {key_col},
                    {datetime_col},
                    {obs_col}
                from {cos_in} stored as parquet
                INTO {cos_out} STORED AS PARQUET {partition_clause}
                """.format(
                    cos_in=cos_in,
                    cos_out=cos_out,
                    key_col=key_col,
                    obs_col=obs_col,
                    datetime_col=datetime_col,
                    time_info=time_info,
                    partition_clause=partition_clause,
                )
                if dry_run:
                    print_sql(sql_stmt)
                    result = None
                else:
                    result = self.execute_sql(sql_stmt)
            return result

        def query_sec():
            """
            return:
                None or 'result'
            """

            p = re.compile(r"per_[0-9]*sec")
            p2 = re.compile(r"per_[0-9]+sec")
            level = "raw"
            num_sec = 1
            if p.match(granularity):
                level = "sec"
                if p2.match(granularity):
                    temp = re.findall(r"\d+", granularity)
                    num_sec = list(map(int, temp))[0]
                    assert 60 % num_sec == 0
            else:
                if granularity[0:2].upper() == "PT" and granularity[-1].upper() == "S":
                    level = "sec"
                    try:
                        import isodate

                        x = isodate.parse_duration(granularity.strip())
                        num_sec = int(x.total_seconds())
                        assert 60 % num_sec == 0
                    except ISO8601Error:
                        print("%s unsupported" % granularity)
                        assert 0
                else:
                    return None

            if level == "sec":
                sql_stmt = """
                select
                    field_name,
                    to_date(time_stamp) as time_stamp_date,
                    hour(time_stamp) as time_stamp_hour,
                    minute(time_stamp) as time_stamp_minute,
                    (floor(second(time_stamp)/{num_sec})) * {num_sec} as time_stamp_second, -- within [current, current+{num_sec}) second time-window
                    {ops}(observation) as {observation}
                from {cos_in} stored as parquet
                group by field_name,  to_date(time_stamp), hour(time_stamp), minute(time_stamp), (floor(second(time_stamp)/{num_sec})) * {num_sec}
                INTO {cos_out} STORED AS PARQUET {partition_clause}
                """.format(
                    cos_in=cos_in,
                    cos_out=tmp_cos,
                    key=key,
                    observation=observation,
                    time_info=time_info,
                    num_sec=num_sec,
                    partition_clause=partition_clause,
                    ops=ops,
                )
                if dry_run:
                    print_sql(sql_stmt)
                    result = None
                else:
                    result = self.execute_sql(sql_stmt)

                # Restore timestamp as single column
                if dry_run:
                    init_cos = "cos://dry_run/"
                else:
                    init_cos = self.get_job(result.job_id)["resultset_location"]
                if keep_col_names is True:
                    datetime_col = """to_timestamp(concat(date(time_stamp_date), " ", ":".join([time_stamp_hour, time_stamp_minute, time_stamp_second]), "yyyy-MM-dd HH:mm:ss") as {time_stamp}""".format(
                        time_stamp=time_stamp
                    )
                else:
                    datetime_col = """to_timestamp(concat(date(time_stamp_date), " ", ":".join([time_stamp_hour, time_stamp_minute, time_stamp_second]), "yyyy-MM-dd HH:mm:ss") as time_stamp"""
                sql_stmt = """
                select
                    {key_col},
                    {datetime_col},
                    {obs_col}
                from {cos_in} stored as parquet
                INTO {cos_out} STORED AS PARQUET {partition_clause}
                """.format(
                    cos_in=cos_in,
                    cos_out=cos_out,
                    key_col=key_col,
                    obs_col=obs_col,
                    datetime_col=datetime_col,
                    time_info=time_info,
                    partition_clause=partition_clause,
                )
                if dry_run:
                    print_sql(sql_stmt)
                    result = None
                else:
                    result = self.execute_sql(sql_stmt)
            return result

        result = query_min()
        if result is None:
            result = query_sec()
        if result is None:
            result = query_hour()
        if result is None:
            result = query_day()
        return result

    def get_ts_datasource(
        self,
        table_name,
        key,
        time_stamp,
        observation,
        cos_out,
        granularity="raw",
        where_clause="",
        ops="avg",
        dry_run=False,
        keep_col_names: bool = True,
        cast_observation=None,
        num_objects=20,
        print_warning=True,
    ):
        """
        Prepare the data source for time-series in the next-query, in that the result is
        broken down into multiple objects using `num_objects` as the criteria

        It will returns the data source in 3 columns:
            * keep_col_names <- False: use exact values below
                field_name, time_stamp, observation
            * keep_col_names <- True: use the values passed via arguments
                <key>, <time_stamp>, <observation>

        Parameters
        --------------
        table: str
            The catalog table name
        key: str
            The column name being used as the key
        time_stamp: str
            The column name being used as timestick
        observation: str
            The column name being used as value
        cast_observation: str, optional=None
            The type to be casted for the `observation` column
        cos_out: str
            The COS URL where the data is copied to - later as data source
        granularity: str
            a value in one of ["raw", "per_min", "per_<x>min", "per_sec", "per_<x>sec"]
            with <x> is a number divided by 60, e.g. 10, 15
        dry_run: bool, optional
            This option, once selected as True, returns the internally generated SQL statement, and no job is queried.
        num_objects: int, optional
            The number of objects to be created for storing the data
        print_warning: bool, default=True
            print a warning or not
        keep_col_names: bool, optional (False)
            By default, all 3 original column names are maintained.
            If you set to false, they are mapped to `field_name` (for key),
            `time_stamp` and `observation`, respectively.

        Returns
        ----------
        str
            The COS_URL where the data with 3 fields (key, time_stamp, observation)
            and can be digested into time-series via TIME_SERIES_FORMAT(key, timestick, value)
        """
        if len(self._unixtime_columns) == 0 and print_warning is True:
            msg = (
                "WARNING: You may want to assign the list of columns to`.columns_in_unixtime`",
                " to let the SQL client know what columns are timestamp and in UNIX time format",
            )
            print(msg)

        return self._get_ts_datasource_v3(
            table_name,
            key,
            time_stamp,
            observation,
            cos_out,
            granularity,
            where_clause,
            ops,
            dry_run,
            num_objects=num_objects,
            cast_observation=cast_observation,
            keep_col_names=keep_col_names,
        )

    def _get_ts_datasource_v2(
        self,
        table_name,
        key,
        time_stamp,
        observation,
        cos_out,
        granularity="raw",
        where_clause="",
        ops="avg",
        dry_run=False,
        keep_col_names: bool = True,
        cast_observation=None,
        num_objects=None,
        num_rows=None,
    ):
        """
        Prepare the data source for time-series in the next-query

        It will returns the data source in 3 columns: field_name, time_stamp, observation

        Parameters
        --------------
        table: str
            The catalog table name or the view-table that you generate from the WITH clause via :meth:`with_` method
        key: str
            The column name being used as the key, and is maped to `field_name`
        time_stamp: str
            The column name being used as timetick, and is mapped to `time_stamp`
        observation: str
            The column name being used as value, and is maped to `observation`
        cos_out: str
            The COS URL where the data is copied to - later as data source
        granularity: str
            There are 2 options:

            * a value in one of ["raw", "per_min", "per_<x>min", "per_sec", "per_<x>sec", "per_hour", "per_<x>hour"]
            with <x> is a number divided by 60, e.g. 10, 15
            * a value of "per_day"

            * a value that follows ISO 8601 'duration', e.g. PT1M, PT1S, PT2H
        ops: str
            The aggregation method: "avg", "sum", "max", "min", "count"
        dry_run: bool, optional
            This option, once selected as True, returns the internally generated SQL statement, and no job is queried.
        num_objects: None or int
            The number of objects to be created for storing the data. Using `num_objects` and `num_rows` are exclusive.
        num_rows: None or int
            The number of rows for each object to be created for storing the data. Using `num_objects` and `num_rows` are exclusive.
        keep_col_names: bool, optional (False)
            By default, all 3 original column names are maintained.
            If you set to false, they are mapped to `field_name` (for key),
            `time_stamp` and `observation`, respectively.
        cast_observation: str, optional=None
            The type to be casted for the `observation` column

        Returns
        ----------
        str
            The COS_URL where the data with 3 fields (key, time_stamp, observation)
            and can be digested into time-series via TIME_SERIES_FORMAT(key, timestick, value)

        Raises
        ------
        ISO8601Error
            granularity input is not a valid ISO 8601-compliant value

        """

        """
        WITH tmp_A AS (SELECT storage_account_id as field_name,
                cast(timestamp_finish/1000 as timestamp) as time_stamp,
                request_latency as observation
            FROM cos_cx_exp
            WHERE isnotnull(storage_account_id) AND isnotnull(request_latency)
            AND Year=2020 and Month=09)
    Select                        field_name,
                        to_date(time_stamp) as time_stamp_date,
                        max(observation) as request_latency
                    from tmp_A
                    group by field_name,  time_stamp_date
                    INTO cos://us-south/customer-exp STORED AS PARQUET PARTITIONED INTO 20 OBJECTS

        """
        """
        WITH table_A AS
      (SELECT storage_account_id AS field_name,
              cast(timestamp_finish/1000 AS TIMESTAMP) AS time_stamp,
              request_latency AS observation
       FROM cos_cx_exp
       WHERE isnotnull(storage_account_id)
         AND isnotnull(request_latency)
         AND YEAR=2020
         AND MONTH=09
         AND DAY<5 INTO cos://us-south/customer-exp STORED AS PARQUET PARTITIONED INTO 20 OBJECTS)
    SELECT field_name,
           to_date(time_stamp) AS time_stamp_date,
           hour(time_stamp) AS time_stamp_hour,
           minute(time_stamp) AS time_stamp_minute,
           (floor(second(time_stamp)/1)) * 1 AS time_stamp_second, max(observation) AS request_latency
    FROM table_A stored AS parquet
    GROUP BY field_name,
             to_date(time_stamp),
             hour(time_stamp),
             minute(time_stamp),
             (floor(second(time_stamp)/1)) * 1 INTO cos://us-south/customer-exp STORED AS PARQUET PARTITIONED INTO 20 OBJECTS

    SELECT field_name, to_timestamp(concat(date(time_stamp_date), " ", ":".join([time_stamp_hour, time_stamp_minute, time_stamp_second]), "yyyy-MM-dd HH:mm:ss") AS time_stamp,
                                    request_latency AS observation
    FROM table_A stored AS parquet INTO cos://us-south/customer-exp STORED AS PARQUET PARTITIONED INTO 20 OBJECTS
        """
        tmp_cos = self.target_cos_url
        if num_objects is None and num_rows is None:
            print("provide at least `num_objects` or `num_rows`")
            assert 0
        if num_objects is not None and num_rows is not None:
            print("can't use both `num_objects` and `num_rows`")
            assert 0

        if granularity == "raw":
            pass
        elif granularity == "per_min":
            pass
        if time_stamp in self._unixtime_columns:
            #  -- convert unix-time in ms to sec
            time_info = "cast({time_stamp}/1000 as timestamp)".format(
                time_stamp=time_stamp
            )
        else:
            time_info = "{time_stamp}".format(time_stamp=time_stamp)
        if keep_col_names is True:
            key_col = "field_name as {key}".format(key=key)
            obs_col = "{observation}".format(observation=observation)
        else:
            key_col = "field_name, -- as {key}".format(key=key)
            obs_col = "{observation} as observation".format(observation=observation)

        if granularity == "raw":
            tmp_cos = cos_out

        if len(where_clause) == 0:
            extra_where = ""
        else:
            extra_where = "AND " + where_clause

        if num_objects:
            partition_clause = "PARTITIONED INTO {x} OBJECTS".format(x=num_objects)
        elif num_rows:
            partition_clause = "PARTITIONED EVERY {x} ROWS".format(x=num_rows)
        if cast_observation is None:
            select_stmt = """SELECT {key} as field_name,
                    {time_info} as time_stamp,
                    {observation} as observation
                FROM {table_name}
                WHERE isnotnull({key}) AND isnotnull({observation})
                {extra_where}
                """
        else:
            select_stmt = """SELECT {key} as field_name,
                    {time_info} as time_stamp,
                    cast({observation} as {cast_observation}) as observation
                FROM {table_name}
                WHERE isnotnull({key}) AND isnotnull({observation})
                {extra_where}
                """
        view_stmt = ""
        if self._has_with_clause and not self._has_select_clause:
            # don't support this path
            assert 0
            # self._sql_stmt = self._sql_stmt + select_stmt
        else:
            # self._sql_stmt = select_stmt
            view_stmt = select_stmt
        result = None
        # if dry_run:
        #    print_sql(self._sql_stmt)
        #    select_container_id_full_location = "cos://dry_run/"
        # else:
        #    result = self.execute_sql(self._sql_stmt)
        #    select_container_id_full_location = self.get_job(result.job_id)['resultset_location']

        # cos_in = ""
        if granularity == "raw":
            select_stmt += """
            INTO {cos_out} STORED AS PARQUET {partition_clause}
            """
            select_stmt = select_stmt.format(
                table_name=table_name,
                cos_out=tmp_cos,
                key=key,
                observation=observation,
                time_info=time_info,
                extra_where=extra_where,
                cast_observation=cast_observation,
                partition_clause=partition_clause,
            )
            if dry_run:
                # print_sql(self._sql_stmt)
                print_sql(select_stmt)
            else:
                # result = self.execute_sql(self._sql_stmt)
                result = self.execute_sql(select_stmt)
            return result
        else:
            select_stmt = select_stmt.format(
                table_name=table_name,
                cos_out=tmp_cos,
                key=key,
                observation=observation,
                time_info=time_info,
                extra_where=extra_where,
                cast_observation=cast_observation,
                partition_clause=partition_clause,
            )
            # cos_in = select_container_id_full_location
            # self._sql_stmt = "WITH table_A AS (" + select_stmt + ")"
            view_stmt = "WITH table_A AS (" + select_stmt + ")"
            cos_in = "table_A"

        def query_day():
            """
            return:
                None or 'result'
            """
            nonlocal cos_in

            p = re.compile(r"per_[0-9]*day")
            p2 = re.compile(r"per_[0-9]+day")
            level = "raw"
            num_day = 1
            if p.match(granularity):
                level = "day"
                if p2.match(granularity):
                    temp = re.findall(r"\d+", granularity)
                    num_day = list(map(int, temp))[0]
                    assert 1 % num_day == 0
            else:
                if granularity[0:1].upper() == "P" and granularity[-1].upper() == "D":
                    level = "day"
                    try:
                        import isodate

                        x = isodate.parse_duration(granularity.strip())
                        num_day = int(x.total_seconds() / 60 / 60 / 24)  # (day)
                        assert 1 % num_day == 0
                    except ISO8601Error:
                        print("%s unsupported" % granularity)
                        assert 0
                else:
                    return None

            if level == "day":
                if num_day == 1:
                    sql_stmt = """
                    select
                        field_name,
                        to_date(time_stamp) as time_stamp_date,
                        {ops}(observation) as {observation}
                    from {cos_in} stored as parquet
                    group by field_name,  time_stamp_date
                    INTO {cos_out} STORED AS PARQUET {partition_clause}
                    """.format(
                        cos_in=cos_in,
                        cos_out=tmp_cos,
                        key=key,
                        observation=observation,
                        time_info=time_info,
                        partition_clause=partition_clause,
                        ops=ops,
                    )
                else:  # num_hour > 1
                    msg = "Can't use a day value > 1"
                    raise Exception(msg)
                    assert 0
                    sql_stmt = """
                    select
                        field_name,
                        to_date(time_stamp) as time_stamp_date,
                        (floor(hour(time_stamp)/{num_hour})) * {num_hour} as time_stamp_hour, -- within [current, current+{num_hour}) hour time-window
                        {ops}(observation) as {observation}
                    from {cos_in} stored as parquet
                    group by field_name,  time_stamp_date, time_stamp_hour
                    INTO {cos_out} STORED AS PARQUET {partition_clause}
                    """.format(
                        cos_in=cos_in,
                        cos_out=tmp_cos,
                        key=key,
                        observation=observation,
                        time_info=time_info,
                        num_hour=num_hour,
                        partition_clause=partition_clause,
                        ops=ops,
                    )
                sql_stmt = view_stmt + "\n" + sql_stmt
                if dry_run:
                    print_sql(sql_stmt)
                    result = None
                else:
                    result = self.execute_sql(sql_stmt)

                # Restore timestamp as single column
                if dry_run:
                    cos_in = "cos://dry_run/"
                else:
                    cos_in = self.get_job(result.job_id)["resultset_location"]
                if keep_col_names is True:
                    datetime_col = """to_timestamp(concat(date(time_stamp_date), " ", "00:00"), "yyyy-MM-dd HH:mm") as {time_stamp}""".format(
                        time_stamp=time_stamp
                    )
                else:
                    datetime_col = """to_timestamp(concat(date(time_stamp_date), " ", "00:00"), "yyyy-MM-dd HH:mm") as time_stamp"""
                sql_stmt = """
                select
                    {key_col},
                    {datetime_col},
                    {obs_col}
                from {cos_in} stored as parquet
                INTO {cos_out} STORED AS PARQUET {partition_clause}
                """.format(
                    cos_in=cos_in,
                    cos_out=cos_out,
                    key_col=key_col,
                    datetime_col=datetime_col,
                    obs_col=obs_col,
                    time_info=time_info,
                    partition_clause=partition_clause,
                )
                if dry_run:
                    print_sql(sql_stmt)
                    result = None
                else:
                    result = self.execute_sql(sql_stmt)
            return result

        def query_hour():
            """
            return:
                None or 'result'
            """
            nonlocal cos_in

            p = re.compile(r"per_[0-9]*hour")
            p2 = re.compile(r"per_[0-9]+hour")
            level = "raw"
            num_hour = 1
            if p.match(granularity):
                level = "hour"
                if p2.match(granularity):
                    temp = re.findall(r"\d+", granularity)
                    num_hour = list(map(int, temp))[0]
                    assert 24 % num_hour == 0
            else:
                if granularity[0:2].upper() == "PT" and granularity[-1].upper() == "H":
                    level = "hour"
                    try:
                        import isodate

                        x = isodate.parse_duration(granularity.strip())
                        num_hour = int(x.total_seconds() / 60 / 60)  # (hour)
                        assert 24 % num_hour == 0
                    except ISO8601Error:
                        print("%s unsupported" % granularity)
                        assert 0
                else:
                    return None

            if level == "hour":
                if num_hour == 1:
                    sql_stmt = """
                    select
                        field_name,
                        to_date(time_stamp) as time_stamp_date,
                        hour(time_stamp) as time_stamp_hour,
                        {ops}(observation) as {observation}
                    from {cos_in} stored as parquet
                    group by field_name,  time_stamp_date, time_stamp_hour
                    INTO {cos_out} STORED AS PARQUET {partition_clause}
                    """.format(
                        cos_in=cos_in,
                        cos_out=tmp_cos,
                        key=key,
                        observation=observation,
                        time_info=time_info,
                        num_hour=num_hour,
                        partition_clause=partition_clause,
                        ops=ops,
                    )
                else:  # num_hour > 1
                    sql_stmt = """
                    select
                        field_name,
                        to_date(time_stamp) as time_stamp_date,
                        (floor(hour(time_stamp)/{num_hour})) * {num_hour} as time_stamp_hour, -- within [current, current+{num_hour}) hour time-window
                        {ops}(observation) as {observation}
                    from {cos_in} stored as parquet
                    group by field_name,  time_stamp_date, time_stamp_hour
                    INTO {cos_out} STORED AS PARQUET {partition_clause}
                    """.format(
                        cos_in=cos_in,
                        cos_out=tmp_cos,
                        key=key,
                        observation=observation,
                        time_info=time_info,
                        num_hour=num_hour,
                        partition_clause=partition_clause,
                        ops=ops,
                    )
                sql_stmt = view_stmt + "\n" + sql_stmt
                if dry_run:
                    print_sql(sql_stmt)
                    result = None
                else:
                    result = self.execute_sql(sql_stmt)

                # Restore timestamp as single column
                if dry_run:
                    cos_in = "cos://dry_run/"
                else:
                    cos_in = self.get_job(result.job_id)["resultset_location"]
                if keep_col_names is True:
                    datetime_col = """to_timestamp(concat(date(time_stamp_date), " ", time_stamp_hour, ":00"), "yyyy-MM-dd HH:mm") as {time_stamp}""".format(
                        time_stamp=time_stamp
                    )
                else:
                    datetime_col = """to_timestamp(concat(date(time_stamp_date), " ", time_stamp_hour, ":00"), "yyyy-MM-dd HH:mm") as time_stamp"""
                sql_stmt = """
                select
                    {key_col},
                    {datetime_col},
                    {obs_col}
                from {cos_in} stored as parquet
                INTO {cos_out} STORED AS PARQUET {partition_clause}
                """.format(
                    cos_in=cos_in,
                    cos_out=cos_out,
                    key_col=key_col,
                    obs_col=obs_col,
                    datetime_col=datetime_col,
                    time_info=time_info,
                    partition_clause=partition_clause,
                )
                if dry_run:
                    print_sql(sql_stmt)
                    result = None
                else:
                    result = self.execute_sql(sql_stmt)
            return result

        def query_min():
            """
            return:
                None or 'result'
            """
            nonlocal cos_in

            p = re.compile(r"per_[0-9]*min")
            p2 = re.compile(r"per_[0-9]+min")
            level = "raw"
            num_min = 1
            if p.match(granularity):
                level = "minute"
                if p2.match(granularity):
                    temp = re.findall(r"\d+", granularity)
                    num_min = list(map(int, temp))[0]
                    assert 60 % num_min == 0
            else:
                if granularity[0:2].upper() == "PT" and granularity[-1].upper() == "M":
                    level = "minute"
                    try:
                        import isodate

                        x = isodate.parse_duration(granularity.strip())
                        num_min = int(x.total_seconds() / 60)  # (minute)
                        assert 60 % num_min == 0
                    except ISO8601Error:
                        print("%s unsupported" % granularity)
                        assert 0
                else:
                    return None

            if level == "minute":
                sql_stmt = """
                select
                    field_name,
                    to_date(time_stamp) as time_stamp_date,
                    hour(time_stamp) as time_stamp_hour,
                    (floor(minute(time_stamp)/{num_min})) * {num_min} as time_stamp_minute, -- within [current, current+{num_min}) minute time-window
                    {ops}(observation) as {observation}
                from {cos_in} stored as parquet
                group by field_name,  to_date(time_stamp), hour(time_stamp), (floor(minute(time_stamp)/{num_min})) * {num_min}
                INTO {cos_out} STORED AS PARQUET {partition_clause}
                """.format(
                    cos_in=cos_in,
                    cos_out=tmp_cos,
                    key=key,
                    observation=observation,
                    time_info=time_info,
                    num_min=num_min,
                    partition_clause=partition_clause,
                    ops=ops,
                )
                sql_stmt = view_stmt + "\n" + sql_stmt
                if dry_run:
                    print_sql(sql_stmt)
                    result = None
                else:
                    result = self.execute_sql(sql_stmt)

                # Restore timestamp as single column
                if dry_run:
                    cos_in = "cos://dry_run/"
                else:
                    cos_in = self.get_job(result.job_id)["resultset_location"]
                if keep_col_names is True:
                    datetime_col = """to_timestamp(concat(date(time_stamp_date), " ", time_stamp_hour, ":", time_stamp_minute), "yyyy-MM-dd HH:mm") as {time_stamp}""".format(
                        time_stamp=time_stamp
                    )
                else:
                    datetime_col = """to_timestamp(concat(date(time_stamp_date), " ", time_stamp_hour, ":", time_stamp_minute), "yyyy-MM-dd HH:mm") as time_stamp"""
                sql_stmt = """
                select
                    {key_col},
                    {datetime_col},
                    {obs_col}
                from {cos_in} stored as parquet
                INTO {cos_out} STORED AS PARQUET {partition_clause}
                """.format(
                    cos_in=cos_in,
                    cos_out=cos_out,
                    key_col=key_col,
                    obs_col=obs_col,
                    datetime_col=datetime_col,
                    time_info=time_info,
                    partition_clause=partition_clause,
                )
                if dry_run:
                    print_sql(sql_stmt)
                    result = None
                else:
                    result = self.execute_sql(sql_stmt)
            return result

        def query_sec():
            """
            return:
                None or 'result'
            """

            p = re.compile(r"per_[0-9]*sec")
            p2 = re.compile(r"per_[0-9]+sec")
            level = "raw"
            num_sec = 1
            if p.match(granularity):
                level = "sec"
                if p2.match(granularity):
                    temp = re.findall(r"\d+", granularity)
                    num_sec = list(map(int, temp))[0]
                    assert 60 % num_sec == 0
            else:
                if granularity[0:2].upper() == "PT" and granularity[-1].upper() == "S":
                    level = "sec"
                    try:
                        import isodate

                        x = isodate.parse_duration(granularity.strip())
                        num_sec = int(x.total_seconds())
                        assert 60 % num_sec == 0
                    except ISO8601Error:
                        print("%s unsupported" % granularity)
                        assert 0
                else:
                    return None

            if level == "sec":
                sql_stmt = """
                select
                    field_name,
                    to_date(time_stamp) as time_stamp_date,
                    hour(time_stamp) as time_stamp_hour,
                    minute(time_stamp) as time_stamp_minute,
                    (floor(second(time_stamp)/{num_sec})) * {num_sec} as time_stamp_second, -- within [current, current+{num_sec}) second time-window
                    {ops}(observation) as {observation}
                from {cos_in} stored as parquet
                group by field_name,  to_date(time_stamp), hour(time_stamp), minute(time_stamp), (floor(second(time_stamp)/{num_sec})) * {num_sec}
                INTO {cos_out} STORED AS PARQUET {partition_clause}
                """.format(
                    cos_in=cos_in,
                    cos_out=tmp_cos,
                    key=key,
                    observation=observation,
                    time_info=time_info,
                    num_sec=num_sec,
                    partition_clause=partition_clause,
                    ops=ops,
                )
                sql_stmt = view_stmt + "\n" + sql_stmt
                if dry_run:
                    print_sql(sql_stmt)
                    result = None
                else:
                    result = self.execute_sql(sql_stmt)

                # Restore timestamp as single column
                if dry_run:
                    init_cos = "cos://dry_run/"
                else:
                    init_cos = self.get_job(result.job_id)["resultset_location"]
                if keep_col_names is True:
                    datetime_col = """to_timestamp(concat(date(time_stamp_date), " ", ":".join([time_stamp_hour, time_stamp_minute, time_stamp_second]), "yyyy-MM-dd HH:mm:ss") as {time_stamp}""".format(
                        time_stamp=time_stamp
                    )
                else:
                    datetime_col = """to_timestamp(concat(date(time_stamp_date), " ", ":".join([time_stamp_hour, time_stamp_minute, time_stamp_second]), "yyyy-MM-dd HH:mm:ss") as time_stamp"""
                sql_stmt = """
                select
                    {key_col},
                    {datetime_col},
                    {obs_col}
                from {cos_in} stored as parquet
                INTO {cos_out} STORED AS PARQUET {partition_clause}
                """.format(
                    cos_in=cos_in,
                    cos_out=cos_out,
                    key_col=key_col,
                    obs_col=obs_col,
                    datetime_col=datetime_col,
                    time_info=time_info,
                    partition_clause=partition_clause,
                )
                if dry_run:
                    print_sql(sql_stmt)
                    result = None
                else:
                    result = self.execute_sql(sql_stmt)
            return result

        result = query_min()
        if result is None:
            result = query_sec()
        if result is None:
            result = query_hour()
        if result is None:
            result = query_day()
        return result

    def _get_ts_datasource_v3(
        self,
        table_name,
        key,
        time_stamp,
        observation,
        cos_out,
        granularity="raw",
        where_clause="",
        ops="avg",
        dry_run=False,
        keep_col_names: bool = True,
        cast_observation=None,
        num_objects=None,
        num_rows=None,
    ):
        """
        Prepare the data source for time-series in the next-query

        It will returns the data source in 3 columns: field_name, time_stamp, observation

        Parameters
        --------------
        table: str
            The catalog table name or the view-table that you generate from the WITH clause via :meth:`with_` method
        key: str
            The column name being used as the key, and is maped to `field_name`
        time_stamp: str
            The column name being used as timetick, and is mapped to `time_stamp`
        observation: str
            The column name being used as value, and is maped to `observation`
        cast_observation: str, optional=None
            The type to be casted for the `observation` column
        cos_out: str
            The COS URL where the data is copied to - later as data source
        granularity: str
            There are 2 options:

            * a value in one of ["raw", "per_min", "per_<x>min", "per_sec", "per_<x>sec", "per_hour", "per_<x>hour"]
            with <x> is a number divided by 60, e.g. 10, 15
            * a value of "per_day"

            * a value that follows ISO 8601 'duration', e.g. PT1M, PT1S, PT2H
        ops: str
            The aggregation method: "avg", "sum", "max", "min", "count"
        dry_run: bool, optional
            This option, once selected as True, returns the internally generated SQL statement, and no job is queried.
        num_objects: None or int
            The number of objects to be created for storing the data. Using `num_objects` and `num_rows` are exclusive.
        num_rows: None or int
            The number of rows for each object to be created for storing the data. Using `num_objects` and `num_rows` are exclusive.
        keep_col_names: bool, optional (False)
            By default, all 3 original column names are maintained.
            If you set to false, they are mapped to `field_name` (for key),
            `time_stamp` and `observation`, respectively.

        Returns
        ----------
        str
            The COS_URL where the data with 3 fields (key, time_stamp, observation)
            and can be digested into time-series via TIME_SERIES_FORMAT(key, timestick, value)

        Raises
        ------
        ISO8601Error
            granularity input is not a valid ISO 8601-compliant value

        """
        """
    WITH table_A AS
      (SELECT storage_account_id AS field_name,
              cast(timestamp_finish/1000 AS TIMESTAMP) AS time_stamp,
              request_latency AS observation
       FROM cos_cx_exp
       WHERE isnotnull(storage_account_id)
         AND isnotnull(request_latency)
         AND YEAR=2020
         AND MONTH=09
         AND DAY<5 INTO cos://us-south/customer-exp STORED AS PARQUET PARTITIONED INTO 20 OBJECTS)
    SELECT field_name,
           to_date(time_stamp) AS time_stamp_date,
           hour(time_stamp) AS time_stamp_hour,
           minute(time_stamp) AS time_stamp_minute,
           (floor(second(time_stamp)/1)) * 1 AS time_stamp_second, max(observation) AS request_latency
           to_timestamp(concat(date(time_stamp_date), " ", ":".join([time_stamp_hour, time_stamp_minute, time_stamp_second]), "yyyy-MM-dd HH:mm:ss") AS time_stamp,
    FROM table_A stored AS parquet
    GROUP BY field_name,
             to_date(time_stamp),
             hour(time_stamp),
             minute(time_stamp),
             (floor(second(time_stamp)/1)) * 1 INTO cos://us-south/customer-exp STORED AS PARQUET PARTITIONED INTO 20 OBJECTS
        """
        tmp_cos = self.target_cos_url
        if num_objects is None and num_rows is None:
            print("provide at least `num_objects` or `num_rows`")
            assert 0
        if num_objects is not None and num_rows is not None:
            print("can't use both `num_objects` and `num_rows`")
            assert 0

        if granularity == "raw":
            pass
        elif granularity == "per_min":
            pass
        if time_stamp in self._unixtime_columns:
            #  -- convert unix-time in ms to sec
            time_info = "cast({time_stamp}/1000 as timestamp)".format(
                time_stamp=time_stamp
            )
        else:
            time_info = "{time_stamp}".format(time_stamp=time_stamp)
        if keep_col_names is True:
            key_col = "field_name as {key}".format(key=key)
            obs_col = "{ops}(observation) as {observation}".format(
                observation=observation, ops=ops
            )
        else:
            key_col = "field_name, -- as {key}".format(key=key)
            obs_col = "{ops}(observation) as observation".format(
                observation=observation, ops=ops
            )

        if granularity == "raw":
            tmp_cos = cos_out

        if len(where_clause) == 0:
            extra_where = ""
        else:
            extra_where = "AND " + where_clause

        if num_objects:
            partition_clause = "PARTITIONED INTO {x} OBJECTS".format(x=num_objects)
        elif num_rows:
            partition_clause = "PARTITIONED EVERY {x} ROWS".format(x=num_rows)
        if cast_observation is None:
            select_stmt = """SELECT {key} as field_name,
                    {time_info} as time_stamp,
                    {observation} as observation
                FROM {table_name}
                WHERE isnotnull({key}) AND isnotnull({observation})
                {extra_where}
                """
        else:
            select_stmt = """SELECT {key} as field_name,
                    {time_info} as time_stamp,
                    cast({observation} as {cast_observation}) as observation
                FROM {table_name}
                WHERE isnotnull({key}) AND isnotnull({observation})
                {extra_where}
                """
        view_stmt = ""
        if self._has_with_clause and not self._has_select_clause:
            # don't support this path
            assert 0
            # self._sql_stmt = self._sql_stmt + select_stmt
        else:
            # self._sql_stmt = select_stmt
            view_stmt = select_stmt
        result = None
        # if dry_run:
        #    print_sql(self._sql_stmt)
        #    select_container_id_full_location = "cos://dry_run/"
        # else:
        #    result = self.execute_sql(self._sql_stmt)
        #    select_container_id_full_location = self.get_job(result.job_id)['resultset_location']

        # cos_in = ""
        if granularity == "raw":
            select_stmt += """
            INTO {cos_out} STORED AS PARQUET {partition_clause}
            """
            select_stmt = select_stmt.format(
                table_name=table_name,
                cos_out=tmp_cos,
                key=key,
                observation=observation,
                time_info=time_info,
                extra_where=extra_where,
                cast_observation=cast_observation,
                partition_clause=partition_clause,
            )
            if dry_run:
                # print_sql(self._sql_stmt)
                print_sql(select_stmt)
            else:
                # result = self.execute_sql(self._sql_stmt)
                result = self.execute_sql(select_stmt)
            return result
        else:
            select_stmt = select_stmt.format(
                table_name=table_name,
                cos_out=tmp_cos,
                key=key,
                observation=observation,
                time_info=time_info,
                extra_where=extra_where,
                cast_observation=cast_observation,
                partition_clause=partition_clause,
            )
            # cos_in = select_container_id_full_location
            # self._sql_stmt = "WITH table_A AS (" + select_stmt + ")"
            view_stmt = "WITH table_A AS (" + select_stmt + ")"
            cos_in = "table_A"

        def query_day():
            """
            return:
                None or 'result'
            """
            nonlocal cos_in

            p = re.compile(r"per_[0-9]*day")
            p2 = re.compile(r"per_[0-9]+day")
            level = "raw"
            num_day = 1
            if p.match(granularity):
                level = "day"
                if p2.match(granularity):
                    temp = re.findall(r"\d+", granularity)
                    num_day = list(map(int, temp))[0]
                    assert 1 % num_day == 0
            else:
                if granularity[0:1].upper() == "P" and granularity[-1].upper() == "D":
                    level = "day"
                    try:
                        import isodate

                        x = isodate.parse_duration(granularity.strip())
                        num_day = int(x.total_seconds() / 60 / 60 / 24)  # (day)
                        assert 1 % num_day == 0
                    except ISO8601Error:
                        print("%s unsupported" % granularity)
                        assert 0
                else:
                    return None

            if level == "day":
                if keep_col_names is True:
                    datetime_col = """to_timestamp(concat(date(time_stamp), " ", "00:00"), "yyyy-MM-dd HH:mm") as {time_stamp}""".format(
                        time_stamp=time_stamp
                    )
                else:
                    datetime_col = """to_timestamp(concat(date(time_stamp), " ", "00:00"), "yyyy-MM-dd HH:mm") as time_stamp"""
                if num_day == 1:
                    sql_stmt = """
                    select
                        {key_col},
                        {obs_col},
                        to_date(time_stamp) as time_stamp_date,
                    {datetime_col}
                    from {cos_in}
                    group by field_name,  to_date(time_stamp)
                    INTO {cos_out} STORED AS PARQUET {partition_clause}
                    """.format(
                        cos_in=cos_in,
                        cos_out=cos_out,
                        key_col=key_col,
                        obs_col=obs_col,
                        datetime_col=datetime_col,
                        time_info=time_info,
                        num_day=num_day,
                        partition_clause=partition_clause,
                        ops=ops,
                    )
                else:  # num_day > 1
                    msg = "Can't use a day value > 1"
                    raise Exception(msg)
                    assert 0
                    sql_stmt = """
                    select
                        {key_col},
                        {obs_col},
                        to_date(time_stamp) as time_stamp_date,
                        (floor(hour(time_stamp)/{num_hour})) * {num_hour} as time_stamp_hour, -- within [current, current+{num_hour}) hour time-window
                        {datetime_col}
                    from {cos_in}
                    group by field_name,  time_stamp_date, time_stamp_hour
                    INTO {cos_out} STORED AS PARQUET {partition_clause}
                    """.format(
                        cos_in=cos_in,
                        cos_out=cos_out,
                        key_col=key_col,
                        obs_col=obs_col,
                        datetime_col=datetime_col,
                        time_info=time_info,
                        num_day=num_day,
                        partition_clause=partition_clause,
                        ops=ops,
                    )
                sql_stmt = view_stmt + "\n" + sql_stmt
                if dry_run:
                    print_sql(sql_stmt)
                    result = None
                else:
                    result = self.execute_sql(sql_stmt)

                ## Restore timestamp as single column
                # if dry_run:
                #    cos_in = "cos://dry_run/"
                # else:
                #    cos_in = self.get_job(result.job_id)['resultset_location']
                # sql_stmt = """
                # select
                #    {key_col},
                #    {datetime_col},
                #    {obs_col}
                # from {cos_in} stored as parquet
                # INTO {cos_out} STORED AS PARQUET {partition_clause}
                # """.format(cos_in=cos_in, cos_out=cos_out, key_col=key_col, datetime_col=datetime_col, obs_col=obs_col, time_info=time_info,
                #    partition_clause=partition_clause)
                # if dry_run:
                #    print_sql(sql_stmt)
                #    result = None
                # else:
                #    result = self.execute_sql(sql_stmt)
            return result

        def query_hour():
            """
            return:
                None or 'result'
            """
            nonlocal cos_in

            p = re.compile(r"per_[0-9]*hour")
            p2 = re.compile(r"per_[0-9]+hour")
            level = "raw"
            num_hour = 1
            if p.match(granularity):
                level = "hour"
                if p2.match(granularity):
                    temp = re.findall(r"\d+", granularity)
                    num_hour = list(map(int, temp))[0]
                    assert 24 % num_hour == 0
            else:
                if granularity[0:2].upper() == "PT" and granularity[-1].upper() == "H":
                    level = "hour"
                    try:
                        import isodate

                        x = isodate.parse_duration(granularity.strip())
                        num_hour = int(x.total_seconds() / 60 / 60)  # (hour)
                        assert 24 % num_hour == 0
                    except ISO8601Error:
                        print("%s unsupported" % granularity)
                        assert 0
                else:
                    return None

            if level == "hour":
                if keep_col_names is True:
                    datetime_col = """to_timestamp(concat(date(to_date(time_stamp)), " ", hour(time_stamp), ":00"), "yyyy-MM-dd HH:mm") as {time_stamp}""".format(
                        time_stamp=time_stamp
                    )
                else:
                    datetime_col = """to_timestamp(concat(date(to_date(time_stamp)), " ", hour(time_stamp), ":00"), "yyyy-MM-dd HH:mm") as time_stamp"""
                if num_hour == 1:
                    sql_stmt = """
                    select
                        {key_col},
                        {obs_col},
                        to_date(time_stamp) as time_stamp_date,
                        hour(time_stamp) as time_stamp_hour,
                        {datetime_col}
                    from {cos_in}
                    group by field_name,  to_date(time_stamp), hour(time_stamp)
                    INTO {cos_out} STORED AS PARQUET {partition_clause}
                    """.format(
                        cos_in=cos_in,
                        cos_out=cos_out,
                        key_col=key_col,
                        obs_col=obs_col,
                        datetime_col=datetime_col,
                        time_info=time_info,
                        num_hour=num_hour,
                        partition_clause=partition_clause,
                        ops=ops,
                    )
                else:  # num_hour > 1
                    sql_stmt = """
                    select
                        {key_col},
                        {obs_col},
                        to_date(time_stamp) as time_stamp_date,
                        (floor(hour(time_stamp)/{num_hour})) * {num_hour} as time_stamp_hour, -- within [current, current+{num_hour}) hour time-window
                        {datetime_col}
                    from {cos_in}
                    group by field_name,  to_date(time_stamp), (floor(hour(time_stamp)/{num_hour})) * {num_hour}
                    INTO {cos_out} STORED AS PARQUET {partition_clause}
                    """.format(
                        cos_in=cos_in,
                        cos_out=cos_out,
                        key_col=key_col,
                        obs_col=obs_col,
                        datetime_col=datetime_col,
                        time_info=time_info,
                        num_hour=num_hour,
                        partition_clause=partition_clause,
                        ops=ops,
                    )
                sql_stmt = view_stmt + "\n" + sql_stmt
                if dry_run:
                    print_sql(sql_stmt)
                    result = None
                else:
                    result = self.execute_sql(sql_stmt)

                ## Restore timestamp as single column
                # if dry_run:
                #    cos_in = "cos://dry_run/"
                # else:
                #    cos_in = self.get_job(result.job_id)['resultset_location']
                # sql_stmt = """
                # select
                #    {key_col},
                #    {datetime_col},
                #    {obs_col}
                # from {cos_in} stored as parquet
                # INTO {cos_out} STORED AS PARQUET {partition_clause}
                # """.format(cos_in=cos_in, cos_out=cos_out, key_col=key_col, obs_col=obs_col, datetime_col=datetime_col, time_info=time_info,
                #    partition_clause=partition_clause)
                # if dry_run:
                #    print_sql(sql_stmt)
                #    result = None
                # else:
                #    result = self.execute_sql(sql_stmt)
            return result

        def query_min():
            """
            return:
                None or 'result'
            """
            nonlocal cos_in

            p = re.compile(r"per_[0-9]*min")
            p2 = re.compile(r"per_[0-9]+min")
            level = "raw"
            num_min = 1
            if p.match(granularity):
                level = "minute"
                if p2.match(granularity):
                    temp = re.findall(r"\d+", granularity)
                    num_min = list(map(int, temp))[0]
                    assert 60 % num_min == 0
            else:
                if granularity[0:2].upper() == "PT" and granularity[-1].upper() == "M":
                    level = "minute"
                    try:
                        import isodate

                        x = isodate.parse_duration(granularity.strip())
                        num_min = int(x.total_seconds() / 60)  # (minute)
                        assert 60 % num_min == 0
                    except ISO8601Error:
                        print("%s unsupported" % granularity)
                        assert 0
                else:
                    return None

            if level == "minute":
                if keep_col_names is True:
                    datetime_col = """to_timestamp(concat(date(to_date(time_stamp)), " ", hour(time_stamp), ":", (floor(minute(time_stamp)/{num_min})) * {num_min}), "yyyy-MM-dd HH:mm") as {time_stamp}""".format(
                        time_stamp=time_stamp, num_min=num_min
                    )
                else:
                    datetime_col = """to_timestamp(concat(date(to_date(time_stamp)), " ", hour(time_stamp), ":", (floor(minute(time_stamp)/{num_min})) * {num_min}), "yyyy-MM-dd HH:mm") as time_stamp""".format(
                        num_min=num_min
                    )
                sql_stmt = """
                select
                    {key_col},
                    {obs_col},
                    to_date(time_stamp) as time_stamp_date,
                    hour(time_stamp) as time_stamp_hour,
                    (floor(minute(time_stamp)/{num_min})) * {num_min} as time_stamp_minute, -- within [current, current+{num_min}) minute time-window
                    {datetime_col}
                from {cos_in}
                group by field_name,  to_date(time_stamp), hour(time_stamp), (floor(minute(time_stamp)/{num_min})) * {num_min}
                INTO {cos_out} STORED AS PARQUET {partition_clause}
                """.format(
                    cos_in=cos_in,
                    cos_out=cos_out,
                    key_col=key_col,
                    obs_col=obs_col,
                    datetime_col=datetime_col,
                    time_info=time_info,
                    num_min=num_min,
                    partition_clause=partition_clause,
                    ops=ops,
                )
                sql_stmt = view_stmt + "\n" + sql_stmt
                if dry_run:
                    print_sql(sql_stmt)
                    result = None
                else:
                    result = self.execute_sql(sql_stmt)

                ## Restore timestamp as single column
                # if dry_run:
                #    cos_in = "cos://dry_run/"
                # else:
                #    cos_in = self.get_job(result.job_id)['resultset_location']
                # sql_stmt = """
                # select
                #    {key_col},
                #    {datetime_col},
                #    {obs_col}
                # from {cos_in} stored as parquet
                # INTO {cos_out} STORED AS PARQUET {partition_clause}
                # """.format(cos_in=cos_in, cos_out=cos_out, key_col=key_col, obs_col=obs_col, datetime_col=datetime_col, time_info=time_info,
                #    partition_clause=partition_clause)
                # if dry_run:
                #    print_sql(sql_stmt)
                #    result = None
                # else:
                #    result = self.execute_sql(sql_stmt)
            return result

        def query_sec():
            """
            return:
                None or 'result'
            """

            p = re.compile(r"per_[0-9]*sec")
            p2 = re.compile(r"per_[0-9]+sec")
            level = "raw"
            num_sec = 1
            if p.match(granularity):
                level = "sec"
                if p2.match(granularity):
                    temp = re.findall(r"\d+", granularity)
                    num_sec = list(map(int, temp))[0]
                    assert 60 % num_sec == 0
            else:
                if granularity[0:2].upper() == "PT" and granularity[-1].upper() == "S":
                    level = "sec"
                    try:
                        import isodate

                        x = isodate.parse_duration(granularity.strip())
                        num_sec = int(x.total_seconds())
                        assert 60 % num_sec == 0
                    except ISO8601Error:
                        print("%s unsupported" % granularity)
                        assert 0
                else:
                    return None

            if level == "sec":
                if keep_col_names is True:
                    datetime_col = """to_timestamp(concat(date(to_date(time_stamp)), " ", ":".join([hour(time_stamp), minute(time_stamp), (floor(second(time_stamp)/{num_sec})) * {num_sec}]), "yyyy-MM-dd HH:mm:ss") as {time_stamp}""".format(
                        time_stamp=time_stamp, num_sec=num_sec
                    )
                else:
                    datetime_col = """to_timestamp(concat(date(to_date(time_stamp)), " ", ":".join([hour(time_stamp), minute(time_stamp), (floor(second(time_stamp)/{num_sec})) * {num_sec}]), "yyyy-MM-dd HH:mm:ss") as time_stamp""".format(
                        num_sec=num_sec
                    )
                sql_stmt = """
                select
                    {key_col},
                    {obs_col},
                    to_date(time_stamp) as time_stamp_date,
                    hour(time_stamp) as time_stamp_hour,
                    minute(time_stamp) as time_stamp_minute,
                    (floor(second(time_stamp)/{num_sec})) * {num_sec} as time_stamp_second, -- within [current, current+{num_sec}) second time-window,
                    {datetime_col}
                from {cos_in}
                group by field_name,  to_date(time_stamp), hour(time_stamp), minute(time_stamp), (floor(second(time_stamp)/{num_sec})) * {num_sec}
                INTO {cos_out} STORED AS PARQUET {partition_clause}
                """.format(
                    cos_in=cos_in,
                    cos_out=cos_out,
                    key_col=key_col,
                    obs_col=obs_col,
                    datetime_col=datetime_col,
                    time_info=time_info,
                    num_sec=num_sec,
                    partition_clause=partition_clause,
                    ops=ops,
                )
                sql_stmt = view_stmt + "\n" + sql_stmt
                if dry_run:
                    print_sql(sql_stmt)
                    result = None
                else:
                    result = self.execute_sql(sql_stmt)

                # # Restore timestamp as single column
                # if dry_run:
                #    init_cos = "cos://dry_run/"
                # else:
                #    init_cos = self.get_job(result.job_id)['resultset_location']
                # sql_stmt = """
                # select
                #    {key_col},
                #    {datetime_col},
                #    {obs_col}
                # from {cos_in} stored as parquet
                # INTO {cos_out} STORED AS PARQUET {partition_clause}
                # """.format(cos_in=cos_in, cos_out=cos_out, key_col=key_col, obs_col=obs_col,
                #            datetime_col=datetime_col, time_info=time_info,
                #    partition_clause=partition_clause)
                # if dry_run:
                #    print_sql(sql_stmt)
                #    result = None
                # else:
                #    result = self.execute_sql(sql_stmt)
            return result

        result = query_min()
        if result is None:
            result = query_sec()
        if result is None:
            result = query_hour()
        if result is None:
            result = query_day()
        return result

    def human_form_to_machine_form(self, sql_stmt):
        """ apply magic tricks to convert some useful names, e.g. hour, day, ... to the expected numeric value in [ms] - which is the expected input to TimeSeries functions in SQL
        """
        with lock:
            backup_stmt = self._sql_stmt
            self._sql_stmt = sql_stmt
            self.format_()
            sql_stmt = self._sql_stmt
            self._sql_stmt = backup_stmt
        return sql_stmt

    def execute_sql(self, *args, **kwargs):
        sql_stmt = args[0]
        tmp = list(args)
        sql_stmt = self.human_form_to_machine_form(sql_stmt)
        tmp[0] = sql_stmt
        args = tuple(tmp)
        return super().execute_sql(*args, **kwargs)

    def run_sql(self, *args, **kwargs):
        sql_stmt = args[0]
        tmp = list(args)
        sql_stmt = self.human_form_to_machine_form(sql_stmt)
        tmp[0] = sql_stmt
        args = tuple(tmp)
        return super().run_sql(*args, **kwargs)

    def submit_sql(self, *args, **kwargs):
        sql_stmt = args[0]
        tmp = list(args)
        sql_stmt = self.human_form_to_machine_form(sql_stmt)
        tmp[0] = sql_stmt
        args = tuple(tmp)
        return super().submit_sql(*args, **kwargs)


def test_run():
    sqlClient = SQLClient()
    sql_stmt = """
     WITH
        hourly_avg_table as (
            SELECT
                location,
                TS_SEG_AVG(TS_SEGMENT_BY_TIME(pm, 3600000, 3600000)) as hourly_avg_pm_ts,
                TS_SEG_AVG(TS_SEGMENT_BY_TIME(pm, hour , hour)) as hourly_avg_pm_ts_2
                TS_SEG_AVG(TS_SEGMENT_BY_TIME(pm, hour , hour)) as hourly_avg_pm_ts_2
                TS_SEG_AVG(TS_SEGMENT_BY_TIME(pm, hour , 3600000)) as hourly_avg_pm_ts_2
            FROM cos://s3.us-south.cloud-object-storage.appdomain.cloud/tuan-sql-result/jobid=f6cee0f2-5524-43cd-8aee-ddc3c428868f STORED AS PARQUET)
    SELECT
        location,
        TS_FILLNA(hourly_avg_pm_ts, TS_INTERPOLATOR_LINEAR(0.0,1,1)) as hourly_avg_pm_ts
    FROM hourly_avg_table
    INTO cos://us-south/tuan-sql-result STORED AS PARQUET
    """
    sqlClient._sql_stmt = sql_stmt
    sqlClient.run()
