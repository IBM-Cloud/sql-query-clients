# sql-query-clients [![Build Status](https://travis-ci.org/IBM-Cloud/sql-query-clients.svg?branch=master)](https://travis-ci.org/IBM-Cloud/sql-query-clients)

This repository contains application client samples and blueprint code for the [IBM Cloud SQL Query service](https://cloud.ibm.com/catalog/services/sql-query#about).  

Please refer to [SQL Query Getting Started](https://cloud.ibm.com/docs/services/sql-query?topic=sql-query-gettingstarted) for general information and turorial for this service.

## List of clients
 * [ibmcloudsql](https://github.com/IBM-Cloud/sql-query-clients/tree/master/Python) Python SDK
 * [Cloud Function](https://github.com/IBM-Cloud/sql-query-clients/tree/master/Python/cloud_function) for SQL Query (uses `ibmcloudsql`)
 * [sqlQuery](https://github.com/IBM-Cloud/sql-query-clients/tree/master/Node) Node SDK
 * [Documentation](https://ibm-cloud.github.io/sql-query-clients/)

## How to generate docs

Requirement: conda 

* In the docs folder, you run [if you don’t have sphinx and required package yet]

`make setup`

This create `sphinx` environment. Make sure you're in this environment each time you run the below commands

* Get docstring updated

`make python`

* generate docs in local file (in /tmp/sql-query-clients-docs/html - for the purpose of local check the output)

`make html` 

* (check local generated content carefully before running this) generate and push to the server [only those with given priviledges]

`make buildandcommithtml`
