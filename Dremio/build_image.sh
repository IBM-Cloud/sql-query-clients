docker build --tag dremio-ibm-sql-query .
docker tag dremio-ibm-sql-query torsstei/dremio-ibm-sql-query
docker push torsstei/dremio-ibm-sql-query:latest

