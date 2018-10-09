# ibmcloudsql

Allows you to run SQL statements in the IBM Cloud on data stored on object storage::

## Example usage
```
import ibmcloudsql
my_ibmcloud_apikey = '<your api key here>'
my_instance_crn='<your ibm cloud sql query instance CRN here>'
my_target_cos_url='<Cloud Object Storage URL for the SQL result target. Format: cos://<endpoint>/<bucket>/[<prefix>]>'
sqlClient = SQLQuery(my_ibmcloud_apikey, my_instance_crn)
sqlClient.run_sql('SELECT * FROM cos://us-geo/sql/orders.parquet STORED AS PARQUET LIMIT 5 INTO {} STORED AS CSV'.format(my_target_cos_url)).head()
```

## SQLQuery method list
 * `SQLQuery(api_key, instance_crn, target_cos_url=None, client_info='')` Constructor
 * `logon()` Needs to be called before any other method below. Logon is valid for one hour.
 * `submit_sql(sql_text)` returns `jobId`as string
 * `wait_for_job(jobId)` Waits for job to end and returns job completion state (either `completed` or `failed`)
 * `get_result(jobId)` returns SQL result data frame
 * `list_results(jobId)` returns a data frame with the list of result objects written
 * `delete_result(jobId)` deletes all result set objects in cloud object storage for the given jobId
 * `get_job(jobId)` returns details for the given SQL job as a json object
 * `get_jobs()` returns the list of recent 30 submitted SQL jobs with all details as a data frame
 * `run_sql(sql_text)` Compound method that calls `submit_sql`, `wait_for_job` and `wait_for_job` in sequenceA
 * `sql_ui_link()` Returns browser link for SQL Query web console for currently configured instance
 * `get_cos_summary()` Returns summary for stored number of objects and volume for a given cos url as a  json 
