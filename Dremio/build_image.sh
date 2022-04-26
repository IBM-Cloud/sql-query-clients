docker build --tag dremio-ibm-sql-query .
docker tag dremio-ibm-sql-query torsstei/dremio-ibm-sql-query:dremio20.1.0-202202061055110045-36733c65
docker tag dremio-ibm-sql-query torsstei/dremio-ibm-sql-query:latest
docker push torsstei/dremio-ibm-sql-query:dremio20.1.0-202202061055110045-36733c65
docker push torsstei/dremio-ibm-sql-query:latest

