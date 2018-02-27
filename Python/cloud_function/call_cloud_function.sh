bx wsk action invoke -br --result ibmcloudsql_cloudfunction \
 --param sql "SELECT * FROM cos://us-geo/sql/employees.parquet STORED AS PARQUET"
bx wsk activation list
#bx wsk activation get b8696d16977f45e8a96d16977f95e804
