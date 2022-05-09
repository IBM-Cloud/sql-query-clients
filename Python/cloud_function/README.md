# Generic Cloud Function for IBM Cloud Data Engine

This directory contains a simple IBM Cloud Function in Python that calls a custom SQL query in the IBM Cloud Data Engine service using the ibmcloudsql Python package. It prereqs the bx CLI tool and the cloud function plugin.

## Function parameters:
 * `sql` The SQL statement text. Refer to IBM Cloud Data Engine documentation for details and use the IBM Cloud Data Engine web console to author and test your SQL statement interactively.
 * `api_key` - Your IAM API key for your IBM Cloud user or service ID with access to your Data Engine instance and COS bucket
 * `instance_crn` - The instance CRN of your Data Engine instance. Find it in IBM Cloud console dashboard for your instance. Press the `Instance CRN` button there to copy it toyour clipboard
 * `target_url` - Cloud Object Storage URL for the SQL result target. Format: `cos://<endpoint>/<bucket>/[<prefix>]`
 * `client_info` (optional) - Tracking information to identify your client application inside IBM cloud
 * `async` (optional) - When set to true: only submit the SQL statement and don't wait for it to finish. When not provided the default is false.

## 1. Optional: Build and publish SQL cloud function docker image using `build.sh`
This creates a new docker image with all required dependencies and packages and the according client code to invoke the Data Engine API. You only need to do this if you made changes to things in this repository. You will then also need to adapt the `register.sh` script to reference your own pushed docker image. You can use the `invoke.py`script to test your docker image as an action locally before pushing to docker hub and creating a real IBM Cloud Function with it. Here is an [article](https://medium.com/openwhisk/advanced-debugging-of-openwhisk-actions-518414636932) describing the usage of this test script.

## 2. Register the SQL cloud function using `register.sh`
This registers a Cloud Function called `sqlcloudfunction`inside your IBM Cloud org and space.

## 3. Bind using `bind.sh` to your COS and Data Engine instances
This sets the required parameters for API key, instance CRN and COS URL for SQL results. You need to edit the script with your instance data before running it.

## 4. Call the function with a SQL statement using `call.sh`
This calls the function with a simple sample statement passing to the function as a function parameter. You can change the SQL statement text to any other statement that works for you and your data.

*Note*: you can also decide to provide or override the COS and Data Engine instance information at invocation time by passing the parameters there. You can also decide to register the function with a hard coded SQL statement text by providing the `sql` parameter in the bind script.

 * More background on [Python cloud function](https://console.bluemix.net/docs/openwhisk/openwhisk_actions.html#creating-python-actions) creation and handling.
 * [Python environments](https://console.bluemix.net/docs/openwhisk/openwhisk_reference.html#openwhisk_ref_python_environments) for cloud functions
 * IBM Cloud CLI [download](https://console.bluemix.net/docs/cli/reference/bluemix_cli/download_cli.html#download_install)
 * Cloud functions [CLI plug-in](https://console.bluemix.net/docs/openwhisk/bluemix_cli.html#cloudfunctions_cli)
