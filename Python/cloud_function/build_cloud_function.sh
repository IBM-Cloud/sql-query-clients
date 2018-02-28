#!/usr/bin/env bash

# Create a fresh Python virtual environment and activate it:
/usr/local/bin/virtualenv virtualenv
source virtualenv/bin/activate

# Install ibmcloudsql and afterwards remove dependencies that are already
# available in cloud function python-jessie:3 runtime:
pip install --upgrade --force-reinstall ibmcloudsql 
pip uninstall --yes urllib3 simplejson six setuptools python-dateutil pytz pandas numpy jmespath docutils

# Create zip package with cloud function code in __main__.py and with packages in virtualenv:
# (Note: the virtual environment folder has to be literally "virtualenv" so that cloud function
#  can find it.)
rm ibmcloudsql_cloudfunction.zip
zip -r ibmcloudsql_cloudfunction.zip virtualenv __main__.py

# Create/Replace the cloud function
# We set the maximum allowed timeout of 5 minutes:
bx wsk action delete ibmcloudsql_cloudfunction
bx wsk action create ibmcloudsql_cloudfunction --timeout 300000 --kind python-jessie:3 ibmcloudsql_cloudfunction.zip
