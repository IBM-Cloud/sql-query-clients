ibmcloudsql
-----------

Allows you to run SQL statements in the IBM Cloud on data stored on object storage::

## Example usage
    import ibmcloudsql
    my_ibmcloud_apikey = '<your api key here>'
    my_instance_crn='<your ibm cloud sql query instance CRN here>'
    my_target_cos_url='<Cloud Object Storage URL for the SQL result target. Format: cos://<endpoint>/<bucket>/[<prefix>]>'
    sqlClient = SQLQuery(my_ibmcloud_apikey, my_instance_crn, my_target_cos_url)
    sqlClient.run_sql('SELECT * FROM cos://us-geo/sql/orders.parquet STORED AS PARQUET LIMIT 5").head()

## SQLQuery method list
 * `SQLQuery(api_key, instance_crn, target_cos_url, client_info='')` Constructor
 * `logon()`
 * `submit_sql(sql_text)` returns `jobId`as string
 * `wait_for_job(jobId)`
 * `get_result(jobId)` returns SQL result data frame
 * `delete_result(jobId)` deletes all result set objects in cloud object storage for the given jobId
 * `get_job(jobId)` returns details for the given job as a json object
 * `run_sql(sql_text)` Compound method that calls `submit_sql`, `wait_for_job` and `wait_for_job` in sequenceA
 * `sql_ui_link()` Returns browser link for SQL Query web console for currently configured instance
