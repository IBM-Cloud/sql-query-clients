"""Catalog Table."""
import logging
import time

from deprecated import deprecated

logger = logging.getLogger(__name__)
try:
    from cos import ParsedUrl
    from exceptions import (
        SqlQueryDropTableException,
        SqlQueryFailException,
        SqlQueryCreateTableException,
        InternalErrorException,
    )
except ImportError:
    from .cos import ParsedUrl
    from .exceptions import (
        SqlQueryDropTableException,
        SqlQueryFailException,
        SqlQueryCreateTableException,
        InternalErrorException,
    )


class HiveMetastore:
    """This class supports the handling HIVE catalog table."""

    def __init__(self, target_url):
        """Create an instance of the class.

        Parameters
        ----------
        target_url: str
          The COS URL that is used to store temporary data for any Data Engine queries.
        """
        self.current_table_name = None
        # keep tracks of what tables are availables
        self.partitioned_tables = set()
        self.regular_tables = set()
        self.sql_stmt_show_template = """
        SHOW TABLES {like}
        INTO {cos_out} STORED AS CSV
        """
        # The default URL where data should be queried
        self.cos_in_url_partitioned = "cos://us-geo/sql/customers_partitioned.csv"
        self.cos_in_url = "cos://us-geo/sql/customers.csv"

        self.sql_stmt_create_template = """
        CREATE TABLE {table_name}
        USING {format_type}
        LOCATION {cos_in}
        """
        self._target_url = target_url
        self.supported_format_types = ["PARQUET", "CSV", "JSON"]

    def _is_valid_target_url(self, target_url=None):
        """Raise ValueError if the required COS URL is invalid."""
        if target_url is None:
            target_url = self._target_url
        if target_url is None or not ParsedUrl().is_valid_cos_url(target_url):
            msg = "Need to define target COS URL"
            if target_url is not None:
                msg = "Not a valid COS URL: {}".format(target_url)
            raise ValueError(msg)
        return True

    def configure(self, target_url):
        """Update the configuration."""
        self._is_valid_target_url(target_url)
        self._target_url = target_url

    @property
    def target_url(self):
        """Return the target COS URL."""
        return self._target_url

    @target_url.setter
    def target_url(self, target_url):
        self._is_valid_target_url(target_url)
        self._target_url = target_url

    # Extended functionality
    def show_tables(self, target_cos_url=None, pattern=None):
        """List the available Hive Metastore.

        Parameters
        ------------
        target_cos_url: string, optional
            The COR URL where the information about the tables are stored
        pattern: str, optional
            If provided, this should be a pattern being used in name matching,
            e.g. '*cus*', which finds all tables with the name has 'cus'

        Returns
        --------
        DataFrame or None
            return `None` if there is an error.

        Raises
        -------
        SqlQueryFailException
        ValueError

        """
        if target_cos_url is None:
            cos_out = self.target_url
        else:
            cos_out = target_cos_url
            self._is_valid_target_url(cos_out)
        sql_stmt_show = self.sql_stmt_show_template.format(
            like="LIKE '{}'".format(pattern) if pattern else "", cos_out=cos_out
        )
        df = None
        try:
            df, job_id = self.execute_sql(sql_stmt_show, get_result=True)
        except (SqlQueryFailException, KeyError) as e:
            logger.info("Fail at SHOW TABLE")
            raise e
        return df

    def drop_all_tables(self):
        """Delete all created tables in the project.

        Returns
        -------
        bool
            True [if success]
        """
        df = self.show_tables()
        if df is not None and not df.empty:
            for (_, table_name) in df["tableName"].iteritems():
                self.drop_table(table_name)
                try:
                    self.partitioned_tables.remove(table_name)
                    self.regular_tables.remove(table_name)
                except KeyError:
                    pass
            self.partitioned_tables = set()
            self.regular_tables = set()
        return True

    def drop_tables(self, table_names):
        """Drop a list of tables.

        Parameters
        ----------
            table_names: list
                A list of tables
        """
        for x in table_names:
            self.drop_table(x)

    def drop_table(self, table_name=None):
        """Drop a given table.

        Parameters
        ----------
        table_name: str, optional
            The name of the table
            If skipped, the being tracked catalog-table is used

        Returns
        -------
        str:
            a job status

        Raises
        -------
        SqlQueryDropTableException
            when it cannot remove the given table name
        ValueError
        """
        if table_name is None and self.current_table_name is None:
            msg = "please provide table_name"
            raise ValueError(msg)
        if table_name is None:
            table_name = self.current_table_name
            self.current_table_name = None
        sql_stmt_drop = """
        DROP TABLE {table_name}""".format(
            table_name=table_name
        )
        try:
            _, job_id = self.execute_sql(sql_stmt_drop)
            logger.debug(
                "Job_id ({stmt}): {job_id}".format(stmt=sql_stmt_drop, job_id=job_id)
            )
            job_status = self.wait_for_job(job_id)
            if job_status != "completed":
                raise SqlQueryDropTableException(
                    "table name {} removed failed".format(table_name)
                )
            self.partitioned_tables.remove(table_name)
            self.regular_tables.remove(table_name)
        except SqlQueryFailException:
            msg = "Wrong table name"
            logger.warning(msg)
        except KeyError:
            pass
        return "completed"

    def create_table(
        self,
        table_name,
        cos_url=None,
        format_type="CSV",
        force_recreate=False,
        blocking=True,
        schema=None,
    ):
        """Create a table for data on COS.

        Parameters
        ----------
        table_name: str
            The name of the table

        cos_url : str, optional
            The COS URL from which the table should reference to
            If not provided, it uses the internal `self.cos_in_url`
        format_type: string, optional
            The type of the data above that you want to reference (default: CSV)

        force_recreate: bool, optional
            (True) force to recreate an existing table
        blocking: bool, optional
            (True) wait until it returns the resut
        schema: None or string
            If None, then automatic schema detection is used. Otherwise, pass in the comma-separated
            string in the form "(columnName type, columnName type)"

        Returns
        -------
            none if job "failed"
            otherwise returns

        Raises
        -------
        ValueError:
            when the argument is invalid for `cos_url` (invalid format or there is no such location),
            format_type (invalid value)


        SqlQueryDropTableException
            when it cannot remove the given table name
        SqlQueryCreateTableException
            when it cannot create the given table name

        """
        self._is_valid_target_url(cos_url)

        def _create_table_async(
            table_name,
            cos_url=None,
            format_type="CSV",
            force_recreate=False,
            schema=None,
        ):
            """
            Create a table asynchronously. This is the async version of :meth:`.create_table`.

              Parameters
              ----------
              table_name: str
                  The name of the table

              cos_url : str, optional
                  The COS URL from which the table should reference to
                  If not provided, it uses the internal `self.cos_in_url`

              force_recreate: bool, optional
                  (True) force to recreate an existing table

              Returns
              ------
                  job_id [if the table is being created]
                  None   [if the table already created]
            """
            self.current_table_name = table_name

            if cos_url is None:
                cos_url = self.cos_in_url

            # from IPython.display import display
            df = self.show_tables()
            try:
                found = df[df["tableName"].str.contains(table_name.strip().lower())]
            except Exception:
                # not found
                found = []

            # if logger.getEffectiveLevel() == logging.DEBUG:
            #     display(df)
            if len(found) > 0 and force_recreate:
                self.drop_table(table_name)
            self.regular_tables.add(table_name)
            if len(found) == 0 or force_recreate:
                if schema is None:
                    sql_stmt_create = self.sql_stmt_create_template.format(
                        table_name=table_name, cos_in=cos_url, format_type=format_type
                    )
                else:
                    # choose scheme -> need to tell "PARTITIONED BY"
                    schema = self._format_schema(schema)
                    sql_stmt_create = """
                    CREATE TABLE {table_name} {schema}
                    USING {format_type}
                    LOCATION {cos_in}
                    """.format(
                        table_name=table_name,
                        cos_in=cos_url,
                        format_type=format_type,
                        schema=schema,
                    )

                logger.debug(sql_stmt_create)
                job_id = self.submit_sql(sql_stmt_create)
                return job_id
            return None

        job_id = _create_table_async(
            table_name,
            cos_url,
            format_type=format_type,
            force_recreate=force_recreate,
            schema=schema,
        )
        if job_id is not None and blocking is True:
            job_status = self.wait_for_job(job_id)
            if job_status == "completed":
                return self.get_result(job_id)
            else:
                return None
        return None

    def _format_schema(self, schema):
        """Format the schema string to ensure it is enclosed by ( and )."""
        schema = schema.strip()
        if schema[0] == "(" or schema[-1] == ")":
            if schema[0] != "(" or schema[-1] != ")":
                print("schema wrong format, should be: (name type, name type)")
                assert 0
        else:
            schema = "(" + schema + ")"
        return schema

    def table_exists(self, table_name):
        """check if a catalog table exists"""
        df = self.show_tables()
        try:
            found = df[df["tableName"].str.contains(table_name)][
                "tableName"
            ].tolist()  # noqa
            if table_name not in found:
                found = []
        except Exception:
            # not found
            found = []
        if len(found) == 0:
            return False
        else:
            return True

    def create_partitioned_table(
        self,
        table_name,
        cos_url=None,
        format_type="CSV",
        schema=None,
        partition_list=None,
    ):
        """Create a partitioned table for data on COS.

        Note
        -----------
        The data needs to be organized in the form that
        match HIVE metastore criteria, e.g.

        .. code-block:: console

            <COS-URL>/field_1=value1_1/field_2=value_2_1/object_file
            <COS-URL>/field_1=value1_2/field_2=value_2_1/object_file

        NOTE: Each time the data is updated, we need to call
        :meth:`.recover_table_partitions`
        on the created partitioned table.

        Parameters
        --------------
        table_name: str
            the name of the table to be created

        cos_url : str, optional
            The COS URL from which the table should reference to
            If not provided, it uses the internal `self.cos_in_url`

        format_type: string, optional
            The type of the data above (default: CSV)

        schema: None or string
            If None, then automatic schema detection is used. Otherwise,
            pass in the comma-separated
            string in the form "(columnName type, columnName type)"

        partition_list: comma-separated string | list
            the list of columns to be part of the partitioning. NOTE: the order
            matters.


        Returns
        ----------
        None

        Raises
        -------
        ValueError:
            when the argument is invalid for `cos_url`
            (invalid format or there is no such location),
            format_type (invalid value)


        SqlQueryFailException:
            when it cannot remove the given table name


        """
        self.current_table_name = table_name

        if cos_url is None:
            cos_url = self.cos_in_url_partitioned
        else:
            self._is_valid_target_url(cos_url)

        if schema is not None:
            if partition_list is None:
                raise ValueError("Please provide `partition_list`")

        if schema is None:
            # auto-detection of scheme
            self.sql_stmt_create_partitioned_template = """
            CREATE TABLE {table_name}
            USING {format_type}
            LOCATION {cos_in}
            """
            sql_stmt_create_partitioned = self.sql_stmt_create_partitioned_template.format(  # noqa
                table_name=table_name, cos_in=cos_url, format_type=format_type,  # noqa
            )
        else:
            if isinstance(partition_list, list):
                tmp = ", ".join(partition_list)
                partition_list = tmp
            # explit selection of scheme -> need to tell "PARTITIONED BY"
            schema = self._format_schema(schema)
            sql_stmt_create_partitioned = """
            CREATE TABLE {table_name} {schema}
            USING {format_type}
            PARTITIONED BY ({partition_list})
            LOCATION {cos_in}
            """.format(
                table_name=table_name,
                cos_in=cos_url,
                format_type=format_type,
                schema=schema,
                partition_list=partition_list,
            )
        logger.debug(sql_stmt_create_partitioned)
        try:
            self.run_sql(sql_stmt_create_partitioned)
        except SqlQueryTableExistException as e:
            msg = "The table already exist. Please either delete with `.drop_table` or update the partition with `.recover_table_partitions`"
            raise SqlQueryCreateTableException(msg, e)
        except InternalErrorException as e:
            msg = str(e)
            no_schema_error_msg = "Unable to infer schema"
            if no_schema_error_msg in msg:
                msg = (
                    "Can't infer schema (explicit schema is needed)"
                    " or the COS URL is wrong. Please check"
                )
                raise SqlQueryCreateTableException(msg)
            else:
                raise e

        time.sleep(2)
        self.recover_table_partitions(table_name)

    def add_partition(self, table_name, col_key_value_pairs, cos_url=None):
        """Add a partition to the table."""
        self.current_table_name = table_name

        if cos_url is None:
            sql_stmt = """ALTER TABLE {table_name} ADD PARTITION ({col_key_value_pairs})
            """.format(
                table_name=table_name, col_key_value_pairs=col_key_value_pairs
            )
        else:
            self._is_valid_target_url(cos_url)
            sql_stmt = """ALTER TABLE {table_name} ADD PARTITION ({col_key_value_pairs}) LOCATION {cos_in}
            """.format(
                table_name=table_name, col_key_value_pairs=col_key_value_pairs, cos_in=cos_url
            )
        self.run_sql(sql_stmt)

    def recover_table_partitions(self, table_name):
        """Update a partitioned table. This step is required after creating a new partitioned table.

        Note
        ------
          You should use this once at the start (at the first time you define
          the table) to save some work but later on, I would recommend using
          :meth:`.add_partition`

        Parameters
        ----------
            table_name: str
                The partitioned table name
        """
        self.current_table_name = table_name

        sql_stmt = """ALTER TABLE {table_name} RECOVER PARTITIONS
        """.format(
            table_name=table_name
        )
        self.run_sql(sql_stmt)

    def get_schema_table(self, table_name):
        """Return the schema of table.

        Parameters
        ----------
        table_name: str
            Name of the HIVE catalog table

        Returns
        ------
        DataFrame or None [if failed - table not found]
            3 columns: col_name (object), data_type (object), comment (float64)

        """
        return self._describe_table(table_name)

    @deprecated(
        version="1.0",
        reason="Please use get_schema_table [in par with :meth:`.get_schema` from COS URL]",  # noqa
    )
    def describe_table(self, table_name):
        """Return the schema of a table."""
        return self._describe_table(table_name)

    def _describe_table(self, table_name):
        self._is_valid_target_url()

        sql_stmt = """
        DESCRIBE TABLE {table_name} INTO {cos_out} STORED AS CSV""".format(
            table_name=table_name, cos_out=self.target_url
        )
        try:
            return self.run_sql(sql_stmt)
        except Exception:
            return None

    def create_metaindex(self, table_name):
        """Create a metaindex for a given table."""
        sql_stmt = """CREATE METAINDEX {}""".format(table_name)
        try:
            return self.run_sql(sql_stmt)
        except Exception:
            return None

    def get_metaindex(self, table_name):
        """Get the metaindex of a table."""
        sql_stmt = """DESCRIBE METAINDEX ON TABLE {}""".format(table_name)
        try:
            return self.run_sql(sql_stmt)
        except Exception:
            return None
