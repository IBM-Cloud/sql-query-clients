# flake8: noqa W503
import re
from datetime import datetime

import pytest
import responses
from ibmcloudsql.sql_magic import SQLBuilder


@pytest.fixture
def sql_stmt():
    _sql_stmt = """
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
    # print(_sql_stmt)
    return _sql_stmt


@pytest.fixture
def sql_magic():
    return SQLBuilder()


def test_chain_function(sql_magic):
    targeturl = "cos://test/url"
    ts_source_location = "cos://s3.us-south.cloud-object-storage.appdomain.cloud/sql-query-cos-access-ts/jobid=eba380ac-1dda-4255-ab6a-9d72be3db9f7"
    sql_magic.reset_()
    sql_magic.with_(
        "container_ts_table",
        """
        SELECT
            container_id,
            ts
        FROM {cos_in} STORED AS PARQUET
        USING TIME_SERIES_FORMAT(key="container_id", timetick="time_stamp", value="request_latency"
        ) in ts   -- NOTE: 'USING' is applied for data source [and there is no need for GROUP BY clause]""".format(
            cos_in=ts_source_location
        ),
    ).with_(
        "diff_avg_latency_per_interval",
        """
        select
            container_id,
            ts_diff(ts_seg_avg(ts_segment_by_time(ts, 60 * 15 * 1000, 60 * 15 * 1000))) as ts
        from container_ts_table""",
    ).with_(
        "diff_latency_flattened",
        """
        select
            container_id,
            ts_explode(ts) as (tt, diff_latency)
        from diff_avg_latency_per_interval""",
    ).with_(
        "avg_diff_latency_per_id",
        """
        select
            container_id,
            ts_avg(ts) as avg_diff_latency
        from diff_avg_latency_per_interval""",
    ).with_(
        "joined",
        """
        select
            diff_latency_flattened.container_id,
            tt,
            diff_latency,
            avg_diff_latency
        from diff_latency_flattened, avg_diff_latency_per_id
        where diff_latency_flattened.container_id=avg_diff_latency_per_id.container_id""",
    ).select_(
        """
    container_id,
    tt,
    diff_latency"""
    ).from_table_(
        "joined"
    ).where_(
        "abs(diff_latency) < avg_diff_latency * 2.0"
    ).store_at_(
        """{cos_out}""".format(cos_out=targeturl), format_type="parquet"
    ).partition_objects_(
        20
    )
    # sql_magic.print_sql()
    print(sql_magic._sql_stmt)
    assert (
        sql_magic._sql_stmt
        == """ WITH container_ts_table AS (
        SELECT
            container_id,
            ts
        FROM cos://s3.us-south.cloud-object-storage.appdomain.cloud/sql-query-cos-access-ts/jobid=eba380ac-1dda-4255-ab6a-9d72be3db9f7 STORED AS PARQUET
        USING TIME_SERIES_FORMAT(key="container_id", timetick="time_stamp", value="request_latency"
        ) in ts   -- NOTE: 'USING' is applied for data source [and there is no need for GROUP BY clause]
) , diff_avg_latency_per_interval AS (
        select
            container_id,
            ts_diff(ts_seg_avg(ts_segment_by_time(ts, 60 * 15 * 1000, 60 * 15 * 1000))) as ts
        from container_ts_table
) , diff_latency_flattened AS (
        select
            container_id,
            ts_explode(ts) as (tt, diff_latency)
        from diff_avg_latency_per_interval
) , avg_diff_latency_per_id AS (
        select
            container_id,
            ts_avg(ts) as avg_diff_latency
        from diff_avg_latency_per_interval
) , joined AS (
        select
            diff_latency_flattened.container_id,
            tt,
            diff_latency,
            avg_diff_latency
        from diff_latency_flattened, avg_diff_latency_per_id
        where diff_latency_flattened.container_id=avg_diff_latency_per_id.container_id
) SELECT
    container_id,
    tt,
    diff_latency FROM joined WHERE abs(diff_latency) < avg_diff_latency * 2.0 INTO cos://test/url STORED AS PARQUET PARTITIONED INTO 20 OBJECTS"""
    )


