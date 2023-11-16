"""
This is the test script
"""
# flake8: noqa W191
import pandas as pd
import cosaccess  # noqa
import test_credentials  # noqa
from cosaccess import CosAccessManager

pd.set_option("display.max_colwidth", None)
pd.set_option("display.max_columns", 20)

print("Initializing CosAccessManager...")
cosaccess = CosAccessManager(apikey=test_credentials.apikey)

print("get_users()...")
print(cosaccess.get_users().head(5))

print("get_service_ids()...")
print(cosaccess.get_service_ids().head(5))

print("get_access_groups()...")
print(cosaccess.get_access_groups().head(5))

print("get_policies_for_cos_bucket()...")
print(cosaccess.get_policies_for_cos_bucket("sqltempregional").head(5))

print("get_policies_for_cos_bucket()...")
print(cosaccess.get_policies_for_cos_bucket("results").head(5))

print("get_policies_for_cos_bucket() with prefix...")
print(cosaccess.get_policies_for_cos_bucket("results", "data_mart/table1/foo").head(5))

