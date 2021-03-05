FROM dremio/dremio-oss

USER root

# Download JDBC driver and Dremio connector for SQL Query
RUN cd /tmp \
&& wget --output-document=/opt/dremio/jars/3rdparty/ibmcloudsql-jdbc.jar https://us.sql-query.cloud.ibm.com/download/jdbc/ibmcloudsql-jdbc-2.5.20.jar \
&& wget --output-document=/opt/dremio/jars/dremio-ibm-sql-query-plugin-12.1.0-202101041749050132-55c827cb.jar https://github.com/IBM-Cloud/sql-query-clients/releases/download/Dremio-v0.1/dremio-ibm-sql-query-plugin-12.1.0-202101041749050132-55c827cb.jar

