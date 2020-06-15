.. _sql-magic-label:

ibmcloudsql.sql_magic
================================================

:mod:`ibmcloudsql.sql_magic` provides 2 classes

* :py:class:`TimeSeriesTransformInput` class which provides utilities for mapping user-friendly APIs to library-friendly APIs
* :py:class:`TimeSeriesSchema` class which provides hints about the schema of the data to support :meth:`get_ts_datasource`
* :py:class:`SQLMagic` class which provides APIs to help constructing a complete SQL Query without knowing the details about IBM Cloud SQL-specific syntax

TimeSeriesTransformInput
------------------------

A :class:`TimeSeriesTransformInput` class that provides utilities for mapping from user-friendly time-series query into library-friendly time-series query

Example:

.. code-block:: console

    sql_stmt = """
    ts_segment_by_time(ts, week, week)
    """
    sql_stmt = """
    ts_segment_by_time(ts, 604800000, 604800000)
    """

* :meth:`transform_sql`: the decorator that is applied on the :meth:`SQLMagic.print_sql` and :meth:`SQLMagic.format_` methods
* :meth:`ts_segment_by_time`

TimeSeriesSchema
------------------------

* :attr:`unixtime_columns` tells which columns contain time-stamp data and in unix time format

SQLMagic
------------------------

A :class:`SQLMagic` class is also a :class:`TimeSeriesSchema` class

* :meth:`reset_` : to reset the internal storage of SQL statement (use this before constructing a new one)
* :meth:`print_sql`: to print and check the current content of SQL statement

* :meth:`with_` : provide table-name and the SQL query for that table
* :meth:`select_`: provide column names
* :meth:`from_table_`: the table name
* :meth:`from_cos_`: provide COS URL and format of data via `format_type` option
* :meth:`from_view_`: provide SQL statement that return a view
* :meth:`where_`: where condition
* :meth:`order_by_`: list of columns
* :meth:`group_by_`: list of columns
* :meth:`store_at_`: provide COS URL and format of data
* :meth:`partiton_objects_`: provide number of objects
* :meth:`partition_rows_`: provide number of rows per object
* :meth:`format_`: to apply transformation needed to map user-friendly Time-Series Queries into library-friendly Time-Series Queries


