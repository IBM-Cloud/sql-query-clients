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
result_df = sqlClient.get_result(jobId)
print("jobId {} restults are stored in {}. Result set is:".format(jobId, sqlClient.get_job(jobId)['resultset_location']))
print(result_df.head(200))

print("Running test with individual method invocation and ORC target:")
jobId = sqlClient.submit_sql("SELECT * FROM cos://us-geo/sql/employees.parquet STORED AS PARQUET LIMIT 10 INTO {} STORED AS ORC".format(test_credentials.result_location))
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

print("Running test with individual method invocation and JSON target:")
jobId = sqlClient.submit_sql(
        "WITH orders as (SELECT customerid, named_struct('count', count(orderid), 'orderids', collect_list(orderid)) orders \
                FROM cos://us-geo/sql/orders.parquet STORED AS PARQUET  \
                GROUP BY customerid)    \
        SELECT c.customerid,    \
               named_struct('name', companyname, 'contact', contactname, 'tile', contacttitle, 'phone', PHONE) company, \
        	   named_struct('street', address, 'city', city, 'zip', postalcode, 'country', country) address,   \
        	   orders  \
        FROM cos://us-geo/sql/customers.parquet STORED AS PARQUET c,    \
             orders o   \
        WHERE o.customerid=c.customerid \
        INTO {} STORED AS JSON".format(test_credentials.result_location))
sqlClient.wait_for_job(jobId)
result_df = sqlClient.get_result(jobId)
print("jobId {} restults are stored in {}. Result set is:".format(jobId, sqlClient.get_job(jobId)['resultset_location']))
print(result_df.head(10))


print("Running test with partitioned CSV target:")
jobId = sqlClient.submit_sql("SELECT * FROM cos://us-geo/sql/employees.parquet STORED AS PARQUET INTO {} STORED AS CSV PARTITIONED BY (city)".format(test_credentials.result_location))
sqlClient.wait_for_job(jobId)
result_objects_df = sqlClient.list_results(jobId)
print(result_objects_df.head(200))
result_df = sqlClient.get_result(jobId)
print("jobId {} results are stored in {}. Result set is:".format(jobId, sqlClient.get_job(jobId)['resultset_location']))
print(result_df.head(200))

print("Running test with paginated parquet target:")
jobId = sqlClient.submit_sql("SELECT * FROM cos://us-geo/sql/employees.parquet STORED AS PARQUET LIMIT 10 INTO {} STORED AS PARQUET".format(test_credentials.result_location), 2)
sqlClient.wait_for_job(jobId)
result_df = sqlClient.get_result(jobId, 1)
print("jobId {} result page 1 is:".format(jobId))
print(result_df.head(200))
result_df = sqlClient.get_result(jobId, 5)
print("jobId {} result page 5 is:".format(jobId))
print(result_df.head(200))
print("Trying to retrieve non existing page number:")
try:
    result_df = sqlClient.get_result(jobId, 6)
except ValueError as e:
    print(e)
print("Trying to retrieve invalid page number:")
try:
    result_df = sqlClient.get_result(jobId, 0)
except ValueError as e:
    print(e)
print("Trying to use wrong data type for page number:")
try:
    result_df = sqlClient.get_result(jobId, 'abc')
except ValueError as e:
    print(e)
print("Trying to run SQL with invalid pagesize:")
try:
    jobId = sqlClient.submit_sql("SELECT * FROM cos://us-geo/sql/employees.parquet STORED AS PARQUET LIMIT 10 INTO {} STORED AS PARQUET".format(test_credentials.result_location), 0)
except ValueError as e:
    print(e)
print("Trying to run SQL with PARTITIONED clause plus pagesize:")
try:
    jobId = sqlClient.submit_sql("SELECT * FROM cos://us-geo/sql/employees.parquet STORED AS PARQUET LIMIT 10 INTO {} STORED AS PARQUET PARTITIONED BY (city)".format(test_credentials.result_location), 2)
except SyntaxError as e:
    print(e)

    
print("Running test with paginated JSON target:")
jobId = sqlClient.submit_sql(
        "WITH orders as (SELECT customerid, named_struct('count', count(orderid), 'orderids', collect_list(orderid)) orders \
                FROM cos://us-geo/sql/orders.parquet STORED AS PARQUET  \
                GROUP BY customerid)    \
        SELECT c.customerid,    \
               named_struct('name', companyname, 'contact', contactname, 'tile', contacttitle, 'phone', PHONE) company, \
        	   named_struct('street', address, 'city', city, 'zip', postalcode, 'country', country) address,   \
        	   orders  \
        FROM cos://us-geo/sql/customers.parquet STORED AS PARQUET c,    \
             orders o   \
        WHERE o.customerid=c.customerid \
        INTO {} STORED AS JSON".format(test_credentials.result_location), pagesize=10)
sqlClient.wait_for_job(jobId)
result_df_list = sqlClient.list_results(jobId)
print("jobId {} result pages:".format(jobId))
print(result_df_list.head(200))
result_df = sqlClient.get_result(jobId, pagenumber=2)
print("jobId {} result page 2 is:".format(jobId))
print(result_df.head(10))
    
    
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
pd.set_option('display.max_colwidth', 10)
print(sqlClient.get_jobs().head(200))
pd.set_option('display.max_colwidth', -1)

print("COS Summary:")
print(sqlClient.get_cos_summary(test_credentials.result_location))

print("Test with target URL as separate parameter")
sqlClient = ibmcloudsql.SQLQuery(test_credentials.apikey, test_credentials.instance_crn, test_credentials.result_location, client_info='ibmcloudsql test')
sqlClient.logon()
jobId = sqlClient.submit_sql("SELECT * FROM cos://us-geo/sql/employees.parquet STORED AS PARQUET LIMIT 10")
sqlClient.wait_for_job(jobId)
result_objects_df = sqlClient.list_results(jobId)
print(result_objects_df.head(200))
result_df = sqlClient.get_result(jobId)
print(result_df.head(200))

print("Test job history export to COS")
sqlClient.export_job_history(test_credentials.result_location + "/my_job_history/")

sqlClient = ibmcloudsql.SQLQuery(test_credentials.apikey, test_credentials.instance_crn, client_info='ibmcloudsql test')
sqlClient.logon()

print("Running EU test with individual method invocation and Parquet target:")
sqlClient_eu = ibmcloudsql.SQLQuery(test_credentials.apikey, test_credentials.eu_instance_crn, client_info='ibmcloudsql test')
sqlClient_eu.logon()
jobId = sqlClient_eu.submit_sql("SELECT * FROM cos://us-geo/sql/employees.parquet STORED AS PARQUET LIMIT 10 INTO {} STORED AS PARQUET".format(test_credentials.eu_result_location))
sqlClient_eu.wait_for_job(jobId)
result_df = sqlClient_eu.get_result(jobId)
print("jobId {} restults are stored in {}. Result set is:".format(jobId, sqlClient_eu.get_job(jobId)['resultset_location']))
print(result_df.head(200))
print("EU SQL UI Link:")
sqlClient_eu.sql_ui_link()
