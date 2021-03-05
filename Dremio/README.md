# Dremio IBM SQL Query Connector

<img src="https://www.dremio.com/img/dremio-website.png" width="60"> <img src="https://1.cms.s81c.com/sites/default/files/2018-12-06/SQL-logo.jpeg" width="80">


## Overview

This is a community based IBM SQL Query Dremio connector made using the ARP framework. Check [Dremio Hub](https://github.com/dremio-hub) for more examples and [ARP Docs](https://github.com/dremio-hub/dremio-sqllite-connector#arp-file-format) for documentation. 

### What is Dremio?

Dremio delivers lightning fast query speed and a self-service semantic layer operating directly against your data lake storage and other sources. No moving data to proprietary data warehouses or creating cubes, aggregation tables and BI extracts. Just flexibility and control for Data Architects, and self-service for Data Consumers.

## Installation
You can launch the ready-to-use Dremio image with the latest release of the IBM SQL Query connector and the IBM SQL Query JDBC driver like follows:
 * `docker run -d -p 9047:9047 -p 31010:31010 -p 45678:45678 torsstei/dremio-ibm-sql-query`

Now you can open the Dremio console at this URL: http://localhost:9047 and proceed as descibed in Usage below.

## Usage

### Creating a new IBM SQL Query Source

In the Dremio UI click the `+` option for `External Sources` in the bottom left corner. Then select `IBMSQL` and specify the following parameters:

* JDBC URL 
    * Ex: `jdbc:ibmcloudsql:{instance-crn}`
    * The `{instance-crn}` is the unique identifier of your instance of SQL Query in your IBM Cloud account.
    * Make sure that the URL does not include the paramter `?targetcosurl=...`. This is specified in a separate parameter. See below.
    * See also `Connect` menu in your IBM SQL Query web console.
* API Key (IBM Cloud IAM API Key)
* Target COS URL
    * Ex: `cos://{IBM cloud region alias}/{bucket name}/{prefix}`
    * This is the IBM cloud object storage location where results for each SQL query are written. You can configure automatic [expliration](https://cloud.ibm.com/docs/cloud-object-storage?topic=cloud-object-storage-expiry) if you want an automatic cleanup.
    * This is the same value as in the field `Targert location` in your IBM SQL Query web console.

Learn  about IBM SQL Query JDBC client properties [here](https://cloud.ibm.com/docs/sql-query?topic=sql-query-jdbc)

## Development

### Manual Build and Installation of the connector

0. Change the pom's dremio.version to suit your Dremio's version.
   `<version.dremio> 4.9.1-202010230218060541-2e764ed0</version.dremio>`
1. In root directory with the pom.xml file run `mvn clean install -DskipTests` (or run the `build_jar.sh` script). If you want to run the tests, add the JDBC jar to your local maven repo along with environment variables that are required. Check the basic test example for more details.
2. Take the resulting `.jar` file in the target folder and put it in the <DREMIO_HOME>/jars folder in Dremio
3. Download the IBM SQL Query JDBC driver from [here](https://cloud.ibm.com/docs/sql-query?topic=sql-query-jdbc) and put in in the <DREMIO_HOME>/jars/3rdparty folder
4. Restart Dremio

### Building the docker image

Run `build_image.sh`.
