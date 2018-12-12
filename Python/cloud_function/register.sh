#!/usr/bin/env bash

# Create/Replace the cloud function
# We set the maximum allowed timeout of 5 minutes:
ibmcloud fn action delete sqlcloudfunction
ibmcloud fn action create sqlcloudfunction --timeout 300000 --docker ibmfunctions/sqlquery
