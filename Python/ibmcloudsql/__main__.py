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


def main(dict):
    my_bluemix_apikey = 'YNiXREBMTfQsSzKrXYhQJElNXnUFEgpQ7qVVTkDK3_Zr'
    my_instance_crn = 'crn%3Av1%3Abluemix%3Apublic%3Asql-query%3Aus-south%3Aa%2Fd86af7367f70fba4f306d3c19c938f2f%3Ad1b2c005-e3d8-48c0-9247-e9726a7ed510%3A%3A'
    my_target_cos_endpoint = 's3.us-south.objectstorage.softlayer.net'
    my_target_cos_bucket = 'sqltempregional'
    sqlClient = ibmcloudsql.SQLQuery(my_bluemix_apikey, my_instance_crn, my_target_cos_endpoint, my_target_cos_bucket,
                                     client_info='ibmcloudsql cloud function test')
    sqlClient.logon()
    jobId = sqlClient.submit_sql(
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
        ORDER BY e.LastName, e.FirstName, NumOrders DESC")
    sqlClient.wait_for_job(jobId)
    result = sqlClient.get_result(jobId)

    return {'jobId': jobId, 'result_set': result.to_json(orient='table')}
