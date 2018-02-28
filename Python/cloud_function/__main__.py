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
    target_endpoint  = args.get("cos_endpoint", "")
    if target_endpoint == "":
        return {'error': 'No Cloud Object Storage target endpoint specified'}
    target_bucket = args.get("cos_bucket", "")
    if target_bucket == "":
        return {'error': 'No Cloud Object Storage target bucket specified'}
    target_prefix = args.get("cos_prefix", "")
    client_infofmation = args.get("client_info", "ibmcloudsql cloud function")
    sql_statement_text = args.get("sql", "")
    if sql_statement_text == "":
        return {'error': 'No SQL statement specified'}
    sqlClient = ibmcloudsql.SQLQuery(ibmcloud_apikey, sql_instance_crn, target_endpoint, target_bucket,
                                     target_cos_prefix=target_prefix, client_info=client_infofmation)
    sqlClient.logon()
    jobId = sqlClient.submit_sql(sql_statement_text)
    sqlClient.wait_for_job(jobId)
    result = sqlClient.get_result(jobId)
    result_location = sqlClient.get_job(jobId)['resultset_location']

    return {'jobId': jobId, 'result_location': result_location, 'result_set_sample': result.head(10).to_json(orient='table')}
