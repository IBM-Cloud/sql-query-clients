#!/usr/bin/env bash

# You need to edit this script and replace the placeholders below with
# your instance and API key data.

ibmcloud fn action update sqlcloudfunction_as_python \
 --param apikey <your API key here> \
 --param sqlquery_instance_crn <your Data Engine instance CRN here> \
 --param target_url <your ibm cloud object storage URL (cos://<endpoint>/<bucket>/[prefix]) here>
