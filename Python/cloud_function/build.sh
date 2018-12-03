docker build --tag --no-cache torsstei/sqlfunction:latest .
docker push torsstei/sqlfunction 
docker tag torsstei/sqlfunction:latest ibmfunctions/sqlquery:latest
docker push ibmfunctions/sqlquery:latest

