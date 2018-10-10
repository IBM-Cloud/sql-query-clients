import sys
sys.path.append('ibmcloudsql')
import ibmcloudsql
import test_credentials
import pandas as pd
pd.set_option('display.max_colwidth', -1)

sqlClient = ibmcloudsql.SQLQuery(test_credentials.apikey, test_credentials.instance_crn, client_info='ibmcloudsql test')
sqlClient.logon()

print("Running test with individual method invocation and Parquet target:")
jobId = sqlClient.submit_sql("SELECT * FROM cos://us-geo/sql/employees.parquet STORED AS PARQUET LIMIT 10 INTO {} STORED AS PARQUET".format(test_credentials.result_location))
sqlClient.wait_for_job(jobId)
try:
    result_df = sqlClient.get_result(jobId)
except ValueError as e:
    print(e)

print("Running test with individual method invocation and CSV target:")
jobId = sqlClient.submit_sql("SELECT * FROM cos://us-geo/sql/employees.parquet STORED AS PARQUET LIMIT 10 INTO {} STORED AS CSV".format(test_credentials.result_location))
sqlClient.wait_for_job(jobId)
result_df = sqlClient.get_result(jobId)
print("jobId {} restults are stored in {}. Result set is:".format(jobId, sqlClient.get_job(jobId)['resultset_location']))
print(result_df.head(200))

print("Running test with partitioned CSV target:")
jobId = sqlClient.submit_sql("SELECT * FROM cos://us-geo/sql/employees.parquet STORED AS PARQUET INTO cos://us-south/sqltempregional/ STORED AS CSV PARTITIONED BY (city)")
sqlClient.wait_for_job(jobId)
result_objects_df = sqlClient.list_results(jobId)
print(result_objects_df.head(200))
result_df = sqlClient.get_result(jobId)
print("jobId {} restults are stored in {}. Result set is:".format(jobId, sqlClient.get_job(jobId)['resultset_location']))
print(result_df.head(200))

print("Running test with compound method invocation:")
result_df = sqlClient.run_sql(
"WITH orders_shipped AS \
  (SELECT OrderID, EmployeeID, (CASE WHEN shippedDate < requiredDate \
                                   THEN 'On Time' \
                                   ELSE 'Late' \
                                END) AS Shipped \
   FROM cos://us-geo/sql/orders.parquet STORED AS PARQUET) \
SELECT e.FirstName, e.LastName, COUNT(o.OrderID) As NumOrders, Shipped \
FROM orders_shipped o, \
     cos://us-geo/sql/employees.parquet STORED AS PARQUET e \
WHERE e.EmployeeID = o.EmployeeID \
GROUP BY e.FirstName, e.LastName, Shipped \
ORDER BY e.LastName, e.FirstName, NumOrders DESC \
INTO {} STORED AS CSV".format(test_credentials.result_location))
print("Result set is:")
print(result_df.head(200))

print("Running test with SQL grammar error:")
print(sqlClient.run_sql("SELECT xyzFROM cos://us-geo/sql/employees.parquet STORED AS PARQUET LIMIT 10 INTO {} STORED AS CSV".format(test_credentials.result_location)))

print("Running test with SQL runtime error:")
print(sqlClient.run_sql("SELECT xyz FROM cos://us-geo/sql/employees.parquet STORED AS PARQUET LIMIT 10 INTO {} STORED AS CSV".format(test_credentials.result_location)))

print("SQL UI Link:")
sqlClient.sql_ui_link()

print("Job list:")
print(sqlClient.get_jobs().head(200))

print("COS Summary:")
print(sqlClient.get_cos_summary("cos://us-south/cloudant-access-logs-us-south/cloudant-access-logs/dt=2018-02-02"))

print("Test with target URL as separate parameter")
sqlClient = ibmcloudsql.SQLQuery(test_credentials.apikey, test_credentials.instance_crn, test_credentials.result_location, client_info='ibmcloudsql test')
sqlClient.logon()
jobId = sqlClient.submit_sql("SELECT * FROM cos://us-geo/sql/employees.parquet STORED AS PARQUET LIMIT 10")
sqlClient.wait_for_job(jobId)
result_objects_df = sqlClient.list_results(jobId)
print(result_objects_df.head(200))
result_df = sqlClient.get_result(jobId)
print(result_df.head(200))
