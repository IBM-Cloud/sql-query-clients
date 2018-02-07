ibmcloudsql
-----------

Allows you to run SQL statements in the IBM Cloud on data stored on object storage::

    >>> import ibmcloudsql
    >>> my_ibmcloud_apikey = '<your api key here>'
    >>> my_instance_crn='<your ibm cloud sql query instance CRN here>'
    >>> my_target_cos_endpoint='<your ibm cloud object storage endpoint name here>'
    >>> my_target_cos_bucket='<your ibm cloud object storage bucket name here>'
    >>> my_target_cos_prefix='<your ibm cloud object storage object prefix here>'
    >>> sqlClient = SQLQuery(my_bluemix_apikey, my_instance_crn, my_target_cos_endpoint, my_target_cos_bucket, my_target_cos_prefix')
    >>> sqlClient.run_sql('SELECT * FROM cos://us-geo/sql/orders.parquet STORED AS PARQUET LIMIT 5").head()


