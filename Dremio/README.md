# Dremio IBM SQL Query Connector

<img src="https://www.dremio.com/img/dremio-website.png" width="60"> <img src="https://1.cms.s81c.com/sites/default/files/2018-12-06/SQL-logo.jpeg" width="80">


## Overview

This is a community based IBM SQL Query Dremio connector made using the ARP framework. Check [Dremio Hub](https://github.com/dremio-hub) for more examples and [ARP Docs](https://github.com/dremio-hub/dremio-sqllite-connector#arp-file-format) for documentation. 

### What is Dremio?

Dremio delivers lightning fast query speed and a self-service semantic layer operating directly against your data lake storage and other sources. No moving data to proprietary data warehouses or creating cubes, aggregation tables and BI extracts. Just flexibility and control for Data Architects, and self-service for Data Consumers.

## Installation

### Run Dremio with SQL Query connector locally

You can launch the ready-to-use Dremio image with the latest release of the IBM SQL Query connector and the IBM SQL Query JDBC driver like follows:
 * `docker run -d -p 9047:9047 -p 31010:31010 -p 45678:45678 torsstei/dremio-ibm-sql-query`

Now you can open the Dremio console at this URL: http://localhost:9047 and proceed as descibed in Usage below.

### Run Dremio with SQL Query connector in IBM Cloud

You can use helm charts to deploy an entire Dremio cluster on Kubernetes in IBM Cloud's managed [Kubernetes Service](https://www.ibm.com/cloud/kubernetes-service).

* Make sure you have helm installed on your local machine. For instance use `brew install kubernetes-helm` on Mac OS.
* Make sure you have Kubernetes cluster created in your IBM Cloud account.
* Install the IBM Cloud [CLI tool](https://cloud.ibm.com/docs/cli?topic=cli-install-ibmcloud-cli).
* Install and Set up the Kubernetes container service plugin for the IBM Cloud CLI and the kubectl CLI tool for your Kubernetes cluster as described [here](https://cloud.ibm.com/docs/containers?topic=containers-cs_cli_install).
* Clone the github repository with the Dremio helm charts for IBM Cloud:
   * `git clone https://github.com/IBM-Cloud/dremio-cloud-tools.git`
* Go to the directoy with the desired configuration
   * `cd dremio-cloud-tools/charts/dremio_v2`
   * If you want to start with a smaller cluster with less resources use `cd dremio-cloud-tools/charts/dremio_v2_small` instead.
* Submit the helm chart deployment `helm install --wait . --generate-name`
* You can list the deployed helm charts with `helm list`
* You can use the Kubernetes dashboard (can be launched from the IBM Cloud dashboard UI for your Kubernetes cluster) or the `kubectl` CLI to observe the status of the individual assets that helm has deployed in your Kubernetes cluster.
* Identify the load balancer ingress host name of the Dremio server in your Kubernetes cluster
   * `kubectl describe service dremio-client | grep LoadBalancer`
   * Now open URL `http://{hostname}:9047` in your browser to get the Dremio web console.
   * Alternatively you can also go to the Kubernetes dashboard and click on the second Endpoint in `Service->Services->"dremio-client"->External Endpoints` (this is the endpoint with port 9047 for the Dremio console).

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
    * This is the IBM cloud object storage location where results for each SQL query are written. You can configure automatic [expiration](https://cloud.ibm.com/docs/cloud-object-storage?topic=cloud-object-storage-expiry) if you want an automatic cleanup.
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
