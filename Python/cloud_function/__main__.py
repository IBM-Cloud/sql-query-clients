#
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
    #ibmcloud_apikey = 'YNiXREBMTfQsSzKrXYhQJElNXnUFEgpQ7qVVTkDK3_Zr'
    #sql_instance_crn = 'crn%3Av1%3Abluemix%3Apublic%3Asql-query%3Aus-south%3Aa%2Fd86af7367f70fba4f306d3c19c938f2f%3Ad1b2c005-e3d8-48c0-9247-e9726a7ed510%3A%3A'
    #target_endpoint = 's3.us-south.objectstorage.softlayer.net'
    #target_bucket = 'sqltempregional'
    sqlClient = ibmcloudsql.SQLQuery(ibmcloud_apikey, sql_instance_crn, target_endpoint, target_bucket,
                                     target_cos_prefix=target_prefix, client_info=client_infofmation)
    sqlClient.logon()
    jobId = sqlClient.submit_sql(sql_statement_text)
    #jobId = sqlClient.submit_sql(
    #    "WITH orders_shipped AS \
    #      (SELECT OrderID, EmployeeID, (CASE WHEN shippedDate < requiredDate \
    #                                       THEN 'On Time' \
    #                                       ELSE 'Late' \
    #                                    END) AS Shipped \
    #       FROM cos://us-geo/sql/orders.parquet STORED AS PARQUET) \
    #    SELECT e.FirstName, e.LastName, COUNT(o.OrderID) As NumOrders, Shipped \
    #    FROM orders_shipped o, \
    #         cos://us-geo/sql/employees.parquet STORED AS PARQUET e \
    #    WHERE e.EmployeeID = o.EmployeeID \
    #    GROUP BY e.FirstName, e.LastName, Shipped \
    #    ORDER BY e.LastName, e.FirstName, NumOrders DESC")
    sqlClient.wait_for_job(jobId)
    result = sqlClient.get_result(jobId)

    return {'jobId': jobId, 'result_set_sample': result.head(10).to_json(orient='table')}
