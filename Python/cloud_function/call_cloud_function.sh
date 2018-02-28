#!/usr/bin/env bash

# Call the cloud function with a SQL statement as parameter
# We use the -br parameter so that it is a blocking call and the function results
# get displayed on the console afterwards:
bx wsk action invoke -br --result ibmcloudsql_cloudfunction \
 --param sql "SELECT * FROM cos://us-geo/sql/employees.parquet STORED AS PARQUET"

# List the recent cloud function executions (a.k.a. activations):
bx wsk activation list

# Display the results of a specific previous cloud function run. You need to replace the
# ID with the activation ID of your choice:
#bx wsk activation get b8696d16977f45e8a96d16977f95e804
