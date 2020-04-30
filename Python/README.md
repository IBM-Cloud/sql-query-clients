# ibmcloudsql

Allows you to run SQL statements in the IBM Cloud on data stored on object storage::

## Building and testing the library locally
### Set up Python environment
Run `source ./setup_env.sh` which creates and activates a clean virtual Python environment. It uses Python 2.7 by default. Adapt line 2 inside the script if you want a different version.
### Install the local code in your Python environment
Run `./_install`.
### Test the library locally
1. Create a file `ibmcloudsql/test_credentials.py` with the following three lines and your according properties:
```
apikey='<your IBM Cloud API key>'
instance_crn='<your SQL Query instance CRN>'
result_location='<COS URI of default result location for your SQL result sets>'
```
2. Run `python ibmcloudsql/test.py`.
### Packaging and publishing distribution
1. Make sure to increase `version=...` in `setup.py` before creating a new package.
2. Run `package.sh`. It will prompt for user and password that must be authorized for package `ibmcloudsql` on pypi.org.

## Example usage
```
import ibmcloudsql
my_ibmcloud_apikey = '<your api key here>'
my_instance_crn='<your ibm cloud sql query instance CRN here>'
my_target_cos_url='<Cloud Object Storage URL for the SQL result target. Format: cos://<endpoint>/<bucket>/[<prefix>]>'
sqlClient = SQLQuery(my_ibmcloud_apikey, my_instance_crn)
sqlClient.run_sql('SELECT * FROM cos://us-geo/sql/orders.parquet STORED AS PARQUET LIMIT 5 INTO {} STORED AS CSV'.format(my_target_cos_url)).head()
```

## Demo notebook
You can use IBM Watson Studio with the following [demo notebook](https://dataplatform.cloud.ibm.com/exchange/public/entry/view/4a9bb1c816fb1e0f31fec5d580e4e14d) that shows some elaborate examples of using various aspects of ibmcloudsql.

## SQLQuery method list
 * `SQLQuery(api_key, instance_crn, target_cos_url=None, client_info='')` Constructor
 * `logon(force=False)` Needs to be called before any other method below. Logon is valid for one hour. The invocation is a No-Op if previous logon is less than 5 minutes ago. You can force logon anyway with optional paramater `force=True`.
 * `submit_sql(sql_text, pagesize=None)` Returns `jobId`as string. Optional pagesize parameter (in rows) for paginated result objects.
 * `wait_for_job(jobId)` Waits for job to end and returns job completion state (either `completed` or `failed`)
 * `get_result(jobId, pagenumber=None)` returns SQL result data frame for entire result or for specified page of results.
 * `list_results(jobId)` Returns a data frame with the list of result objects written
 * `delete_result(jobId)` Deletes all result set objects in cloud object storage for the given jobId
 * `rename_exact_result(jobId)` Renames single partitioned query result to exact single object name without folder hierarchy.
 * `get_job(jobId)` Returns details for the given SQL job as a json object
 * `get_jobs()` Returns the list of recent 30 submitted SQL jobs with all details as a data frame
 * `run_sql(sql_text)` Compound method that calls `submit_sql`, `wait_for_job` and `wait_for_job` in sequenceA
 * `sql_ui_link()` Returns browser link for SQL Query web console for currently configured instance
 * `get_cos_summary(cos_url)` Returns summary for stored number of objects and volume for a given cos url as a json
 * `list_cos_objects(cos_url)` Returns a data frame with the list of objects found in the given cos url
 * `export_job_history(cos_url)` Exports new jobs as parquet file to the given cos url

## Exceptions
 * `RateLimitedException(message)` raised when jobs can't be submitted due to 429 / Plan limit for concurrent queries has been reached
## Constructor options
 * `api_key`: IAM API key
 * `instance_crn`: SQL Query instance CRN identifier
 * `target_cos_url`: Optional default target URL. Don't use when you want to provide target URL in SQL statement text.
 * `client_info`: Optional string to identify your client application in IBM Cloud for PD reasons.
 * `max_tries`: Optional integer to specify maximum attempts when dealing with request rate limit. Default value is `1`, which means it will through exception `RateLimitedException` when response status code is `429`. It will enable _exponential backoff_ when specifying any positive number greater than `1`. For instance, given `max_tries=5`, assuming it will get response status code `429` for 4 times until the 5th attempt will get response status code `201`, the wait time will be `2s`, `4s`, `8s` and `16s` for each attempts.
