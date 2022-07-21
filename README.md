# sql-query-clients [![Actions Status](https://github.com/IBM-Cloud/sql-query-clients/workflows/Python%20CI/badge.svg)](https://github.com/IBM-Cloud/sql-query-clients/actions) [![Actions Status](https://github.com/IBM-Cloud/sql-query-clients/workflows/Node.js%20CI/badge.svg)](https://github.com/IBM-Cloud/sql-query-clients/actions)

This repository contains application client samples and blueprint code for the [IBM Cloud Data Engine service](https://cloud.ibm.com/catalog/services/sql-query#about).


## List of clients
 * [ibmcloudsql](https://github.com/IBM-Cloud/sql-query-clients/tree/master/Python) Python SDK
 * [Cloud Function](https://github.com/IBM-Cloud/sql-query-clients/tree/master/Python/cloud_function) for Data Engine (uses `ibmcloudsql`)
 * [sqlQuery](https://github.com/IBM-Cloud/sql-query-clients/tree/master/Node) Node SDK **deprecated** (Use this [Data Engine Node SDK]( https://github.com/IBM/sql-query-node-sdk) instead)
 * [Dremio](https://github.com/IBM-Cloud/sql-query-clients/tree/master/Dremio) connector
 * [Grafana](https://github.com/IBM-Cloud/sql-query-clients/tree/master/Grafana) connector

## Documentation
 * Please refer to [Data Engine Getting Started](https://cloud.ibm.com/docs/services/sql-query?topic=sql-query-getting-started) for general information and turorial for this service.
 * The documentation for [ibmcloudsql Python API](https://ibm-cloud.github.io/sql-query-clients/)
 * How to use `ibmcloudsql` in a [Python Notebook](https://dataplatform.cloud.ibm.com/exchange/public/entry/view/4a9bb1c816fb1e0f31fec5d580e4e14d)

## How to generate docs

Requirement: conda

* In the docs folder, you run [if you don’t have sphinx and required package yet]

`make setup`

This create `sphinx` environment. Make sure you're in this environment each time you run the below commands

* Get docstring updated

`make python`

* generate docs in local file (in /tmp/sql-query-clients-docs/html - for the purpose of local check the output)

`make html`

Check the output by opening the browser with the URL: `file:///tmp/sql-query-clients-docs/html/index.html`

* (check the local content carefully before running this) generate and commit to the server [only those with proper  priviledges]

`make buildandcommithtml`
