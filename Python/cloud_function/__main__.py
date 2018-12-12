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
# main() will be run when you invoke this action
#
# @param Cloud Functions actions accept a single parameter, which must be a JSON object.
#
# @return The output of this action, which must be a JSON object.
#
#
import sys
import ibmcloudsql


def main(args):
    ibmcloud_apikey = args.get("apikey", "")
    if ibmcloud_apikey == "":
        return {'error': 'No API key specified'}
    sql_instance_crn = args.get("sqlquery_instance_crn", "")
    if sql_instance_crn == "":
        return {'error': 'No SQL Query instance CRN specified'}
    target_url  = args.get("target_url", "")
    client_information = args.get("client_info", "ibmcloudsql cloud function")
    sql_statement_text = args.get("sql", "")
    if sql_statement_text == "":
        return {'error': 'No SQL statement specified'}
    sqlClient = ibmcloudsql.SQLQuery(ibmcloud_apikey, sql_instance_crn, target_url, client_info=client_information)
    sqlClient.logon()
    try:
        jobId = sqlClient.submit_sql(sql_statement_text)
    except Error as e:
        return {'Error': e}

    jobDetails = sqlClient.get_job(jobId)

    access_code = 'import ibmcloudsql\n'
    access_code += 'api_key="" # ADD YOUR API KEY HERE\n'
    access_code += 'sqlClient = ibmcloudsql.SQLQuery(api_key, ' + sql_instance_crn + ', ' + target_url + ')\n'
    access_code += 'sqlClient.logon()\n'
    access_code += 'result_df = sqlClient.get_result(' + jobId + ')\n'

    return {'jobId': jobId, 'result_location': jobDetails['resultset_location'], 'job_status':  jobDetails['status'],
            'result_access_pandas': access_code}

