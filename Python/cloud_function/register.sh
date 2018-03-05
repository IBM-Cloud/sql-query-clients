#!/usr/bin/env bash

# Create/Replace the cloud function
# We set the maximum allowed timeout of 5 minutes:
bx wsk action delete sqlcloudfunction
bx wsk action create sqlcloudfunction --timeout 300000 --docker torsstei/sqlfunction
