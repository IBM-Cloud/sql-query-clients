FROM dremio/dremio-oss

USER root

# Download JDBC driver and Dremio connector for SQL Query
RUN cd /tmp \
&& wget --output-document=/opt/dremio/jars/3rdparty/ibmcloudsql-jdbc.jar https://us.sql-query.cloud.ibm.com/download/jdbc/ibmcloudsql-jdbc-2.5.46.jar \
&& wget --output-document=/opt/dremio/jars/dremio-ibm-sql-query-plugin-20.1.0-202202061055110045-36733c65.jar https://github.com/IBM-Cloud/sql-query-clients/releases/download/Dremio_20.1.0-202202061055110045-36733c65/dremio-ibm-sql-query-plugin-13.1.0.jar

