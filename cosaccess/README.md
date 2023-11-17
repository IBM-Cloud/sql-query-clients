# cosaccess

## Setup
```
pip install coaccess
```

Manage IBM Cloud COS access privileges on bucket and object level

## Example usage
```
from cosaccess import CosAccessManager
cosaccess = CosAccessManager('<your api key here>')
cosaccess.get_policies_for_cos_bucket('<your bucket name>')
```

## CosAccessManager method list
 * `CosAccessManager(apikey, account_id=None)` Constructor
 * `get_policies_for_cos_bucket(cosBucket, prefix = None):` Returns a dataframe with all policies defined on the COS bucket. When prefix is provided the results only show polcies that are relevant for access to that prefix path.
 * `grant_bucket_access(roles, cos_instance, cos_bucket, prefixes = None, access_group = None, iam_id = None)` Create new access policy for the COS bucket and optionally prefix
 * `update_bucket_access(policy_id, roles, cos_instance, cos_bucket, prefixes = None, access_group = None, iam_id = None)` Overwrites an existing access policy for the COS bucket and optionally prefix
 * `remove_bucket_access(policy_id)` Deletes an existing access policy
 * `get_users()` Returns a dataframe with all users and their details in the account
 * `get_user_iam_id(user_id):` Get the IAM ID of a user specified by name (IBM ID email address)
 * `get_user_name(iam_id)` Get user name in format `<given name> <last name> <email>` for a given IAM ID
 * `get_service_ids()` Returns a dataframe with all Service IDs and their details in the account
 * `get_service_id_iam_id(service_id):` Get the IAM ID of a Service ID specified by Service ID name
 * `get_service_id_name(iam_id)` Get Service ID name for a given IAM ID
 * `get_access_groups()` Returns a dataframe with all acces groups and their details in the account
 * `get_access_group_id(access_group):` Get the access group ID for an access group name
 * `get_access_group_name(access_group_id)` et the access group name for an access group ID
 * `get_policy(policy_id)` Returns a JSON dict with all policy details for the provided policy ID
 * `list_policies()` Returns an array of JSON dicts with all policies and their details in the account
 * `list_policies_for_service(serviceName)` Returns an array of JSON dicts with all policies and their details specified for the provided service type (e.g., `cloud-object-storage`)
 * `list_policies_for_cos_instance(cosServiceInstance)` Returns an array of JSON dicts with all policies and their details specified COS service instance ID
 * `list_policies_for_cos_bucket(cosBucket, prefix = None):` Returns an array of JSON dicts with all policies defined on the COS bucket. When prefix is provided the results only show polcies that are relevant for access to that prefix path.
## Constructor options
 * `apikey`: IAM API key.
 * `account_id`: The IBM Cloud account holding the COS instance(s) for which you want to manage access. Default is the account of the provided API Key.

## Building and testing the library locally
### Set up Python environment
Run `source ./setup_env.sh` which creates and activates a clean virtual Python environment.
### Install the local code in your Python environment
Run `./_install.sh`.
### Test the library locally
1. Create a file `cosaccess/test_credentials.py` with the IBM Cloud IAM API Key:
```
apikey='<your IBM Cloud API key>'
```
you can use the template file `cosaccess/test_credentials.py.template`

2. Run `python cosaccess/test.py`.

### Packaging and publishing distribution
1. Make sure to increase `version=...` in `setup.py` before creating a new package.
2. Run `package.sh`. It will prompt for user and password that must be authorized for package `cosaccess` on pypi.org.
