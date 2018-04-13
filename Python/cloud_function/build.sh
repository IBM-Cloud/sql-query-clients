docker build --tag torsstei/sqlfunction:latest .
docker push torsstei/sqlfunction 
docker tag torsstei/sqlfunction:latest ibmfunctions/sqlquery:latest
docker push ibmfunctions/sqlquery:latest

