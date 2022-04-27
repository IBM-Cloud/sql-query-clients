version=$(grep "<version>" pom.xml | head -1 | sed 's/^.*<version>//g' | sed 's/<\/version>.*$//g')
echo Make sure that you have a release created with the SQL Query connector jar for Dremio versio $version.
echo Building image for Dremio version $version...

docker build --build-arg DREMIO_VERSION=$version --tag dremio-ibm-sql-query .
docker tag dremio-ibm-sql-query torsstei/dremio-ibm-sql-query:dremio$version
docker tag dremio-ibm-sql-query torsstei/dremio-ibm-sql-query:latest
docker push torsstei/dremio-ibm-sql-query:dremio$version
docker push torsstei/dremio-ibm-sql-query:latest

