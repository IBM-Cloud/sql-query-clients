.. _sql-magic-label:

ibmcloudsql.sql_magic
================================================

:mod:`ibmcloudsql.sql_magic` provides the following three classes:

* :py:class:`.TimeSeriesTransformInput` class: provides utilities for mapping user-friendly APIs to library-friendly APIs
* :py:class:`.TimeSeriesSchema` class: provides hints about the schema of the data to support :meth:`.get_ts_datasource`
* :py:class:`.SQLMagic` class: provides APIs to help constructing a complete SQL query without knowing the details about syntax specific to IBM Cloud SQL

TimeSeriesTransformInput
------------------------

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

TimeSeriesSchema
------------------------

* :attr:`unixtime_columns`: shows which columns contain time stamp data in Unix time format

SQLMagic
------------------------

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

