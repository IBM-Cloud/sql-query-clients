# ------------------------------------------------------------------------------
# Copyright IBM Corp. 2018
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ------------------------------------------------------------------------------

import sys
import urllib
import json
import time
import xml.etree.ElementTree as ET
from tornado.escape import json_decode
from tornado.httpclient import HTTPClient, HTTPError
from tornado.httputil import HTTPHeaders
import sys
import types
import pandas as pd
import numpy as np
from botocore.client import Config
import ibm_boto3
from datetime import datetime


class SQLQuery():
    def __init__(self, api_key, instance_crn, target_cos_url=None, client_info=''):
        self.endpoint_alias_mapping = {
            "us-geo": "s3-api.us-geo.objectstorage.softlayer.net",
            "dal-us-geo": "s3-api.dal-us-geo.objectstorage.softlayer.net",
            "wdc-us-geo": "s3-api.wdc-us-geo.objectstorage.softlayer.net",
            "sjc-us-geo": "s3-api.sjc-us-geo.objectstorage.softlayer.net",
            "eu-geo": "s3.eu-geo.objectstorage.softlayer.net",
            "ams-eu-geo": "s3.ams-eu-geo.objectstorage.softlayer.net",
            "fra-eu-geo": "s3.fra-eu-geo.objectstorage.softlayer.net",
            "mil-eu-geo": "s3.mil-eu-geo.objectstorage.softlayer.net",
            "us-south": "s3.us-south.objectstorage.softlayer.net",
            "us-east": "s3.us-east.objectstorage.softlayer.net",
            "ap-geo": "s3.ap-geo.objectstorage.softlayer.net",
            "tok-ap-geo": "s3.tok-ap-geo.objectstorage.softlayer.net",
            "seo-ap-geo": "s3.seo-ap-geo.objectstorage.softlayer.net",
            "hkg-ap-geo": "s3.hkg-ap-geo.objectstorage.softlayer.net",
            "eu-de": "s3.eu-de.objectstorage.softlayer.net",
            "eu-gb": "s3.eu-gb.objectstorage.softlayer.net",
            "ams": "s3.ams03.objectstorage.softlayer.net",
            "che": "s3.che01.objectstorage.softlayer.net",
            "mel": "s3.mel01.objectstorage.softlayer.net",
            "tor": "s3.tor01.objectstorage.softlayer.net"
        }
        self.api_key = api_key
        self.instance_crn = instance_crn
        self.target_cos = target_cos_url
        if client_info == '':
            self.user_agent = 'IBM Cloud SQL Query Python SDK'
        else:
            self.user_agent = client_info
        self.client = HTTPClient()
        self.request_headers = HTTPHeaders({'Content-Type': 'application/json'})
        self.request_headers.add('Accept', 'application/json')
        self.request_headers.add('User-Agent', self.user_agent)
        self.request_headers_xml_content = HTTPHeaders({'Content-Type': 'application/x-www-form-urlencoded'})
        self.request_headers_xml_content.add('Accept', 'application/json')
        self.request_headers_xml_content.add('User-Agent', self.user_agent)
        self.logged_on = False

    def logon(self):
        if sys.version_info >= (3, 0):
            data = urllib.parse.urlencode({'grant_type': 'urn:ibm:params:oauth:grant-type:apikey', 'apikey': self.api_key})
        else:
            data = urllib.urlencode({'grant_type': 'urn:ibm:params:oauth:grant-type:apikey', 'apikey': self.api_key})

        response = self.client.fetch(
            'https://iam.bluemix.net/identity/token',
            method='POST',
            headers=self.request_headers_xml_content,
            validate_cert=False,
            body=data)

        if response.code == 200:
            # print("Authentication successful")
            bearer_response = json_decode(response.body)
            self.bearer_token = 'Bearer ' + bearer_response['access_token']
            self.request_headers = HTTPHeaders({'Content-Type': 'application/json'})
            self.request_headers.add('Accept', 'application/json')
            self.request_headers.add('User-Agent', self.user_agent)
            self.request_headers.add('authorization', self.bearer_token)
            self.logged_on = True

        else:
            print("Authentication failed with http code {}".format(response.code))

    def submit_sql(self, sql_text):
        if not self.logged_on:
            print("You are not logged on to IBM Cloud")
            return
        sqlData = {'statement': sql_text}
        if self.target_cos:
            sqlData.update({'resultset_target': self.target_cos})

        try:
            response = self.client.fetch(
                "https://sql-api.ng.bluemix.net/v2/sql_jobs?instance_crn={}".format(self.instance_crn),
                method='POST',
                headers=self.request_headers,
                validate_cert=False,
                body=json.dumps(sqlData))
        except HTTPError as e:
            raise SyntaxError("SQL submission failed: {}".format(json_decode(e.response.body)['errors'][0]['message']))

        return json_decode(response.body)['job_id']

    def wait_for_job(self, jobId):
        if not self.logged_on:
            print("You are not logged on to IBM Cloud")
            return "Not logged on"

        while True:
            response = self.client.fetch(
                "https://sql-api.ng.bluemix.net/v2/sql_jobs/{}?instance_crn={}".format(jobId, self.instance_crn),
                method='GET',
                headers=self.request_headers,
                validate_cert=False)

            if response.code == 200 or response.code == 201:
                status_response = json_decode(response.body)
                jobStatus = status_response['status']
                if jobStatus == 'completed':
                    # print("Job {} has completed successfully".format(jobId))
                    resultset_location = status_response['resultset_location']
                    break
                if jobStatus == 'failed':
                    print("Job {} has failed".format(jobId))
                    break
            else:
                print("Job status check failed with http code {}".format(response.code))
                break
            time.sleep(2)
        return jobStatus

    def __iter__(self):
        return 0

    def get_result(self, jobId):
        if not self.logged_on:
            print("You are not logged on to IBM Cloud")
            return

        job_details = self.get_job(jobId)
        job_status = job_details['status']
        if job_status == 'running':
            raise ValueError('SQL job with jobId {} still running. Come back later.')
        elif job_status != 'completed':
            raise ValueError('SQL job with jobId {} did not finish successfully. No result available.')

        result_cos_url = job_details['resultset_location']
        provided_cos_endpoint = result_cos_url.split("/")[2]
        result_cos_endpoint = self.endpoint_alias_mapping.get(provided_cos_endpoint, provided_cos_endpoint)
        result_cos_bucket = result_cos_url.split("/")[3]
        result_cos_prefix = result_cos_url[result_cos_url.replace('/', 'X', 3).find('/')+1:]
        result_location = "https://{}/{}?prefix={}".format(result_cos_endpoint, result_cos_bucket, result_cos_prefix)
        result_format = job_details['resultset_format']

        if result_format != "csv":
            raise ValueError("Result object format {} currently not supported by get_result().".format(result_format))

        response = self.client.fetch(
            result_location,
            method='GET',
            headers=self.request_headers,
            validate_cert=False)

        if response.code == 200 or response.code == 201:
            ns = {'s3': 'http://s3.amazonaws.com/doc/2006-03-01/'}
            responseBodyXMLroot = ET.fromstring(response.body)
            bucket_objects = []
            # Find result objects with data
            for contents in responseBodyXMLroot.findall('s3:Contents', ns):
                key = contents.find('s3:Key', ns)
                if int(contents.find('s3:Size', ns).text) > 0:
                    bucket_objects.append(key.text)
                #print("Job result for {} stored at: {}".format(jobId, result_object))
        else:
            raise ValueError("Result object listing for job {} at {} failed with http code {}".format(jobId, result_location,
                                                                                           response.code))

        cos_client = ibm_boto3.client(service_name='s3',
                                      ibm_api_key_id=self.api_key,
                                      ibm_auth_endpoint="https://iam.ng.bluemix.net/oidc/token",
                                      config=Config(signature_version='oauth'),
                                      endpoint_url='https://' + result_cos_endpoint)

        # Loop over result objects and read and concatenate them into result data frame
        for bucket_object in bucket_objects:
            body = cos_client.get_object(Bucket=result_cos_bucket, Key=bucket_object)['Body']
            # add missing __iter__ method, so pandas accepts body as file-like object
            if not hasattr(body, "__iter__"): body.__iter__ = types.MethodType(self.__iter__, body)

            partition_df = pd.read_csv(body)

            # Add columns from hive style partition naming schema
            hive_partition_candidates = bucket_object.replace(result_cos_prefix + '/', '').split('/')
            for hive_partition_candidate in hive_partition_candidates:
                if hive_partition_candidate.count('=') == 1: # Hive style folder names contain exactly one '='
                    column = hive_partition_candidate.split('=')
                    column_name = column[0]
                    column_value = column[1]
                    if column_value == '__HIVE_DEFAULT_PARTITION__': # Null value partition
                        column_value = np.nan
                    if len(column_name) > 0 and len(column_value) > 0:
                        partition_df[column_name] = column_value

            if 'result_df' not in locals():
                result_df = partition_df
            else:
                result_df = result_df.append(partition_df)

        if 'result_df' not in locals():
            return None

        return result_df

    def list_results(self, jobId):
        if not self.logged_on:
            print("You are not logged on to IBM Cloud")
            return

        job_details = self.get_job(jobId)
        if job_details['status'] == 'running':
            raise ValueError('SQL job with jobId {} still running. Come back later.')
        elif job_details['status'] != 'completed':
            raise ValueError('SQL job with jobId {} did not finish successfully. No result available.')

        result_location = job_details['resultset_location'].replace("cos", "https", 1)
        provided_cos_endpoint = job_details['resultset_location'].split("/")[2]
        result_cos_endpoint = self.endpoint_alias_mapping.get(provided_cos_endpoint, provided_cos_endpoint)

        fourth_slash = result_location.replace('/', 'X', 3).find('/')

        response = self.client.fetch(
            result_location[:fourth_slash] + '?prefix=' + result_location[fourth_slash + 1:],
            method='GET',
            headers=self.request_headers,
            validate_cert=False)

        if response.code == 200 or response.code == 201:
            ns = {'s3': 'http://s3.amazonaws.com/doc/2006-03-01/'}
            responseBodyXMLroot = ET.fromstring(response.body)
            bucket_name = responseBodyXMLroot.find('s3:Name', ns).text
            bucket_objects = []
            if responseBodyXMLroot.findall('s3:Contents', ns):
                for contents in responseBodyXMLroot.findall('s3:Contents', ns):
                    key = contents.find('s3:Key', ns)
                    object_url = "cos://{}/{}/{}".format(result_cos_endpoint, bucket_name, key.text)
                    size = contents.find('s3:Size', ns)
                    bucket_objects.append({'Key': object_url, 'Size': size.text})
            else:
                print('There are no result objects for the jobid {}'.format(jobId))
                return
        else:
            print("Result object listing for job {} at {} failed with http code {}".format(jobId, result_location,
                                                                                           response.code))
            return

        result_objects_df = pd.DataFrame(columns=['ObjectURL', 'Size'])
        for object in bucket_objects:
            result_objects_df = result_objects_df.append([{'ObjectURL': object['Key'], 'Size': object['Size']}], ignore_index=True)

        return result_objects_df

    def delete_result(self, jobId):
        if not self.logged_on:
            print("You are not logged on to IBM Cloud")
            return

        job_details = self.get_job(jobId)
        if job_details['status'] == 'running':
            raise ValueError('SQL job with jobId {} still running. Come back later.')
        elif job_details['status'] != 'completed':
            raise ValueError('SQL job with jobId {} did not finish successfully. No result available.')

        result_location = job_details['resultset_location'].replace("cos", "https", 1)
        provided_cos_endpoint = job_details['resultset_location'].split("/")[2]
        result_cos_endpoint = self.endpoint_alias_mapping.get(provided_cos_endpoint, provided_cos_endpoint)

        fourth_slash = result_location.replace('/', 'X', 3).find('/')

        response = self.client.fetch(
            result_location[:fourth_slash] + '?prefix=' + result_location[fourth_slash + 1:],
            method='GET',
            headers=self.request_headers,
            validate_cert=False)

        if response.code == 200 or response.code == 201:
            ns = {'s3': 'http://s3.amazonaws.com/doc/2006-03-01/'}
            responseBodyXMLroot = ET.fromstring(response.body)
            bucket_name = responseBodyXMLroot.find('s3:Name', ns).text
            bucket_objects = []
            if responseBodyXMLroot.findall('s3:Contents', ns):
                for contents in responseBodyXMLroot.findall('s3:Contents', ns):
                    key = contents.find('s3:Key', ns)
                    bucket_objects.append({'Key': key.text})
            else:
                print('There are no result objects for the jobid {}'.format(jobId))
                return
        else:
            print("Result object listing for job {} at {} failed with http code {}".format(jobId, result_location,
                                                                                           response.code))
            return

        cos_client = ibm_boto3.client(service_name='s3',
                                      ibm_api_key_id=self.api_key,
                                      ibm_auth_endpoint="https://iam.ng.bluemix.net/oidc/token",
                                      config=Config(signature_version='oauth'),
                                      endpoint_url='https://' + result_cos_endpoint)

        response = cos_client.delete_objects(Bucket=bucket_name, Delete={'Objects': bucket_objects})

        deleted_list_df = pd.DataFrame(columns=['Deleted Object'])
        for deleted_object in response['Deleted']:
            deleted_list_df = deleted_list_df.append([{'Deleted Object': deleted_object['Key']}], ignore_index=True)

        return deleted_list_df

    def get_job(self, jobId):
        if not self.logged_on:
            print("You are not logged on to IBM Cloud")
            return

        try:
            response = self.client.fetch(
                "https://sql-api.ng.bluemix.net/v2/sql_jobs/{}?instance_crn={}".format(jobId, self.instance_crn),
                method='GET',
                headers=self.request_headers,
                validate_cert=False)
        except HTTPError as e:
            if e.response.code == 400:
                raise ValueError("SQL jobId {} unknown".format(jobId))
            else:
                raise e

        return json_decode(response.body)

    def get_jobs(self):
        if not self.logged_on:
            print("You are not logged on to IBM Cloud")
            return

        response = self.client.fetch(
            "https://sql-api.ng.bluemix.net/v2/sql_jobs?instance_crn={}".format(self.instance_crn),
            method='GET',
            headers=self.request_headers,
            validate_cert=False)
        if response.code == 200 or response.code == 201:
            job_list = json_decode(response.body)
            job_list_df = pd.DataFrame(columns=['job_id', 'status', 'user_id', 'statement', 'resultset_location',
                                                'submit_time', 'end_time', 'error', 'error_message'])
            for job in job_list['jobs']:
                response = self.client.fetch(
                    "https://sql-api.ng.bluemix.net/v2/sql_jobs/{}?instance_crn={}".format(job['job_id'],
                                                                                                self.instance_crn),
                    method='GET',
                    headers=self.request_headers,
                    validate_cert=False)
                if response.code == 200 or response.code == 201:
                    job_details = json_decode(response.body)
                    error = None
                    if 'error' in job_details:
                        error = job_details['error']
                        end_time = None
                    else:
                        end_time = job_details['end_time']
                    error_message = None
                    if 'error_message' in job_details:
                        error_message = job_details['error_message']
                    job_list_df = job_list_df.append([{'job_id': job['job_id'],
                                                       'status': job_details['status'],
                                                       'user_id': job_details['user_id'],
                                                       'statement': job_details['statement'],
                                                       'resultset_location': job_details['resultset_location'],
                                                       'submit_time': job_details['submit_time'],
                                                       'end_time': end_time,
                                                       'error': error,
                                                       'error_message': error_message,
                                                       }], ignore_index=True)
                else:
                    print("Job details retrieval for jobId {} failed with http code {}".format(job['job_id'],
                                                                                               response.code))
                    break
        else:
            print("Job list retrieval failed with http code {}".format(response.code))
        return job_list_df

    def run_sql(self, sql_text):
        self.logon()
        try:
            jobId = self.submit_sql(sql_text)
        except SyntaxError as e:
            return "SQL job submission failed. {}".format(str(e))
        if self.wait_for_job(jobId) == 'failed':
            details = self.get_job(jobId)
            return "SQL job {} failed while executing with error {}. Detailed message: {}".format(jobId, details['error'],
                                                                                                  details['error_message'])
        else:
            return self.get_result(jobId)

    def sql_ui_link(self):
        if not self.logged_on:
            print("You are not logged on to IBM Cloud")
            return

        if sys.version_info >= (3, 0):
            print ("https://sql.ng.bluemix.net/sqlquery/?instance_crn={}".format(
                urllib.parse.unquote(self.instance_crn)))
        else:
            print ("https://sql.ng.bluemix.net/sqlquery/?instance_crn={}".format(
                urllib.unquote(self.instance_crn).decode('utf8')))

    def get_cos_summary(self, url):
        def sizeof_fmt(num, suffix='B'):
            for unit in ['', 'K', 'M', 'G', 'T', 'P', 'E', 'Z']:
                if abs(num) < 1024.0:
                    return "%3.1f %s%s" % (num, unit, suffix)
                num /= 1024.0
            return "%.1f %s%s" % (num, 'Y', suffix)

        if not self.logged_on:
            print("You are not logged on to IBM Cloud")
            return

        endpoint = url.split("/")[2]
        endpoint = self.endpoint_alias_mapping.get(endpoint, endpoint)
        bucket = url.split("/")[3]
        prefix = url[url.replace('/', 'X', 3).find('/') + 1:]

        cos_client = ibm_boto3.client(service_name='s3',
                                      ibm_api_key_id=self.api_key,
                                      ibm_auth_endpoint="https://iam.ng.bluemix.net/oidc/token",
                                      config=Config(signature_version='oauth'),
                                      endpoint_url='https://' + endpoint)

        paginator = cos_client.get_paginator("list_objects")
        page_iterator = paginator.paginate(Bucket=bucket, Prefix=prefix)

        total_size = 0
        smallest_size = 9999999999999999
        largest_size = 0
        count = 0
        oldest_modification = datetime.max.replace(tzinfo=None)
        newest_modification = datetime.min.replace(tzinfo=None)
        smallest_object = None
        largest_object = None

        for page in page_iterator:
            if "Contents" in page:
                for key in page['Contents']:
                    size = int(key["Size"])
                    total_size += size
                    if size < smallest_size:
                        smallest_size = size
                        smallest_object = key["Key"]
                    if size > largest_size:
                        largest_size = size
                        largest_object = key["Key"]
                    count += 1
                    modified = key['LastModified'].replace(tzinfo=None)
                    if modified < oldest_modification:
                        oldest_modification = modified
                    if modified > newest_modification:
                        newest_modification = modified

        if count == 0:
            smallest_size=None
            oldest_modification=None
            newest_modification=None
        else:
            oldest_modification = oldest_modification.strftime("%B %d, %Y, %HH:%MM:%SS")
            newest_modification = newest_modification.strftime("%B %d, %Y, %HH:%MM:%SS")

        return {'url': url, 'total_objects': count, 'total_volume': sizeof_fmt(total_size),
                'oldest_object_timestamp': oldest_modification,
                'newest_object_timestamp': newest_modification,
                'smallest_object_size': sizeof_fmt(smallest_size), 'smallest_object': smallest_object,
                'largest_object_size': sizeof_fmt(largest_size), 'largest_object': largest_object}
