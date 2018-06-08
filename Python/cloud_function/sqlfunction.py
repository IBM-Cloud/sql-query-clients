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


args = json.loads(sys.argv[1])
ibmcloud_apikey = args.get("apikey", "")
if ibmcloud_apikey == "":
    print({'error': 'No API key specified'})
    quit()
sql_instance_crn = args.get("sqlquery_instance_crn", "")
if sql_instance_crn == "":
    print({'error': 'No SQL Query instance CRN specified'})
    quit()
target_url  = args.get("target_url", "")
if target_url == "":
    print({'error': 'No Cloud Object Storage target URL specified'})
    quit()
client_information = args.get("client_info", "ibmcloudsql cloud function")
sql_statement_text = args.get("sql", "")
if sql_statement_text == "":
    print({'error': 'No SQL statement specified'})
    quit()
sql_max_results = args.get("maxresults", "")
if sql_max_results == "":
    print({'info': 'No max results specified'})
sql_last_index = args.get("lastindex", "")
if sql_last_index == "":
    print({'info': 'No last index specified'})
sql_job_id = args.get("jobid", "")
if sql_job_id == "":
    print({'info': 'No job id specified'})    
sqlClient = ibmcloudsql.SQLQuery(ibmcloud_apikey, sql_instance_crn, target_url, client_info=client_information)
sqlClient.logon()
if sql_job_id == "":  
    jobId = sqlClient.submit_sql(sql_statement_text)
    sqlClient.wait_for_job(jobId)
    if sql_max_results == "":
        result = sqlClient.get_result(jobId)
    else:
        result = sqlClient.get_result(jobId).iloc[0:sql_max_results]
    if  len(sqlClient.get_result(jobId).index) > sql_max_results:
        is_truncated = True
    else:
        is_truncated = False
    result_location = sqlClient.get_job(jobId)['resultset_location']
else:     
    first_index = sql_last_index+1
    new_last_index = first_index+sql_max_results   
    result = sqlClient.get_result(sql_job_id).iloc[first_index:new_last_index]
    jobId = sql_job_id
    if  len(sqlClient.get_result(sql_job_id).index) > new_last_index:
        is_truncated = True
    else:
        is_truncated = False
    result_location = sqlClient.get_job(sql_job_id)['resultset_location'] 
access_code = 'import ibmcloudsql\n'
access_code += 'api_key="" # ADD YOUR API KEY HERE\n'
access_code += 'sqlClient = ibmcloudsql.SQLQuery(api_key, ' + sql_instance_crn + ', ' + target_url + ')\n'
access_code += 'sqlClient.logon()\n'
access_code += 'result_df = sqlClient.get_result(' + jobId + ')\n'

result_json={'jobId': jobId, 'result_location': result_location, 'result_access_pandas': access_code, 'result_set_sample': result.to_json(orient='table'), 'result_is_truncated': is_truncated}
print(json.dumps(result_json))