def test_format_(sql_magic):
    sql_stmt = """
     WITH
        hourly_avg_table as (
            SELECT
                location,
                TS_SEG_AVG(TS_SEGMENT_BY_TIME(pm, 3600000, 3600000)) as hourly_avg_pm_ts,
                TS_SEG_AVG(TS_SEGMENT_BY_TIME(pm, hour , hour)) as hourly_avg_pm_ts_2,
                TS_SEG_AVG(TS_SEGMENT_BY_TIME(pm, 20000, hour)) as hourly_avg_pm_ts_3,
                TS_SEG_AVG(TS_SEGMENT_BY_TIME(pm, hour , 3600000)) as hourly_avg_pm_ts_4
            FROM cos://s3.us-south.cloud-object-storage.appdomain.cloud/sql-result/jobid=g6cee0f2-5524-43cd-8aee-ddc3c428868f STORED AS PARQUET)
    SELECT
        location,
        TS_FILLNA(hourly_avg_pm_ts, TS_INTERPOLATOR_LINEAR(0.0,1,1)) as hourly_avg_pm_ts
    FROM hourly_avg_table
    INTO cos://us-south/tuan-sql-result STORED AS PARQUET
    """
    sql_magic._sql_stmt = sql_stmt
    sql_magic.format_()
    print("=====")
    print(sql_magic._sql_stmt)
    print("=====")
    assert (
        sql_magic._sql_stmt
        == """
     WITH
        hourly_avg_table as (
            SELECT
                location,
                TS_SEG_AVG(TS_SEGMENT_BY_TIME(pm, 3600000, 3600000)) as hourly_avg_pm_ts,
                TS_SEG_AVG(TS_SEGMENT_BY_TIME(pm, 3600000 , 3600000)) as hourly_avg_pm_ts_2,
                TS_SEG_AVG(TS_SEGMENT_BY_TIME(pm, 20000, 3600000)) as hourly_avg_pm_ts_3,
                TS_SEG_AVG(TS_SEGMENT_BY_TIME(pm, 3600000 , 3600000)) as hourly_avg_pm_ts_4
            FROM cos://s3.us-south.cloud-object-storage.appdomain.cloud/sql-result/jobid=g6cee0f2-5524-43cd-8aee-ddc3c428868f STORED AS PARQUET)
    SELECT
        location,
        TS_FILLNA(hourly_avg_pm_ts, TS_INTERPOLATOR_LINEAR(0.0,1,1)) as hourly_avg_pm_ts
    FROM hourly_avg_table
    INTO cos://us-south/tuan-sql-result STORED AS PARQUET
    """
    )
    sql_stmt = """
    WITH container_ts_table AS
    (SELECT field_name,
          ts
    FROM cos://s3.us-south.cloud-object-storage.appdomain.cloud/cos-access-ts/jobid=33dfb2c3-ac3a-44af-a55d-d1a366a0883f STORED AS PARQUET USING TIME_SERIES_FORMAT(KEY="field_name", timetick="time_stamp", value="observation") IN ts)
    SELECT field_name AS storage_account_id,
       ts_explode(ts_seg_avg(ts_segment_by_time(ts, week, week))) AS (tt,
                                                                      value)
    FROM container_ts_table INTO cos://us-south/sql-query-cos-access-ts STORED AS PARQUET
    """
    sql_magic._sql_stmt = sql_stmt
    sql_magic.format_()
    print(sql_magic._sql_stmt)
    assert (
        sql_magic._sql_stmt
        == """
    WITH container_ts_table AS
    (SELECT field_name,
          ts
    FROM cos://s3.us-south.cloud-object-storage.appdomain.cloud/cos-access-ts/jobid=33dfb2c3-ac3a-44af-a55d-d1a366a0883f STORED AS PARQUET USING TIME_SERIES_FORMAT(KEY="field_name", timetick="time_stamp", value="observation") IN ts)
    SELECT field_name AS storage_account_id,
       ts_explode(ts_seg_avg(TS_SEGMENT_BY_TIME(ts, 604800000, 604800000))) AS (tt,
                                                                      value)
    FROM container_ts_table INTO cos://us-south/sql-query-cos-access-ts STORED AS PARQUET
    """
    )
