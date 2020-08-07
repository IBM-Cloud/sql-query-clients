.. _sql-magic-label:

SQLMagic Class
================================================

:mod:`ibmcloudsql.sql_magic` provides the following three classes:

* :py:class:`.TimeSeriesTransformInput` class: provides utilities for mapping user-friendly APIs to library-friendly APIs
* :py:class:`.TimeSeriesSchema` class: provides hints about the schema of the data to support :meth:`.get_ts_datasource`
* :py:class:`.SQLMagic` class: provides APIs to help constructing a complete SQL query without knowing the details about syntax specific to IBM Cloud SQL

Time series transform input
---------------------------

A :class:`.TimeSeriesTransformInput` class: provides utilities for mapping from user-friendly time series query into library-friendly time series query

Example:

.. code-block:: console

    sql_stmt = """
    ts_segment_by_time(ts, week, week)
    """
    sql_stmt = """
    ts_segment_by_time(ts, 604800000, 604800000)
    """

* :meth:`.transform_sql`: the decorator that is applied on the :meth:`.SQLMagic.print_sql` and :meth:`.SQLMagic.format_` methods
* :meth:`.ts_segment_by_time`

Time series schema
------------------------

* :attr:`unixtime_columns`: shows which columns contain time stamp data in Unix time format

Time series schema SQL Magic
-----------------------------

A :class:`.SQLMagic` class is also a :class:`.TimeSeriesSchema` class.

* :meth:`.reset_`: resets the internal storage of an SQL statement (use this before constructing a new one)
* :meth:`.print_sql`: prints and checks the current content of an SQL statement
* :meth:`.get_sql`: returns the string representation of the SQL statement 

* :meth:`.with_`: provides table name and the SQL query for that table
* :meth:`.select_`: provides column names
* :meth:`.from_table_`: the table name
* :meth:`.from_cos_`: provides COS URL and format of data via `format_type` option
* :meth:`.from_view_`: provides SQL statement that returns a view
* :meth:`.where_`: where condition
* :meth:`.order_by_`: lists columns
* :meth:`.group_by_`: lists columns
* :meth:`.store_at_`: provides COS URL and format of data
* :meth:`.partition_objects_`: provides number of objects
* :meth:`.partition_rows_`: provides number of rows per object
* :meth:`.partition_by_`: provides the string of tuple of column names for HIVE catalog partitioning 
* :meth:`.format_`: applies transformation needed to map user-friendly time series queries into library-friendly time series queries
* :meth:`.join_cos_`: JOIN statement using COS URL
* :meth:`.join_table_`: JOIN statement using table name

Example: we can generate the SQL string using SQLMagic APIs

.. code-block:: python
    :linenos:

    sqlmagic = ibmcloudsql.SQLMagic()
    (sqlClient
     .with_("humidity_location_table",
              (sqlmagic.select_("location")
                       .from_view_("select count(*) as count, location from dht where humidity > 70.0 group by location")
                       .where_("count > 1000 and count < 2000")
              ).reset_()
           )
     .with_("pm_location_table",
              (sqlmagic.select_("location")
                       .from_view_("select count(*) as count, location from sds group by location")
                       .where_("count > 1000 and count < 2000")
              ).reset_()
           )
     .select_("humidity_location_table.location")
     .from_table_("humidity_location_table")
     .join_table_("pm_location_table", type="inner", condition="humidity_location_table.location=pm_location_table.location")
     .store_at_(targeturl)
     )
    result = sqlClient.run()

This is the typically way to generate the SQL similar to the one above

..  code-block:: python
    :linenos:

    stmt = """
        WITH
            humidity_location_table AS (
            -- 1. Select locations from DHT where humidity is >70% and the length is data is between 1000 and 2000
                SELECT location from (
                    SELECT
                        COUNT(*) AS count,
                        location
                    FROM DHT
                    WHERE humidity > 70.0
                    GROUP BY location
                )
                WHERE count > 1000 AND count < 2000
            ),
            pm_location_table AS (
            -- 2. Select locations from PM where length is data is between 1000 and 2000
               SELECT location from (
                SELECT
                  COUNT(*) AS count,
                  location
                FROM SDS
                GROUP BY location
              )
              WHERE count > 1000 AND count < 2000
            )
            -- 3. Select those locations that are present in both PM and DHT tables
            SELECT
                humidity_location_table.location
            FROM humidity_location_table
            INNER JOIN pm_location_table
            ON humidity_location_table.location=pm_location_table.location
            INTO {}
    """.format(targeturl)
    result = sqlClient.execute_sql(stmt)

