# `cosaccess` Package for Fine-grained Access Management on COS
The purpose of the `cosaccess` package to provide an easy to use interface to data engineers and data lake adinstrators to set up and manage table level access control for IBM COS based data lakes. It also minimized the required information that you need to have at hand. Basically you just bring your API Key and the COS bucket name for your data lake and you can go from there. The following diagram illustrates the multitudes of SDKs and endpoints that you would normally be required to understand and consume.
<br>



![](cosaccess.png?raw=true)

Following list of SDKs and APIs are being consumed and abstracted by `cosaccess`:
 * [IAM Identity API](https://cloud.ibm.com/apidocs/iam-identity-token-api?code=python#list-service-ids)
 * [IAM Token Service API](https://cloud.ibm.com/docs/account?topic=account-iamtoken_from_apikey)
 * [IAM Policy API](https://cloud.ibm.com/apidocs/iam-policy-management?code=python#list-policies)
 * [IAM Users API](https://cloud.ibm.com/apidocs/user-management?code=python#list-users)
 * [IAM Access Group API](https://cloud.ibm.com/apidocs/iam-access-groups?code=python#introduction)
 * [COS API (ibm_boto3)](https://cloud.ibm.com/docs/cloud-object-storage?topic=cloud-object-storage-python)
 * [COS Resource Configuration API](https://cloud.ibm.com/apidocs/cos/cos-configuration?code=python#getbucketconfig)

## Setup
```
pip install cosaccess
```

Manage IBM Cloud COS access privileges on bucket and object level

## Example usage
```
from cosaccess import CosAccessManager
cosaccess = CosAccessManager('<your api key here>')
cosaccess.get_policies_for_cos_bucket('<your bucket name>')
```

## Demo
Yo can fine a fully reprocible end-to-end demo in the [COS FGAC Demo.ipynb](COS%20FGAC%20Demo.ipynb) notebook here in this repository. An extended variant of the same demo can be found in the [Data Engine FGAC Demo.ipynb](Data%20Engine%20FGAC%20Demo.ipynb) notebook also here in the repository.

You can run these notebooks yourself using Jupyter as follows:

```bash
# Clone the Repository
git clone https://github.com/IBM-Cloud/sql-query-clients.git

# Change directory
cd sql-query-clients/cosaccess

# Set up your virtual environment
source ./setup_env.sh

# Optionally you can set the following environment variables to avoid entering them in the notebook interactively:
export FGACDEMO_APIKEY=<your IBM Cloud API key>
export FGACDEMO_BUCKET=<your COS bucket to use in the demo>
export FGACDEMO_DATAENGINE_INSTANCE=<the instance CRN of your Data Engine standard plan instance>

# Install Jupyter
pip install jupyter

# Run Jupyter
jupyter notebook

```

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
 * `get_cos_instance_crn(bucket)` Returns the instance CRN of the COS instance holding the provided COS bucket
 * `list_cos_endpoints()` Returns a JSON dict with all endpoints for COS supported by IBM Cloud
 * `get_cos_endpoint(cos_bucket)` Returns the endpoint for a bucket
 * `touch_cos_object(cos_bucket, object_path)` Creates an empty object in the specified bucket and with the specified path. Similar to `touch` shell command
 * `delete_cos_object(cos_bucket, object_path)` Delete the object with the specified path from the specified bucket
 * `get_cos_objects(cos_bucket, prefix)` Returns a dataframe with all objects in the specified bucket and prefix
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
 * `get_access_group_members(access_group_name, access_group_id)`  Show all members of the access group identified by either name or ID.
 * `add_member_to_access_group(access_group_name, access_group_id, user_name, user_id, service_id_name, service_id)` Add new member (user or service ID, specified by ither ID or name) to the access group identified by either name or ID.
 * `delete_member_from_access_group(access_group_name, access_group_id, user_name, user_id, service_id_name, service_id)` Remove new member (user or service ID, specified by ither ID or name) from the access group identified by either name or ID.

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
