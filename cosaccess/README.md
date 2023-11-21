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

## Demo
Here is a little [demo notebook](https://dataplatform.cloud.ibm.com/analytics/notebooks/v2/2471b8af-1ee2-4b57-a81e-5de09199fe49/view?access_token=f5b64c8129c72ec65dc1a898146bb28723205dbb4b31827d19180c3bae7902df&context=cpdaas) that shows a few more usage examples.


## CosAccessManager method list
### Initialization
 * `CosAccessManager(apikey, account_id=None)` Constructor. `apikey`: IAM API key. `account_id`: The IBM Cloud account holding the COS instance(s) for which you want to manage access. Default is the account of the provided API Key.
### Retrieving Access Policies
 * `get_policies_for_cos_bucket(cosBucket, prefix = None, roles = None):` Returns a dataframe with all policies defined on the COS bucket. When prefix is provided the results only show polcies that are relevant for access to that prefix path. When a list of roles is provided only policies that assign at least on of these roles are returned.
 * `get_policy(policy_id)` Returns a JSON dict with all policy details for the provided policy ID
 * `list_policies(roles = None)` Returns an array of JSON dicts with all policies and their details in the account. When a list of roles is provided only policies that assign at least on of these roles are returned.
 * `list_policies_for_service(serviceName, roles = None)` Returns an array of JSON dicts with all policies and their details specified for the provided service type (e.g., `cloud-object-storage`). When a list of roles is provided only policies that assign at least on of these roles are returned.
 * `list_policies_for_cos_instance(cosServiceInstance, roles = None)` Returns an array of JSON dicts with all policies and their details specified COS service instance ID. When a list of roles is provided only policies that assign at least on of these roles are returned.
 * `list_policies_for_cos_bucket(cosBucket, prefix = None, roles = None):` Returns an array of JSON dicts with all policies defined on the COS bucket. When prefix is provided the results only show polcies that are relevant for access to that prefix path. When a list of roles is provided only policies that assign at least on of these roles are returned.
### CRUD for Access Policies
 * `grant_bucket_access(roles, cos_bucket, prefixes = None, access_group = None, iam_id = None)` Create new access policy for the COS bucket and optionally prefix
 * `update_bucket_access(policy_id, roles, cos_bucket, prefixes = None, access_group = None, iam_id = None)` Overwrites an existing access policy for the COS bucket and optionally prefix
 * `remove_bucket_access(policy_id)` Deletes an existing access policy
### COS Helper Methods
 * `get_cos_instance_id(bucket)` Returns the instance ID of the COS instance holding the provided COS bucket
### Working with Users
 * `get_users()` Returns a dataframe with all users and their details in the account
 * `get_user_iam_id(user_id):` Get the IAM ID of a user specified by name (IBM ID email address)
 * `get_user_name(iam_id)` Get user name in format `<given name> <last name> <email>` for a given IAM ID
### Working with Service IDs
 * `get_service_ids()` Returns a dataframe with all Service IDs and their details in the account
 * `get_service_id_iam_id(service_id):` Get the IAM ID of a Service ID specified by Service ID name
 * `get_service_id_name(iam_id)` Get Service ID name for a given IAM ID
 * `get_service_id_details(service_id_name, service_id)` Return the details of a service ID identified by either name or ID.
 * `create_service_id(service_id_name, with_apikey)` Create a new service ID. When optional parameter with_apikey is set to True there will also be an API krey created and assoctiated with the new service ID
 * `delete_service_id(service_id_name, service_id)` Delete a service ID identified by either name or ID.
### Working with Access Groups
 * `get_access_groups()` Returns a dataframe with all acces groups and their details in the account
 * `get_access_group_id(access_group)` Get the access group ID for an access group name
 * `get_access_group_name(access_group_id)` Get the access group name for an access group ID
 * `get_access_group_members(access_group_name, access_group_id)` Return a dataframe with all members of an access group identified by either name or ID
 * `add_member_to_access_group(access_group_name, access_group_id, user_name, user_id, service_id_name, service_id)` Add a new member (either a user or a Service ID) to an access group identified by either name or ID
 * `delete_member_from_access_groupaccess_group_name, access_group_id, user_name, user_id, service_id_name, service_id)` Remove a member (either a user or a Service ID) from an access group identified by either name or ID
 * `create_access_group(access_group_name)` Create a new access group
 * `delete_access_group(access_group_name, access_group_id, force)` Delete an access group identified by either name or ID. Set force to True to delete the group also when it still has members.

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
