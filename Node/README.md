# ibmcloudsql - Node

Allows you to run SQL statements in the IBM Cloud on data stored on object storage.

## Installation

using npm:

```
$ npm install -g npm
$ npm install --save ibm-cloud-sql
```

## Example Usage

```
var sqlQuery = new SqlQuery(apikey, crn, targetCosUrl);

sqlQuery.runSql("select * from cos://us-south/employees/banklist.csv limit 5").then(data => console.log(data));
```

## SQLQuery method list
 * `SqlQuery(api_key, instance_crn, target_cos_url)` Constructor
 * `logon()` Needs to be called before any other method below. Logon is valid for one hour.
 * `submitSql(sql_text)` returns `jobId`as string
 * `waitForJob(jobId)` Waits for job to end and returns job completion state (either `completed` or `failed`)
 * `getResult(jobId)` returns SQL result data frame
 * `deleteResult(jobId)` deletes all result set objects in cloud object storage for the given jobId
 * `getJob(jobId)` returns details for the given SQL job as a JSON object
 * `getJobs()` returns the list of recent 30 submitted SQL jobs with all details as a data frame
 * `runSql(sql_text)` Compound method that calls `submitSql`, `waitForJob` and `getResult` in sequence
 * `sqlUILink()` Returns browser link for SQL Query web console for currently configured instance