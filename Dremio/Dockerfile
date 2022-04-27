FROM dremio/dremio-oss

ARG DREMIO_VERSION

USER root

# Download JDBC driver and Dremio connector for SQL Query
RUN cd /tmp \
&& wget --output-document=/opt/dremio/jars/3rdparty/ibmcloudsql-jdbc.jar https://us.sql-query.cloud.ibm.com/download/jdbc/ibmcloudsql-jdbc-2.5.46.jar \
&& wget --output-document=/opt/dremio/jars/dremio-ibm-sql-query-plugin-$DREMIO_VERSION.jar https://github.com/IBM-Cloud/sql-query-clients/releases/download/Dremio_$DREMIO_VERSION/dremio-ibm-sql-query-plugin-$DREMIO_VERSION.jar

