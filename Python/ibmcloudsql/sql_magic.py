import sqlparse
from functools import wraps
import re

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
    @classmethod
    def transform_sql(cls, f):
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
        Help to transform from user-friendly query into library-friendly query

        Using either: `per_hour`

        .. code-block:: console
            ts_segment_by_time(ts, per_hour, per_hour)
            ts_segment_by_time(ts, hour, hour)

        or: using  ISO 8601 https://en.wikipedia.org/wiki/ISO_8601#Durations 
            P[n]Y[n]M[n]DT[n]H[n]M[n]S or P[n]W

        Example:

        .. code-block:: python
            ts_segment_by_time(ts, PT1H, PT1H)

        into

        .. code-block:: python
            ts_segment_by_time(ts, 3600000, 3600000)

        as ts_segment_by_time operates at mili-seconds level, hour=60*60*1000 miliseconds
        """
        sql_stmt = re.sub(r'ts_segment_by_time', 'TS_SEGMENT_BY_TIME', sql_stmt, flags=re.IGNORECASE)
        h = re.compile(r'TS_SEGMENT_BY_TIME[\s]?\(([a-zA-Z0-9]+)[\s]?,[\s]?(?P<window>[a-zA-Z][a-zA-Z_0-9]+)[\s]?,[\s]?(?P<step>[a-zA-Z][a-zA-Z_0-9]+)', re.MULTILINE)
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
                start_end[i] = result.span(i)
            sql_stmt = sql_stmt[:start_end[2][0]] + str(num[2]) + sql_stmt[start_end[2][1]:start_end[3][0]] + \
                str(num[3]) +  sql_stmt[start_end[3][1]:]
            result = h.search(sql_stmt)
        return sql_stmt

class TimeSeriesSchema():
    def __init__(self):
        # the list of column in unix-tme format
        """9999999999999 (13 digits) means Sat Nov 20 2286 17:46:39 UTC
        999999999999 (12 digits) means Sun Sep 09 2001 01:46:39 UTC
        99999999999 (11 digits) means Sat Mar 03 1973 09:46:39 UTC
        100000000000000 (15 digits) means Wed Nov 16 5138 09:46:40
        https://stackoverflow.com/questions/23929145/how-to-test-if-a-given-time-stamp-is-in-seconds-or-milliseconds
        """
        self._unixtime_columns = []


class SQLMagic(TimeSeriesSchema):

    def __init__(self):
        super().__init__()
        # contain the sql string that we can evoke using run() or submit()
        self._sql_stmt = ""
        self._has_stored_location = False
        self._has_with_clause = False
        self._has_select_clause = False
        self.supported_format_types = ["PARQUET", "CVS", "JSON"]

    @TimeSeriesTransformInput.transform_sql
    def print_sql(self):
        print_sql(self._sql_stmt)

    def reset_(self):
        self._sql_stmt = ""
        self._has_stored_location = False
        self._has_with_clause = False
        self._has_select_clause = False

    def with_(self, table_name, sql_stmt):
        if "WITH" not in self._sql_stmt:
            self._sql_stmt = self._sql_stmt + " WITH " + table_name + " AS (" + sql_stmt  + "\n) "
            self._has_with_clause = True
        else:
            self._sql_stmt = self._sql_stmt + ", " + table_name + " AS (" + sql_stmt  + "\n) "
        return self

    def select_(self,  columns):
        """
        Parameters:
        ---------------
        columns: str
            a string representing a comma-separated list of columns
        """
        assert(self._has_select_clause is False)
        self._sql_stmt = self._sql_stmt + "SELECT " + columns
        self._has_select_clause = True
        return self

    def from_table_(self, table):
        self._sql_stmt = self._sql_stmt + " FROM " + table
        return self

    def from_cos_(self, cos_url, format_type="parquet"):
        self._sql_stmt = self._sql_stmt + " FROM " + cos_url + " STORED AS" + format_type
        return self

    def from_view_(self, sql_stmt):
        self._sql_stmt = self._sql_stmt + " FROM  ( \n" + sql_stmt + " \n) "
        return self

    def where_(self, condition):
        if "WHERE" not in self._sql_stmt:
            self._sql_stmt = self._sql_stmt + " WHERE " + condition
        else:
            self._sql_stmt = self._sql_stmt + ", " + condition
        return self

    def order_by_(self, columns):
        """
        Parameters
        ---------------
        condition: str
            a string representing a comma-separated list of columns
        """
        self._sql_stmt = self._sql_stmt + "ORDER BY " + columns
        return self

    def group_by_(self, columns):
        if "GROUP BY" not in self._sql_stmt:
            self._sql_stmt = self._sql_stmt + " GROUP BY " + columns
        else:
            self._sql_stmt = self._sql_stmt + ", " + columns
        return self

    def store_at_(self, cos_url, format_type=""):
        if self._has_stored_location is False:
            self._sql_stmt = self._sql_stmt + " INTO " + cos_url
            self._has_stored_location = True
        else:
            assert(0)
        if len(format_type) > 0 and format_type.upper() in self.supported_format_types:
            self._sql_stmt = self._sql_stmt + " STORED AS " + format_type.upper()
        return self

    # def store_as_(self, format_type="parquet"):
    #     if "INTO " not in self._sql_stmt:
    #         self._sql_stmt = self._sql_stmt + " INTO {cos_out} STORED AS " + format_type.upper()
    #     else:
    #         self._sql_stmt = self._sql_stmt + " STORED AS " + format_type.upper()
    #     return self

    def partition_objects_(self, num_objects):
        if "PARTITION" not in self._sql_stmt:
            self._sql_stmt = self._sql_stmt + " PARTITIONED INTO " + str(num_objects) + " OBJECTS"
        else:
            assert(0)
        return self

    def partition_rows_(self, num_rows):
        if "PARTITION" not in self._sql_stmt:
            self._sql_stmt = self._sql_stmt + " PARTITIONED INTO " + str(num_rows) + " ROWS"
        else:
            assert(0)
        return self

    @TimeSeriesTransformInput.transform_sql
    def format_(self):
        """Perform string replacement needed so that the final result is a SQL statement that is accepted by Spark SQL
        """
        return self

def test_chain_function():
    targeturl = "cos://test/url"
    ts_source_location="cos://s3.us-south.cloud-object-storage.appdomain.cloud/sql-query-cos-access-ts/jobid=eba380ac-1dda-4255-ab6a-9d72be3db9f7"
    sqlClient = SQLMagic()
    sqlClient.reset_()
    sqlClient.with_("container_ts_table", """
        SELECT
            container_id,
            ts
        FROM {cos_in} STORED AS PARQUET
        USING TIME_SERIES_FORMAT(key="container_id", timetick="time_stamp", value="request_latency"
        ) in ts   -- NOTE: 'USING' is applied for data source [and there is no need for GROUP BY clause]""".format(cos_in=ts_source_location) )\
            .with_("diff_avg_latency_per_interval", """
        select
            container_id,
            ts_diff(ts_seg_avg(ts_segment_by_time(ts, 60 * 15 * 1000, 60 * 15 * 1000))) as ts
        from container_ts_table""") \
            .with_("diff_latency_flattened", """
        select
            container_id,
            ts_explode(ts) as (tt, diff_latency)
        from diff_avg_latency_per_interval""") \
            .with_("avg_diff_latency_per_id", """
        select
            container_id,
            ts_avg(ts) as avg_diff_latency
        from diff_avg_latency_per_interval""") \
            .with_("joined", """
        select
            diff_latency_flattened.container_id,
            tt,
            diff_latency,
            avg_diff_latency
        from diff_latency_flattened, avg_diff_latency_per_id
        where diff_latency_flattened.container_id=avg_diff_latency_per_id.container_id""") \
            .select_("""
    container_id,
    tt,
    diff_latency""") \
            .from_table_("joined") \
            .where_("abs(diff_latency) < avg_diff_latency * 2.0") \
            .store_at_("""{cos_out}""".format(cos_out=targeturl), format_type="parquet") \
            .partition_objects_(20)
    sqlClient.print_sql()

def test_01(sql_stmt):
    #result = re.search(r'TS_SEGMENT_BY_TIME[\s]?\(([a-zA-Z0-9]+)[\s]?,[\s]?(?P<window>[0-9]+)[\s]?,[\s]?(?P<step>[0-9]+)', sql_stmt)
    h = re.compile(r'TS_SEGMENT_BY_TIME[\s]?\(([a-zA-Z0-9]+)[\s]?,[\s]?(?P<window>[0-9]+)[\s]?,[\s]?(?P<step>[0-9]+)')
    result = h.search(sql_stmt)
    # h.sub()
    print(result.group())
    print(result.group(1), result.group(2), result.group(3))
    print(result.groupdict())
    loc = result.span(0)[1]
    pre = sql_stmt[:loc + 1]
    post = sql_stmt[loc + 1:]
    print(pre)

def test_02(sql_stmt):
    h = re.compile(r'TS_SEGMENT_BY_TIME[\s]?\(([a-zA-Z0-9]+)[\s]?,[\s]?(?P<window>[a-zA-Z_0-9]+)[\s]?,[\s]?(?P<step>[a-zA-Z_0-9]+)', re.MULTILINE)
    result = h.search(sql_stmt)
    print(result.groups())
    print("===")
    # results = h.findall(sql_stmt)
    results = h.finditer(sql_stmt)
    # h.sub()
    for result in results:
        print(result.group(2), result.group(3))
        print(result.span(2), result.span(3))
        for i in [2, 3]:
            if not result.group(i).isdigit():
                if result.strip() == "hour":
                    num = 60
                num = num * 60 * 1000
                #print(result.group(i))
                sql_stmt = sql_
                pass
        # print(result.group())
        # print(result.group(1), result.group(2), result.group(3))
        # print(result.groupdict())

def test_03(sql_stmt):
    h = re.compile(r'TS_SEGMENT_BY_TIME[\s]?\(([a-zA-Z0-9]+)[\s]?,[\s]?(?P<window>[a-zA-Z][a-zA-Z_0-9]+)[\s]?,[\s]?(?P<step>[a-zA-Z][a-zA-Z_0-9]+)', flags = re.MULTILINE | re.IGNORECASE)
    result = h.search(sql_stmt)
    print(result.groups())
    print("===")
    # results = h.findall(sql_stmt)
    result = h.search(sql_stmt)
    # h.sub()
    while result:
        start_end = {}
        print(result.group(2), result.group(3))
        print(result.span(2), result.span(3))
        num = {}
        for i in [2, 3]:
            if not result.group(i).isdigit():
                if result.group(i).strip() == "hour":
                    num[i] = 60
                num[i] = num[i] * 60 * 1000
                #print(result.group(i))
                #sql_stmt = sql_stmt
                pass
            start_end[i] = result.span(i)
        print(num)
        sql_stmt = sql_stmt[:start_end[2][0]] + str(num[2]) + sql_stmt[start_end[2][1]:start_end[3][0]] + \
            str(num[3]) +  sql_stmt[start_end[3][1]:]
        print(sql_stmt)
        result = h.search(sql_stmt)

def test_04(sql_stmt):
    sql = SQLMagic()
    sql._sql_stmt = sql_stmt
    sql.format_()
    print(sql._sql_stmt)


if __name__ == "__main__":
    # test_chain_function()
    import re
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
    print(sql_stmt)
    #   test_01(sql_stmt)
    #   test_02(sql_stmt)
    # test_03(sql_stmt)
    test_04(sql_stmt)
    sql_stmt = """
    WITH container_ts_table AS
  (SELECT field_name,
          ts
   FROM cos://s3.us-south.cloud-object-storage.appdomain.cloud/sql-query-cos-access-ts/jobid=53dfb2c3-ac3a-44af-a55d-d1a366a0883f STORED AS PARQUET USING TIME_SERIES_FORMAT(KEY="field_name", timetick="time_stamp", value="observation") IN ts)
SELECT field_name AS storage_account_id,
       ts_explode(ts_seg_avg(ts_segment_by_time(ts, week, hour))) AS (tt,
                                                                      value)
FROM container_ts_table INTO cos://us-south/sql-query-cos-access-ts STORED AS PARQUET
    """
    test_04(sql_stmt)
    sql_stmt = """
    WITH container_ts_table AS
  (SELECT field_name,
          ts
   FROM cos://s3.us-south.cloud-object-storage.appdomain.cloud/sql-query-cos-access-ts/jobid=53dfb2c3-ac3a-44af-a55d-d1a366a0883f STORED AS PARQUET USING TIME_SERIES_FORMAT(KEY="field_name", timetick="time_stamp", value="observation") IN ts)
SELECT field_name AS storage_account_id,
       ts_explode(ts_seg_avg(ts_segment_by_time(ts, P1W, PT1H))) AS (tt,
                                                                      value)
FROM container_ts_table INTO cos://us-south/sql-query-cos-access-ts STORED AS PARQUET
    """
    test_04(sql_stmt)