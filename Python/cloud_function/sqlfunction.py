# ------------------------------------------------------------------------------
# Copyright IBM Corp. 2018
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ------------------------------------------------------------------------------
#
# @param Cloud Functions actions accept a single parameter, which must be a JSON object.
#
# @return The output of this action, which must be a JSON object.
#
#
import sys
import ibmcloudsql
import json
import os


args = json.loads(sys.argv[1])
ibmcloud_apikey = args.get("apikey", "")
sql_instance_crn = args.get("sqlquery_instance_crn", "")
target_url  = args.get("target_url", "")
client_information = args.get("client_info", "ibmcloudsql cloud function: " + os.environ['__OW_ACTION_NAME'])
sql_job_id = args.get("jobid", "")
sql_statement_text = args.get("sql", "")
sql_index = args.get("index", "")
sql_max_results = args.get("maxresults", "")
sql_async_execution = args.get("async", False)

if ibmcloud_apikey == "":
    print({'error': 'No API key specified'})
    quit()
if sql_instance_crn == "":
    print({'error': 'No SQL Query instance CRN specified'})
    quit()
if sql_statement_text == "":
    if sql_job_id == "":
        print({'error': 'Neither SQL statement nor job id specified'})
        quit()
    if sql_index == "":
        print({'info': 'No starting index specified. Will return starting with first row'})
if sql_max_results == "":
    print({'info': 'No max results specified. Will return all results'})

sqlClient = ibmcloudsql.SQLQuery(ibmcloud_apikey, sql_instance_crn, target_url, client_info=client_information)
sqlClient.logon()
next_index = ""
if sql_job_id == "":  
    jobId = sqlClient.submit_sql(sql_statement_text)
    if not sql_async_execution:
        sqlClient.wait_for_job(jobId)
        if sql_max_results == "":
            result = sqlClient.get_result(jobId)
        else:
            result = sqlClient.get_result(jobId).iloc[0:sql_max_results]
            if  len(sqlClient.get_result(jobId).index) > sql_max_results:  next_index = sql_max_results
else:     
    first_index = sql_index
    last_index = first_index+sql_max_results   
    result = sqlClient.get_result(sql_job_id).iloc[first_index:last_index]
    jobId = sql_job_id
    if  len(sqlClient.get_result(sql_job_id).index) > last_index: next_index = last_index
jobDetails = sqlClient.get_job(jobId)
access_code = 'import ibmcloudsql\n'
access_code += 'api_key="" # ADD YOUR API KEY HERE\n'
access_code += 'sqlClient = ibmcloudsql.SQLQuery(api_key, ' + sql_instance_crn + ', ' + target_url + ')\n'
access_code += 'sqlClient.logon()\n'
access_code += 'result_df = sqlClient.get_result(' + jobId + ')\n'

result_json={'action_name': os.environ['__OW_ACTION_NAME'], 'jobId': jobId, 'result_location': jobDetails['resultset_location'],
             'async_execution': sql_async_execution, 'job_status':  jobDetails['status'], 'result_access_pandas': access_code}
if not sql_async_execution:
    result_json['result_set_sample'] = result.to_json(orient='table')
    result_json['result_next_index'] = next_index
print(json.dumps(result_json))


