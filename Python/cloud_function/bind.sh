#!/usr/bin/env bash

# You need to edit this script and replace the placeholders below with
# your instance and API key data.

bx wsk action update sqlcloudfunction \
 --param apikey <your API key here> \
 --param sqlquery_instance_crn <your SQL Query instance CRN here> \
 --param target_url <your ibm cloud object storage URL (cos://<endpoint>/<bucket>/[prefix]) here>
