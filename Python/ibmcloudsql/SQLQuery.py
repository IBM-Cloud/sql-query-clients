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
import time
import xml.etree.ElementTree as ET
import types
import backoff
import requests
from requests.exceptions import HTTPError
import pandas as pd
import numpy as np
from ibm_botocore.client import Config
import ibm_boto3
from datetime import datetime
import pyarrow
import os
import tempfile
try:
    from exceptions import RateLimitedException
except Exception:
    from .exceptions import RateLimitedException
try:
    from .cos import COSClient
except Exception:
    from cos import COSClient
try:
    from sql_magic import SQLMagic, format_sql, print_sql
except Exception:
    from .sql_magic import SQLMagic, format_sql, print_sql
try:
    from .catalog_table import HiveMetastore
except Exception:
    from catalog_table import HiveMetastore
    
import logging
logger = logging.getLogger(__name__)
from functools import wraps
import json
from json import JSONDecodeError
import getpass
import requests
import dateutil.parser
from pprint import pformat
from collections import namedtuple
import inspect
import sqlparse

from enum import Enum

def check_saved_jobs_decorator(f):
    """a decorator that load data from ProjectLib, check for completed SQL
    Query job, before deciding to launch it"""
    @wraps(f)
    def wrapped(*args, **kwargs):
        self = args[0]
        dictionary = inspect.getcallargs(f, *args, **kwargs)
        prefix = dictionary[
            'prefix']  # Gets you the username, default or modifed
        sql_stmt = dictionary["sql_stmt"]
        # refine query
        sql_stmt = format_sql(sql_stmt)

        run_as_usual = True
        if self.project_lib is not None:
            # handle here
            if self.project_lib.data is None:
                self.read_project_lib_data(file_name=prefix)
                keys_mapping = {}
                # refine existing data
                for key, _ in self.project_lib.data.items():
                    new_key = format_sql(key)
                    if key != new_key:
                        keys_mapping[key] = new_key
                if len(keys_mapping) > 0:
                    rename_keys(self.project_lib.data, keys_mapping)

            if sql_stmt in self.project_lib.data:
                run_as_usual = False
                job_id = self.project_lib.data[sql_stmt]["job_id"]
                if self.project_lib.data[sql_stmt]["status"] == "completed":
                    print("Job {} completed".format(job_id))
                else:
                    # query the status
                    job_result = self.get_job(job_id)
                    self.project_lib.data[sql_stmt]["job_info"] = job_result
                    try:
                        self.project_lib.data[sql_stmt]["status"] = job_result[
                            "status"]
                    except KeyError as e:
                        import pprint
                        pprint.pprint(job_result)
                        raise e
                    if job_result["status"] == "failed":
                        run_as_usual = True

        if run_as_usual:
            job_id = f(*args, **kwargs)
            if self.project_lib is not None:
                self.project_lib.data[sql_stmt] = {
                    "job_id": job_id,
                    "status": "running"
                }
                self.write_project_lib_data()
        return job_id

    return wrapped

    
class SQLQuery(COSClient, SQLMagic, HiveMetastore):
    """The class the provides necessary APIs to interact with

    1. IBM SQL Serverless service
    2. IBM COS service

    Parameters
    ----------
    apikey : str, optional
        an account-level API key [manage/Access (IAM)/IBM Cloud API keys]
    instance_crn :str, optional
        CRN from SQLQuery instance
    target_cos_url : str, optional
        the URI where retrieved data is stored
    max_concurrent_jobs: int, optional
        the max number of concurrent jobs
    client_info : str, optional
        User-defined string
    """
    def __init__(self, api_key, instance_crn, target_cos_url=None, client_info='', 
                max_concurrent_jobs=4,
                max_tries=1):
        COSClient.__init__(self,
                           cloud_apikey=api_key,
                           cos_url=target_cos_url,
                           client_info=client_info)
        SQLMagic.__init__(self)
        HiveMetastore.__init__(self, target_cos_url)

        self.instance_crn = instance_crn
        self.target_cos_url = target_cos_url
        self.export_cos_url = target_cos_url
        if client_info == '':
            self.user_agent = 'IBM Cloud SQL Query Python SDK'
        else: 
            self.user_agent = client_info

        self.max_tries = max_tries
        self.max_concurrent_jobs = max_concurrent_jobs  # the current maximum concurrent jobs

        # track the status of jobs - save the time to SQLQuery server
        self.jobs_tracking = {}
        
        logger.debug("SQLClient created successful")

    def configure(self, cloud_apikey, sqlquery_instance_crn, target_cos_url):
        """ use this to update the configuration
        """
        self.apikey = getpass.getpass(
            'Enter IBM Cloud API Key (leave empty to use previous one): '
        ) or self.apikey
        self.instance_crn = input(
            'Enter SQL Query Instance CRN (leave empty to use previous one): '
        ) or self.instance_crn
        if self.target_cos_url == '':
            self.target_cos_url = input('Enter target URI for SQL results: ')
        else:
            self.target_cos_url = input(
                'Enter target URI for SQL results (leave empty to use ' +
                self.target_cos_url + '): ') or self.target_cos_url
        HiveMetastore.target_url(self, self.target_cos_url)

    @property
    def my_jobs(self):
        """
        Return information about jobs already queried via `get_job()`
        issued by this SQLClient class object

        This is different from :py:meth:`get_jobs()`

        Returns
        -------
        dict

        """
        return self.jobs_tracking

    def _send_req(self, json_data):
        '''send SQL data to API. return job id'''

        try:
            response = requests.post(
                "https://api.sql-query.cloud.ibm.com/v2/sql_jobs?instance_crn={}".format(self.instance_crn),
                headers=self.request_headers,
                json=json_data)

            # Throw in case we hit the rate limit
            if (response.status_code == 429):
                raise RateLimitedException("SQL submission failed: {}".format(response.json()['errors'][0]['message']))

            # any other error but 429 will be raised here, like 403 etc
            response.raise_for_status()

            resp = response.json()
            return resp['job_id']
        except KeyError as e:
            raise SyntaxError("SQL submission failed: {}".format(response.json()['errors'][0]['message']))

        except HTTPError as e:
            raise SyntaxError("SQL submission failed: {}".format(response.json()['errors'][0]['message']))

    def submit_sql(self, sql_text, pagesize=None):
        self.logon()
        sqlData = {'statement': sql_text}
        # If a valid pagesize is specified we need to append the proper PARTITIONED EVERY <num> ROWS clause
        if pagesize or pagesize==0:
            if type(pagesize) == int and pagesize>0:
                if self.target_cos_url:
                    sqlData["statement"] += " INTO {}".format(self.target_cos_url)
                elif " INTO "  not in sql_text.upper():
                    raise SyntaxError("Neither resultset_target parameter nor \"INTO\" clause specified.")
                elif " PARTITIONED " in sql_text.upper():
                    raise SyntaxError("Must not use PARTITIONED clause when specifying pagesize parameter.")
                sqlData["statement"] += " PARTITIONED EVERY {} ROWS".format(pagesize)
            else:
                raise ValueError('pagesize parameter ({}) is not valid.'.format(pagesize))
        elif self.target_cos_url:
            sqlData.update({'resultset_target': self.target_cos_url})

        intrumented_send = backoff.on_exception(
            backoff.expo,
            RateLimitedException,
            max_tries=self.max_tries
        )(self._send_req)

        return intrumented_send(sqlData)

    def submit(self,
                   pagesize=None,
                   blocking=True):
        """ run the internal SQL statement that you created using the APIs provided by SQLMagic
        """
        self.format_()
        return self.submit_sql2(self._sql_stmt,
            pagesize=pagesize,
            blocking=blocking)

    def submit_sql2(self,
                   sql_stmt,
                   pagesize=None,
                   blocking=True):
        """
        Asynchronous call - submit and quickly return the job_id.

        Parameters
        ----------
        sql_stmt: str
            SQL Query string
        pagesize: int, optional
            an integer indicating the number of rows for each partition/page
            [using PARTITIONED EVERY <pagesize> ROWS syntax]
        blocking : bool, optional (default=True)
            If True, wait until the queue is available

            Default, wait. Otherwise, return if the queue is not available

        Returns
        -------
        str
            job_id

        Raises
        ------
        RateLimitedException
            when the SQLQUery instance is serving the max-limit of requests

        SyntaxError
            for both KeyError or HTTPError

        Example
        -------

        .. code-block:: console

            curl -XPOST \
                --url "https://api.sql-query.cloud.ibm.com/v2/sql_jobs?instance_crn=YOUR_SQL_QUERY_CRN" \
                -H "Accept: application/json" \
                -H "Authorization: Bearer YOUR_BEARER_TOKEN" \
                -H "Content-Type: application/json" \
                -d '{"statement":"SELECT firstname FROM cos://us-geo/sql/employees.parquet STORED AS PARQUET WHERE EMPLOYEEID=5 INTO cos://us-geo/target-bucket/q1-results" }'

        NOTE:

        1. All the headers (-H) can be put into a dictionary and
        passed to the *headers* argument of requests.post() API.

        2. All the data (-d option) is put into a dictionary and
        passed to the *json* argument of requests.post() API.

            * 'statement': value is full SQL statement in string
            * 'resultset_target' (optional): only need when there is no 'INTO statement' in the query string, and the value must be the COS URL output

        .. code-block:: python

            sqlData = {'statement': sql_stmt}
            request_headers = {'Content-Type': 'application/json'}
            request_headers.update({'Accept':'application/json'})
            request_headers.update({'User-Agent': self.user_agent})
            request_headers.update({'authorization': 'Bearer {}'.format(ro_credentials.token)})
            response = requests.post(
                "https://api.sql-query.cloud.ibm.com/v2/sql_jobs?instance_crn={}".format(self.instance_crn),
                headers=request_headers,
                json=sqlData)
            \"\"\"
            {
                "errors": [
                    {
                    "code": "bad_request",
                    "message": "Target url specified in parameter resultset_target and as part of into clause in statement"
                    }
                ]
            }
            {
                "job_id": "e2adca0a-9247-4cfa-ac58-db4b2bc33a01",
                "status": "queued"
            }
            {
                "status_code": 429,
                "errors": [
                    {
                    "code": "too_many_requests",
                    "message": "This instance is currently running its maximum number of query jobs. Try again later, after at least one of the currently running jobs has completed."
                    }
                ]
            }
            \"\"\"
            # error code information: https://cloud.ibm.com/apidocs/sql-query


        """
        self.sqlClient.logon()
        self.request_headers["authorization"] = self.sqlClient.request_headers[
            "authorization"]
        sql_text = sql_stmt
        sqlData = {'statement': sql_text}

        def INTO_present(sql_text):
            """ check if INTO keyword is present in the SQL query"""
            return (" INTO " in sql_text.upper()) or (
                "\nINTO " in sql_text.upper())

        # If a valid pagesize is specified we need to append the proper PARTITIONED EVERY <num> ROWS clause
        if pagesize or pagesize == 0:
            if type(pagesize) == int and pagesize > 0:
                if self.cos_out_url and not INTO_present(sql_text):
                    sqlData["statement"] += " INTO {}".format(self.cos_out_url)
                elif not INTO_present(sql_text):
                    raise SyntaxError(
                        "Neither resultset_target parameter nor \"INTO\" clause specified."
                    )
                elif " PARTITIONED " in sql_text.upper():
                    raise SyntaxError(
                        "Must not use PARTITIONED clause when specifying pagesize parameter."
                    )
                sqlData["statement"] += " PARTITIONED EVERY {} ROWS".format(
                    pagesize)
            else:
                raise ValueError(
                    'pagesize parameter ({}) is not valid.'.format(pagesize))
        elif self.cos_out_url and not INTO_present(sql_text):
            sqlData.update({'resultset_target': self.cos_out_url})

        def issue_request():
            response = requests.post(
                "https://api.sql-query.cloud.ibm.com/v2/sql_jobs?instance_crn={}"
                .format(self.sqlquery_instance_crn),
                headers=self.request_headers,
                json=sqlData)
            return response

        is_done = False
        while is_done is False:
            try:
                response = issue_request()
                resp = response.json()
                status_code = 0
                is_done = True
                if "status_code" in resp:
                    status_code = resp["status_code"]
                    if resp["status_code"] == 429:
                        if blocking is True:
                            is_done = False
                            while True:
                                if (self.get_number_running_jobs() <
                                        self.max_concurrent_jobs):
                                    break
                                time.sleep(10)  # seconds
                        else:
                            raise RateLimitedException(
                                "SQL submission failed ({code}): {msg}".format(
                                    code=status_code,
                                    msg=response.json()['errors'][0]
                                    ['message']))
                if (blocking is False) or ('job_id' in resp):
                    logger.debug(pformat(resp))
                    return resp['job_id']
            except (KeyError, HTTPError) as _:
                raise SyntaxError(
                    "SQL submission failed ({code}): {msg} - {query}".format(
                        code=status_code,
                        msg=response.json()['errors'][0]['message'],
                        query=pformat(sqlData)))
        if "job_id" not in resp:
            raise SyntaxError(
                "SQL submission failed ({code}): {msg} - {query}".format(
                    code=status_code,
                    msg=response.json()['errors'][0]['message'],
                    query=pformat(sqlData)))

    @check_saved_jobs_decorator
    def submit_sql_with_checking_saved_jobs(self,
                                            sql_stmt,
                                            pagesize=None,
                                            prefix=None,
                                            blocking=True):
        """
        Do the checking if a previous job is completed. The comparison is based on the SQL query content.
        The content of previous queries are stored in a file,
        with name given by `prefix` argument, stored as an asset in the Project-Lib.
        This is used in the scenario when you launch many many jobs, and don't want to restart from the
        beginning.

        Parameters
        ----------
        prefix : str, optional
            If it is used, it will looks into the ProjectLib for an asset file name $prefix.json
            and compare the full sql statement if it has been used
            If yes, and the result is successful, there is no need to rerun it

        Note
        ----
            This depends on the usage of :py:meth:`COSClient.connect_project_lib`,
            :py:meth:`COSClient.read_project_lib_data`

        """
        return self.submit_sql(
            sql_stmt,
            pagesize=pagesize,
            blocking=blocking)

    def wait_for_job(self, jobId):
        """
        It's possible that the job's failed because of Spark's internal error.
        So "unknown" is added for such cases. 

        Return
        -------
            'failed', 'completed', or 'unknown'
        """
        def wait_for_job(jobId): 
            self.logon()

            while True:
                response = requests.get(
                    "https://api.sql-query.cloud.ibm.com/v2/sql_jobs/{}?instance_crn={}".format(jobId, self.instance_crn),
                    headers=self.request_headers,
                )

                if response.status_code == 200 or response.status_code == 201:
                    status_response = response.json()
                    jobStatus = status_response['status']
                    if jobStatus == 'completed':
                        break
                    if jobStatus == 'failed':
                        print("Job {} has failed".format(jobId))
                        break
                else:
                    print("Job status check failed with http code {}".format(response.status_code))
                    break
                time.sleep(2)
            return jobStatus

        job_id = jobId
        try:
            x = wait_for_job(job_id)
        except UnboundLocalError as _:
            x = "unknown"
        return x

    def __iter__(self):
        return 0

    def get_result(self, jobId, pagenumber=None):
        """
        Parameters
        ----------
        jobId: int
            The value, if not stored, can be retrieved from self.get_jobs()
        pagenumber: int, optional
            If the data, from the given `job_id` is saved in pages/partitions, then this should be a value
            in the range from 1 to len(self.list_results(job_id))

        Returns
        -------
        dataframe
            The dataframe holding the queried data from a completed job


        .. code-block:: console

            curl -XGET \
                --url "https://api.sql-query.cloud.ibm.com/v2/sql_jobs?instance_crn=<YOUR_SQL_QUERY_CRN>" \
                -H "Accept: application/json" \
                -H "Authorization: Bearer <YOUR_BEARER_TOKEN>"  \
                -H "Content-Type: application/json"

            \"\"\"
            {
            "jobs": [
                {
                "job_id": "7ebed7f7-00dc-44a2-acfa-5bdb53889648",
                "status": "completed",
                "submit_time": "2018-08-14T08:45:54.012Z",
                "user_id": "user1@ibm.com"
                },
                {
                "job_id": "ffde4c5a-1cc2-448b-b377-43573818e5d8",
                "status": "completed",
                "submit_time": "2018-08-14T08:47:33.350Z",
                "user_id": "user1@ibm.com"
                }
            ]
            }
            \"\"\"

        .. code-block:: python

            response = requests.get(
                "https://api.sql-query.cloud.ibm.com/v2/sql_jobs/{}?instance_crn={}".format(jobId, self.instance_crn),
                headers=self.request_headers,
            )

            if response.status_code == 200 or response.status_code == 201:
                status_response = response.json()

            https://cloud.ibm.com/apidocs/sql-query#run-an-sql-job
        """
        self.logon()

        job_details = self.get_job(jobId)
        job_status = job_details.get('status')
        if job_status == 'running':
            raise ValueError('SQL job with jobId {} still running. Come back later.'.format(jobId))
        elif job_status != 'completed':
            raise ValueError('SQL job with jobId {} did not finish successfully. No result available.'.format(jobId))

        if "resultset_location" not in job_details:
            return None

        url_parsed = self.analyze_cos_url(job_details['resultset_location'])
        result_location = "https://{}/{}?prefix={}".format(url_parsed.endpoint, url_parsed.bucket, url_parsed.prefix)
        result_format = job_details['resultset_format']

        if result_format not in ["csv", "parquet", "json"]:
            raise ValueError("Result object format {} currently not supported by get_result().".format(result_format))

        response = requests.get(
            result_location,
            headers=self.request_headers,
        )

        if response.status_code == 200 or response.status_code == 201:
            ns = {'s3': 'http://s3.amazonaws.com/doc/2006-03-01/'}
            responseBodyXMLroot = ET.fromstring(response.text)
            bucket_objects = []
            # Find result objects with data
            for contents in responseBodyXMLroot.findall('s3:Contents', ns):
                key = contents.find('s3:Key', ns)
                if int(contents.find('s3:Size', ns).text) > 0:
                    bucket_objects.append(key.text)
                #print("Job result for {} stored at: {}".format(jobId, result_object))
        else:
            raise ValueError("Result object listing for job {} at {} failed with http code {}".format(jobId, result_location,
                                                                                           response.status_code))

        cos_client = self._get_cos_client(url_parsed.endpoint)

        # When pagenumber is specified we only retrieve that page. Otherwise we concatenate all pages to one DF:
        if pagenumber or pagenumber==0:
            if " PARTITIONED EVERY " not in job_details['statement'].upper():
                raise ValueError("pagenumber ({}) specified, but the job was not submitted with pagination option.".format(pagenumber))
            if type(pagenumber) == int and 0 < pagenumber <= len(bucket_objects):
                if result_format == "csv":
                    body = cos_client.get_object(Bucket=url_parsed.bucket, Key=bucket_objects[pagenumber-1])['Body']
                    if not hasattr(body, "__iter__"): body.__iter__ = types.MethodType(self.__iter__, body)
                    result_df = pd.read_csv(body)
                elif result_format == "parquet":
                    tmpfile = tempfile.NamedTemporaryFile()
                    tempfilename = tmpfile.name
                    tmpfile.close()
                    cos_client.download_file(Bucket=url_parsed.bucket, Key=bucket_objects[pagenumber-1], Filename=tempfilename)
                    result_df = pd.read_parquet(tempfilename)
                elif result_format == "json":
                    body = cos_client.get_object(Bucket=url_parsed.bucket, Key=bucket_objects[pagenumber-1])['Body']
                    body = body.read().decode('utf-8')
                    result_df = pd.read_json(body,lines=True)

            else:
                raise ValueError("Invalid pagenumner ({}) specified".format(pagenumber))
        else:
            # Loop over result objects and read and concatenate them into result data frame
            for bucket_object in bucket_objects:

                if result_format == "csv":
                    body = cos_client.get_object(Bucket=url_parsed.bucket, Key=bucket_object)['Body']
                    # add missing __iter__ method, so pandas accepts body as file-like object
                    if not hasattr(body, "__iter__"): body.__iter__ = types.MethodType(self.__iter__, body)

                    partition_df = pd.read_csv(body)

                elif result_format == "parquet":
                    tmpfile = tempfile.NamedTemporaryFile()
                    tempfilename = tmpfile.name
                    tmpfile.close()
                    cos_client.download_file(Bucket=url_parsed.bucket, Key=bucket_object, Filename=tempfilename)

                    partition_df = pd.read_parquet(tempfilename)

                elif result_format == "json":
                    body = cos_client.get_object(Bucket=url_parsed.bucket, Key=bucket_object)['Body']
                    body = body.read().decode('utf-8')

                    partition_df = pd.read_json(body, lines=True)

                # Add columns from hive style partition naming schema
                hive_partition_candidates = bucket_object.replace(url_parsed.prefix + '/', '').split('/')
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
                    result_df = result_df.append(partition_df, sort=False)

            if 'result_df' not in locals():
                return None

        return result_df

    def list_results(self, jobId, blocking=True):
        """
        NOTE: A single SQL Query can store the queried data in the COS output
        in multiple objects/partitions

        When one of those below is used

        .. code-block:: console

            [ PARTITIONED BY,
            PARTITIONED EVERY x ROWS      [implicitly used with pagesize=X option]
            ]

        Parameters
        ------------
        job_id: str
            The Job ID
        blocking: bool, default: True
            If True, wait for the available slot in the work queue

        Returns
        -------
            None (or nothing) if the function fails

            DataFrame (4 fields: ObjectURL, Size, Bucket, Object) - each row correspond to the information of one partition

        Raises
        ----------
            ValueError

        Notes
        -------
            To know the number of partitions being used, use 'len(self.list_results(job_id))'
        """
        def list_results(jobId):
            self.logon()

            job_details = self.get_job(jobId)
            if job_details['status'] == 'running':
                raise ValueError('SQL job with jobId {} still running. Come back later.')
            elif job_details['status'] != 'completed':
                raise ValueError('SQL job with jobId {} did not finish successfully. No result available.')

            if "resultset_location" not in job_details:
                return None
            result_location = job_details['resultset_location']
            url_parsed = self.analyze_cos_url(result_location)
            result_bucket = url_parsed.bucket
            result_endpoint = url_parsed.endpoint
            result_objects_df =  self.list_cos_objects(job_details['resultset_location'])
            result_objects_df['Bucket'] = result_bucket
            result_objects_df['ObjectURL'] = result_objects_df.apply(lambda x: 'cos://%s/%s/%s' % (result_endpoint, result_bucket, x['Object']), axis=1)
            return result_objects_df

        if blocking:
            job_running = True
            while job_running:
                try:
                    x = list_results(job_id)
                    job_running = False
                except ValueError as e:
                    if "running" in str(e):
                        pass
                    else:
                        raise e
        else:
            x = list_results(job_id)
        return x

    def rename_exact_result(self, job_id, blocking=True):
        """
        A SQL Query can store data into partitioned/paginated multiple objects, or single object.

        Even with single object, indeed, multiple objects are created, two of them has size 0.
        (<URL>/_SUCCESS, and <URL>/) beside the one that holds data (<URL>/)

        This API delete the two 0-size objects, and keep only the one that holds data.

        Parameters
        ----------
        job_id : str
            A string representation of job_id

        blocking: bool, optional
            Default is wait
        
        Returns
        --------
        None 

        Raises
        ------
        ValueError
            If the job_id is the job in that the result is "PARTITIONED BY" or "pagesize=" or "PARITIONED EVERY x ROWS" is used
            or the rename_exact_result() has been applied to this job_id.
        """
        self.logon()

        job_details = self.get_job(jobId)
        job_status = job_details.get('status')

        while job_status == "running" and blocking is True:
            time.sleep(6)
            job_details = self.get_job(job_id)
            job_status = job_details.get('status')

        if job_status == 'running':
            raise ValueError('SQL job with jobId {} still running. Come back later.'.format(jobId))
        elif job_status != 'completed':
            raise ValueError('SQL job with jobId {} did not finish successfully. No result available.'.format(jobId))

        if "resultset_location" not in job_details or job_details[
                "resultset_location"] is None:
            return None
        url_parsed = self.analyze_cos_url(job_details['resultset_location'])
        cos_client = self._get_cos_client(url_parsed.endpoint)

        result_objects = self.list_results(jobId)

        if len(result_objects) > 3:
            raise ValueError('Renaming partitioned results of jobId {} to single exact result object name not supported.'.format(jobId))
        if len(result_objects) == 3 and (int(result_objects.Size[0]) != 0
                                         or int(result_objects.Size[1]) != 0):
            raise ValueError(
                'Results of job_id {} don\'t seem to be regular SQL query output.'
                .format(job_id))

        if len(result_objects) == 1:
            return 
        # HANDLING  [can be 2 rows or 3 rows] - only the last row can be non-zero in size
        max_row_index = len(result_objects) - 1
        pre_row_zeros = True
        for row in range(0, max_row_index):
            if int(result_objects.Size[row]) > 0:
                pre_row_zeros = False
                break

        if pre_row_zeros is False:
            raise ValueError(
                'Results of job_id {} don\'t seem to be regular SQL query output.'
                .format(job_id))

        if len(result_objects) == 3:
            # basically copy the object[2] to object[0]
            # then delete object[2] and object[1]
            copy_source = result_objects.Bucket[2] + "/" + result_objects.Object[2]
            cos_client.copy_object(Bucket=result_objects.Bucket[0], CopySource=copy_source, Key=result_objects.Object[0])
            cos_client.delete_object(Bucket=result_objects.Bucket[2], Key=result_objects.Object[2])
            cos_client.delete_object(Bucket=result_objects.Bucket[1], Key=result_objects.Object[1])
        else:  # len(result_objects) == 2
            cos_client.delete_object(Bucket=result_objects.Bucket[0],
                                     Key=result_objects.Object[0])

        return

    def rename_exact_result_joblist(self,
                                    job_list,
                                    blocking=True):
        """ The bulk mode of `rename_exact_result` method.

        Parameters
        ----------
        job_list: list
            A list of job_id

        """
        for job_id in job_list:
            self.rename_exact_result(job_id, blocking=blocking)

    def delete_result(self, jobId):
        """
        Returns
        ------
        dataframe
            A dataframe, with 3 rows, and one field name "Deleted Object"

        Examples
        --------
        Delete 3 entries in the output COS

        .. code-block:: console

            cos://<cos-name>/bucket_name/jobid=<JOB-ID-NUMBER>/
            cos://<cos-name>/bucket_name/jobid=<JOB-ID-NUMBER>/_SUCCESS
            cos://<cos-name>/bucket_name/jobid=<JOB-ID-NUMBER>/[parquet|csv|json]

        Note
        ----

        * The last entry holds the real data, and the last word also indicates the data format
        * 'JOBPREFIX NONE'  would avoid having 'jobid=JOB-ID-NAME' in the URL

        """
        self.logon()

        job_details = self.get_job(jobId)
        if job_details['status'] == 'running':
            raise ValueError('SQL job with jobId {} still running. Come back later.')
        elif job_details['status'] != 'completed':
            raise ValueError('SQL job with jobId {} did not finish successfully. No result available.')

        if "resultset_location" not in job_details:
            return None
        result_location = job_details['resultset_location'].replace("cos", "https", 1)
        url_parsed = self.analyze_cos_url(result_location)
        bucket_name = url_parsed.bucket
        bucket_objects_df = self.list_cos_objects(result_location)[['Object']]
        if bucket_objects_df.empty:
            print('There are no result objects for the jobid {}'.format(jobId))
            return
        bucket_objects_df = bucket_objects_df.rename(columns={"Object": "Key"})
        bucket_objects = bucket_objects_df.to_dict('records')

        cos_client = self._get_cos_client(url_parsed.endpoint)

        response = cos_client.delete_objects(Bucket=bucket_name, Delete={'Objects': bucket_objects})

        deleted_list_df = pd.DataFrame(columns=['Deleted Object'])
        for deleted_object in response['Deleted']:
            deleted_list_df = deleted_list_df.append([{'Deleted Object': deleted_object['Key']}], ignore_index=True, sort=False)

        return deleted_list_df

    def get_job(self, jobId):
        """
        Returns
        -------
        dict
            a dict of job details (see keys below)

        Note
        ----

        .. code-block:: python

            'job_id',
            'status', : "running", "failed", "completed"
            'statement': "SELECT * ..." [the content of SQL Query],
            'plan_id' ,
            'submit_time',
            'resultset_location',
            'rows_returned',
            'rows_read' ,
            'bytes_read' ,
            'resultset_format': 'csv',
            'end_time': '2020-03-06T21:58:26.274Z',
            'user_id': 'username@us.ibm.com'

        Example
        --------

        .. code-block:: python

            {
                "bytes_read": 43058,
                "end_time": "2020-03-08T03:20:39.131Z",
                "job_id": "ab3f7567-280b-40c9-87a9-256b846f89db",
                "plan_id": "ead0f7f5-0c96-40c0-9aae-63c4846d8188",
                "resultset_format": "parquet",
                "resultset_location": "cos://s3.us-south.cloud-object-storage.appdomain.cloud/tuan-sql-result/customer_orders/jobid=ab3f7567-280b-40c9-87a9-256b846f89db",
                "rows_read": 921,
                "rows_returned": 830,
                "statement": "SELECT OrderID, c.CustomerID CustomerID, CompanyName, ContactName, ContactTitle, Address, City, Region, PostalCode, Country, Phone, Fax          EmployeeID, OrderDate, RequiredDate, ShippedDate, ShipVia, Freight, ShipName, ShipAddress,          ShipCity, ShipRegion, ShipPostalCode, ShipCountry FROM cos://us-geo/sql/orders.parquet STORED AS PARQUET o,          cos://us-geo/sql/customers.parquet STORED AS PARQUET c          WHERE c.CustomerID = o.CustomerID          INTO cos://us-south/tuan-sql-result/customer_orders STORED AS PARQUET PARTITIONED BY (ShipCountry, ShipCity)",
                "status": "completed",
                "submit_time": "2020-03-08T03:20:00.617Z",
                "user_id": "tmhoangt@us.ibm.com"
            }

        """
        def get_job(jobId):
            self.logon()

            try:
                response = requests.get(
                    "https://api.sql-query.cloud.ibm.com/v2/sql_jobs/{}?instance_crn={}".format(jobId, self.instance_crn),
                    headers=self.request_headers,
                )
            except HTTPError as e:
                if e.response.status_code == 400:
                    raise ValueError("SQL jobId {} unknown".format(jobId))
                else:
                    raise e

            return response.json()

        job_id = jobId
        if job_id in self.jobs_tracking and \
            self.jobs_tracking[job_id].get("status") != "running":
            result = self.jobs_tracking[job_id]
        else:
            try:
                result = get_job(job_id)
            except JSONDecodeError as e:
                print("Error at querying job {}".format(job_id))
                raise e
            self.jobs_tracking[job_id] = result
        return result

    def get_jobs(self):
        """
        Return the up-to-30 most recent jobs from the given Cloud API

        Returns
        -------
        dataframe
            a pd.DataFrame with fields - total 30 rows, corresponding to the 30 most recent jobs

        Example
        -------
        .. code-block:: console

            job_id
            status: "running", "failed", "completed"
            user_id
            statement
            resultset_location
            submit_time
            end_time
            rows_read
            rows_returned
            bytes_read
            error
            error_message

        .. code-block:: console

            job_id	status	user_id	statement	resultset_location	submit_time	end_time	rows_read	rows_returned	bytes_read	error	error_message
            8d9c5a97-808f-4a08-9cc3-78e3f07f7ba8	completed	tmhoangt@us.ibm.com	SELECT o.OrderID, c.CompanyName, e.FirstName, e.LastName FROM cos://us-geo/sql/orders.parquet STORED AS PARQUET o, cos://us-geo/sql/employees.parquet STORED AS PARQUET e, cos://us-geo/sql/customers.parquet STORED AS PARQUET c WHERE e.EmployeeID = o.EmployeeID AND c.CustomerID = o.CustomerID AND o.ShippedDate > o.RequiredDate AND o.OrderDate > "1998-01-01" ORDER BY c.CompanyName	cos://s3.us-south.cloud-object-storage.appdomain.cloud/tuan-sql-result/jobid=8d9c5a97-808f-4a08-9cc3-78e3f07f7ba8	2020-02-21T16:19:03.638Z	2020-02-21T16:19:13.691Z	1760	29	41499	None	None

        Note
        ----

        * get_jobs() is used by export_job_history(cos_out_url) which is used to save such data
        """
        self.logon()

        response = requests.get(
            "https://api.sql-query.cloud.ibm.com/v2/sql_jobs?instance_crn={}".format(self.instance_crn),
            headers=self.request_headers,
            )
        if response.status_code == 200 or response.status_code == 201:
            job_list = response.json()
            job_list_df = pd.DataFrame(columns=['job_id', 'status', 'user_id', 'statement', 'resultset_location',
                                                'submit_time', 'end_time', 'rows_read', 'rows_returned', 'bytes_read',
                                                'error', 'error_message'])
            for job in job_list['jobs']:
                response = requests.get(
                    "https://api.sql-query.cloud.ibm.com/v2/sql_jobs/{}?instance_crn={}".format(job['job_id'],
                                                                                                self.instance_crn),
                    headers=self.request_headers,
                    )
                if response.status_code == 200 or response.status_code == 201:
                    job_details = response.json()
                    # None gets converted to integer type in pandas.to_parquet
                    error = ""
                    error_message = ""
                    rows_read = None
                    rows_returned = None
                    bytes_read = None
                    end_time = ""
                    if 'error' in job_details:
                        error = job_details['error']
                    if 'end_time' in job_details:
                        end_time = job_details['end_time']
                    if 'error_message' in job_details:
                        error_message = job_details['error_message']
                    if 'rows_read' in job_details:
                        rows_read = job_details['rows_read']
                    if 'rows_returned' in job_details:
                        rows_returned = job_details['rows_returned']
                    if 'bytes_read' in job_details:
                        bytes_read = job_details['bytes_read']
                    resultset_loc = np.NaN
                    if 'resultset_location' in job_details:
                        resultset_loc = job_details['resultset_location']
                    job_list_df = job_list_df.append([{'job_id': job['job_id'],
                                                       'status': job_details['status'],
                                                       'user_id': job_details['user_id'],
                                                       'statement': job_details['statement'],
                                                       'resultset_location': resultset_loc,
                                                       'submit_time': job_details['submit_time'],
                                                       'end_time': end_time,
                                                       'rows_read': rows_read,
                                                       'rows_returned': rows_returned,
                                                       'bytes_read': bytes_read,
                                                       'error': error,
                                                       'error_message': error_message,
                                                       }], ignore_index=True, sort=False)
                else:
                    print("Job details retrieval for jobId {} failed with http code {}".format(job['job_id'],
                                                                                               response.status_code))
                    break
        else:
            print("Job list retrieval failed with http code {}".format(response.status_code))
        return job_list_df

    def get_jobs_matching(self, job_id_list, status="completed"):
        """ return the list of job_id that have the given status

        Parameters
        ----------
        job_id_list: list
            List of job_id
        status : str, optional
            "completed", or "failed"
        """
        results = []
        for job_id in job_id_list:
            response = self.get_job(job_id)
            if response["status"] == status:
                results.append(job_id)
        return results

    def get_jobs_count_with_status(self, status):
        """ return the number of jobs in the SQL Query server for the given `status`"""
        jobs = self.get_jobs()
        num_jobs = len(jobs[jobs["status"] == status])
        return num_jobs

    def get_number_running_jobs(self):
        """ return the number of running jobs in the SQL Query server"""
        return self.get_jobs_count_with_status('running')

    def run_sql2(self,
                sql_stmt,
                pagesize=None,
                get_result=False,
                blocking=True):
        """
        Extend the behavior of self.run_sql(). 

        1. returns a namedtuple, in that result.data is the one returned by `run_sql`, while result.job_id is the extra part.
        2. ensure the job is successfully put into the queue
        3. synchronous call but has the option to NOT return the data - avoid memory overload

        Parameters
        --------------
        pagesize: int, optional
            an integer indicating the number of rows for each partition/page [using PARTITIONED EVERY <pagesize> ROWS syntax]

        get_result: bool, optional (default=False)
            add the capability to return only the job_id, but wait for the job's completion. Later, we can get the data using :meth:`.get_result` (job_id, pagenumber)

        blocking: bool, optional (default=True)
            If True, wait until the queue is available

        Returns
        -------
        namedtuple [`data`, `job_id`]
            `get_result` = True, then behavior like `ibmcloudsql.run_sql`() which load returned data into memory.
            The default behavior is opposite, to avoid unnecessarily overload the memory.

        Note
        -----

        The query can return data or not. If it is supposed to return data then

        * data can be of type: str (the error messsage, if failed) or pd.DataFrame (the real data, if succeed) - use `isinstance(data, str)` to check

        """
        Container = namedtuple('RunSql', ['data', 'job_id'])

        job_id = self.submit_sql(
            sql_stmt,
            pagesize=pagesize,
            blocking=blocking)
        data = None
        job_status = self.wait_for_job(job_id)
        logger.debug("Job " + job_id + " terminated with status: " +
                     job_status)
        if job_status == 'completed':
            if get_result is True:
                data = self.get_result(job_id)
        elif job_status == "unknown":
            job_status = self.wait_for_job(job_id)

        if job_status == "failed":
            details = self.get_job(job_id)
            try:
                data = "{status}: SQL job {job_id} failed while executing with error {error}. Detailed message: {msg}".format(
                    status=job_status,
                    job_id=job_id,
                    error=details['error'],
                    msg=details['error_message'])
            except KeyError as e:
                pprint.pprint(details)
                raise e
        mycontainer = Container(data, job_id)
        return mycontainer

    def run_sql(self, sql_text, pagesize=None):
        self.logon()
        try:
            jobId = self.submit_sql(sql_text, pagesize)
        except SyntaxError as e:
            return "SQL job submission failed. {}".format(str(e))
        if self.wait_for_job(jobId) == 'failed':
            details = self.get_job(jobId)
            return "SQL job {} failed while executing with error {}. Detailed message: {}".format(jobId, details['error'],
                                                                                                  details['error_message'])
        else:
            return self.get_result(jobId)

    def run(self,
                pagesize=None,
                get_result=False,
                blocking=True):
        """ run the internal SQL statement provided by SQLMagic
        """
        self.format_()
        return self.run_sql2(self._sql_stmt,
            pagesize=pagesize,
            get_result=get_result,
            blocking=blocking)

    def process_failed_jobs_until_all_completed(self, job_id_list):
        """
        re-send those that are failed - due to the time-out mechanism of SQL Query server

        Here, if job_time < 40 minutes, then we re-send.
        """
        complete_all = False
        while complete_all is False:
            complete_all = True
            for index, job_id in enumerate(job_id_list):
                job_result = self.get_job(job_id)
                if job_result["status"] == "failed":
                    delta = dateutil.parser.parse(
                        job_result["end_time"]) - dateutil.parser.parse(
                            job_result["submit_time"])
                    job_time = delta.total_seconds()
                    if job_time < 2400:  # 40 minutes
                        new_job_id = self.submit_sql2(job_result["statement"])
                        job_id_list[index] = new_job_id
                        complete_all = False
        return job_id_list

    def sql_ui_link(self):
        self.logon()

        if sys.version_info >= (3, 0):
            print ("https://sql-query.cloud.ibm.com/sqlquery/?instance_crn={}".format(
                urllib.parse.unquote(self.instance_crn)))
        else:
            print ("https://sql-query.cloud.ibm.com/sqlquery/?instance_crn={}".format(
                urllib.unquote(self.instance_crn).decode('utf8')))

    def get_cos_summary(self, url):
        """
        Return information for the given COR URL (may include bucket + prefix)

        Returns
        -------
        dict
            A dict with keys
                "largest_object"
                "largest_object_size"
                "newest_object_timestamp"
                "oldest_object_timestamp"
                "smallest_object"
                "smallest_object_size"
                "total_objects"
                "total_volume"
                "url"

        Example: self.get_cos_summary_demo()

        """
        def sizeof_fmt(num, suffix='B'):
            for unit in ['', 'K', 'M', 'G', 'T', 'P', 'E', 'Z']:
                if abs(num) < 1024.0:
                    return "%3.1f %s%s" % (num, unit, suffix)
                num /= 1024.0
            return "%.1f %s%s" % (num, 'Y', suffix)

        self.logon()

        url_parsed = self.analyze_cos_url(url)
        cos_client = self._get_cos_client(url_parsed.endpoint)

        paginator = cos_client.get_paginator("list_objects")
        page_iterator = paginator.paginate(Bucket=url_parsed.bucket, Prefix=url_parsed.prefix)

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

    def list_cos_objects(self, url):
        """Returns a dataframe with object meta info from given URI prefix.

        Args:
            url: A URI prefix. e.g., cos://us-south/<bucket-name>/object_path/
        """
        self.logon()

        url_parsed = self.analyze_cos_url(url)
        cos_client = self._get_cos_client(url_parsed.endpoint)
        paginator = cos_client.get_paginator("list_objects")
        page_iterator = paginator.paginate(Bucket=url_parsed.bucket, Prefix=url_parsed.prefix)
        page_dfs = [pd.DataFrame.from_dict(page["Contents"], orient="columns") for page in page_iterator]

        if len(page_dfs) > 0:
            result = pd.concat(page_dfs, ignore_index=True).drop(columns=["ETag", "Owner"]).rename(columns={"Key": "Object"})
            return result
        else:
            return pd.DataFrame(columns=['Object', 'LastModified', 'Size', 'StorageClass'])

    def export_job_history(self, cos_url=None, export_file_prefix = "job_export_", export_file_suffix = ".parquet"):
        """
        Export the most recent jobs to COS URL

        Parameters
        ----------
        cos_url : str
            A COS URL with prefix, i.e. cos://<cos-name>/<bucket>/<prefix>,
            where the data will be stored
        """
        if cos_url:
            # Default export location is target COS URL set at __init__
            # But we'll overwrite that with the provided export URL
            self.export_cos_url = cos_url
        elif not self.export_cos_url:
            raise ValueError('No configured export COS URL.')
        if not self.export_cos_url.endswith('/'):
            self.export_cos_url += "/"
        url_parsed = self.analyze_cos_url(self.export_cos_url)

        job_history_df = self.get_jobs() # Retrieve current job history (most recent 30 jobs)
        job_history_df['error'] = job_history_df['error'].astype(unicode)
        job_history_df['error_message'] = job_history_df['error_message'].astype(unicode)
        terminated_job_history_df = job_history_df[job_history_df['status'].isin(['completed', 'failed'])] # Only export terminated jobs
        newest_job_end_time = terminated_job_history_df.loc[pd.to_datetime(terminated_job_history_df['end_time']).idxmax()].end_time

        # List all existing objects in export location and identify latest exported job timestamp:
        cos_client = self._get_cos_client(url_parsed.endpoint)
        paginator = cos_client.get_paginator("list_objects")
        page_iterator = paginator.paginate(Bucket=url_parsed.bucket, Prefix=url_parsed.prefix)
        newest_exported_job_end_time = ""
        expected_object_prefix = url_parsed.prefix + export_file_prefix
        for page in page_iterator:
            if "Contents" in page:
                for key in page['Contents']:
                    object_name = key["Key"]
                    if not(object_name.startswith(expected_object_prefix)):
                        continue
                    prefix_end_index = len(expected_object_prefix)
                    suffix_index = object_name.find(export_file_suffix)
                    if not(prefix_end_index < suffix_index):
                        continue
                    job_end_time = object_name[prefix_end_index:suffix_index]
                    if job_end_time > newest_exported_job_end_time:
                        newest_exported_job_end_time = job_end_time

        # Export all new jobs if there are some:
        if newest_exported_job_end_time < newest_job_end_time:
            tmpfile = tempfile.NamedTemporaryFile()
            tempfilename = tmpfile.name
            new_jobs_df = terminated_job_history_df[terminated_job_history_df['end_time'] > newest_exported_job_end_time]
            if sys.version_info >= (3, 0):
                new_jobs_df.to_parquet(engine="pyarrow", path=tempfilename, compression="snappy", index=False)
            else:
                new_jobs_df.to_parquet(engine="pyarrow", fname=tempfilename, compression="snappy", index=False)
            export_object = url_parsed.prefix + export_file_prefix + newest_job_end_time + export_file_suffix
            cos_client.upload_file(Bucket=url_parsed.bucket, Filename=tempfilename, Key=export_object)
            print("Exported {} new jobs".format(new_jobs_df['job_id'].count()))
            tmpfile.close()
        else:
            print("No new jobs to export")

    def get_schema_data(self, cos_url, type="json"):
        """
        Return the schema information

        Parameters
        ----------
        cos_url : str
            The COS URL where data is stored
        type : str, optional
            The format type of the data, default is 'json'
            Use from ['json', 'csv', 'parquet'] with case-insensitive

        Returns
        -------
        DataFrame

        """
        if type.upper() not in ["JSON", "CSV", "PARQUET"]:
            logger.error("use wrong format")
            raise Exception("Use wrong format of data: 'type' option")
        sql_stmt = """
        SELECT * FROM DESCRIBE({cos_in} STORED AS {type})
        INTO {cos_out} STORED AS JSON
        """.format(cos_in=cos_url, type=type.upper(), cos_out=self.cos_out_url)
        return self.run_sql(sql_stmt)

    def analyze(self, job_id):
        """Provides some insights about the data layout from the current SQL statement

        Parameters
        -------------
        job_id : str
            The job ID

        todo
        ------

        1. new sql only when max_obj_size > 300MB
        2. check if STORED AS is used, if not suggested adding to sql with PARQUET or JSON
        3. add PARITIONED ... not at the end, but right after STORED AS (which can be missing in original SQL)
        """
        BestPracticeContainer = namedtuple('SqlBestPractice',
                                           ['size', 'max_objs'])
        best_practice = BestPracticeContainer("128 MB", 50)

        result = self.get_job(job_id)
        if result['status'] != 'completed':
            msg = "Job {job_id} is {status} - no more insights".format(
                job_id=job_id, status=result['status'])
            return msg

        cos_url = result['resultset_location']
        if not cos_url:
            msg = "Job {job_id} does not return anything - no more insights".format(
                job_id=job_id)
            return msg

        cos_result = self.get_cos_summary(cos_url)

        def get_total_objects():
            # total_objects = cos_result['total_objects']  #not exact
            r = self.list_results(job_id)
            seriesObj = r.apply(lambda x: True
                                if int(x['Size']) > 0 else False,
                                axis=1)
            total_objects = len(seriesObj[seriesObj == True].index)
            return total_objects

        total_objects = get_total_objects()

        def get_size_in_MB(size_info):
            num, unit = size_info.split(' ')
            mapping = {"TB": 1048576, "GB": 1024, "MB": 1}

            if unit in mapping:
                size_MB = float(num) * mapping[unit]
            else:
                size_MB = 1.0
            return size_MB

        largest_size_MB = get_size_in_MB(cos_result['largest_object_size'])

        if largest_size_MB < float(best_practice.size.split(" ")[0]) * 2:
            msg = "Job {job_id} looks fine - no more insights".format(
                job_id=job_id)
            return msg

        total_volume_MB = get_size_in_MB(cos_result['total_volume'])
        SqlContainer = namedtuple('SqlStatus', [
            'job_id', 'total_data_objects', 'total_volume', 'max_object_size'
        ])
        query = SqlContainer(job_id, total_objects, total_volume_MB,
                             largest_size_MB)
        mappings = {
            "job_id": job_id,
            "total_objects": total_objects,
            "total_volume_MB": total_volume_MB
        }
        msg_01 = "Job {job_id} has {total_objects} object{s}, with {total_volume_MB} MB in total.".format(
            **mappings, s="s" if mappings["total_objects"] > 1 else "")
        if (mappings["total_objects"] > 1):
            msg_01 = msg_01 + " Current object size is ~ {size} MB".format(
                size=mappings["total_volume_MB"] / mappings["total_objects"])

        mappings = {"size": best_practice.size}
        msg_02 = "Best practices: object sizes ~ {size}".format(**mappings)

        mappings = {
            "num_objs":
            min(best_practice.max_objs,
                query.total_volume / float(best_practice.size.split(" ")[0]))
        }

        msg_03 = "Current SQL:\n {sql}\n".format(sql=result["statement"])

        def revise_storage(sql_stmt, storage="parquet"):
            url_storage = re.search(r'INTO (cos)://[^\s]* STORED AS', sql_stmt)
            if url_storage:
                loc = url_storage.span(0)[1]
                pre = sql_stmt[:loc + 1]
                post = sql_stmt[loc + 1:]
                detected_storage = re.search(r'^[^\s]*', post).group(0)
                if storage.upper() != detected_storage:
                    post = post.replace(detected_storage, storage.upper(), 1)
                sql_stmt = pre + post
            else:
                url = re.search(r'INTO (cos)://[^\s]*', sql_stmt)
                loc = url.span(0)[1]
                sql_stmt = sql_stmt[:loc] + ' STORED AS  ' + storage.upper(
                ) + sql_stmt[loc + 1:]
            return sql_stmt

        def msg_partition_into():
            msg_sub = [None] * 2
            msg_sub[
                0] = "Consider using: PARTITIONED INTO {num_objs} OBJECTS/BUCKETS".format(
                    **mappings)

            new_sql = result["statement"]
            if "PARTITION" not in new_sql:
                new_sql = format_sql(revise_storage(new_sql, "parquet"))
                import re
                url = re.search(
                    r'INTO (cos)://[^\s]*[\s]+STORED[\s]+AS[\s]+PARQUET',
                    new_sql)
                loc = url.span(0)[1]
                new_sql = new_sql[:
                                  loc] + " PARTITIONED INTO {num_objs} OBJECTS".format(
                                      **mappings) + new_sql[loc + 1:]

            result["rows_returned"]
            msg_sub[1] = "Suggested SQL:\n {sql}\n".format(sql=new_sql)
            return msg_sub

        def msg_partition_every():
            msg_05 = [None] * 2
            num_rows = int(
                float(result["rows_returned"]) /
                (query.total_volume / float(best_practice.size.split(" ")[0])))
            msg_05[
                0] = "Consider using: PARTITIONED EVERY {num_rows} ROWS".format(
                    **mappings, num_rows=num_rows)

            new_sql = result["statement"]
            if "PARITION" not in new_sql:
                # new_sql = new_sql + " PARTITIONED EVERY {num_rows} ROWS".format(
                #    **mappings, num_rows=num_rows)
                new_sql = format_sql(revise_storage(new_sql, "parquet"))
                import re
                url = re.search(
                    r'INTO (cos)://[^\s]*[\s]+STORED[\s]+AS[\s]+PARQUET',
                    new_sql)
                loc = url.span(0)[1]
                new_sql = new_sql[:
                                  loc] + " PARTITIONED EVERY {num_rows} ROWS".format(
                                      **mappings) + new_sql[loc + 1:]
            result["rows_returned"]
            msg_05[1] = "Suggested SQL:\n {sql}\n".format(sql=new_sql)
            return msg_05

        msg_04 = msg_partition_into()
        msg_05 = msg_partition_every()
        my_list = [msg_01, msg_02, msg_03]
        my_list.extend(msg_04)
        my_list.extend(msg_05)
        msg = os.linesep.join(my_list)

        return msg

    def _get_ts_datasource(self, table_name, key, time_stamp, observation,
                cos_out, granularity="raw", where_clause="", ops="avg", dry_run=False,
                num_objects=None, num_rows=None):
        """
        Prepare the data source for time-series in the next-query

        It will returns the data source in 3 columns: field_name, time_stamp, observation

        Parameters
        --------------
        table: str
            The catalog table name or the view-table that you generate from the WITH clause via :meth:`with_` method
        key: str
            The column name being used as the key, and is maped to `field_name`
        time_stamp: str
            The column name being used as timetick, and is mapped to `time_stamp`
        observation: str
            The column name being used as value, and is maped to `observation`
        cos_out: str
            The COS URL where the data is copied to - later as data source
        granularity: str
            a value in one of ["raw", "per_min", "per_<x>min", "per_sec", "per_<x>sec", "per_hour", "per_<x>hour"]
            with <x> is a number divided by 60, e.g. 10, 15
        ops: str
            The aggregation method: "avg", "sum", "max", "min", "count"

        Returns
        ----------
        str
            The COS_URL where the data with 3 fields (key, time_stamp, observation)
            and can be digested into time-series via TIME_SERIES_FORMAT(key, timestick, value)
        """
        tmp_cos = self.cos_out_url
        if num_objects is None and num_rows is None:
            print("provide at least `num_objects` or `num_rows`")
            assert(0)

        if granularity == "raw":
            pass
        elif granularity == "per_min":
            pass
        if time_stamp in self._unixtime_columns:
            #  -- convert unix-time in ms to sec
            time_info = "cast({time_stamp}/1000 as timestamp)".format(time_stamp=time_stamp)
        else:
            time_info = "{time_stamp}".format(time_stamp=time_stamp)

        if granularity == "raw":
            tmp_cos = cos_out

        if len(where_clause) == 0:
            extra_where = ""
        else:
            extra_where = "AND " + where_clause

        if num_objects:
            partition_clause = "PARTITIONED INTO {x} OBJECTS".format(x=num_objects)
        elif num_rows:
            partition_clause = "PARTITIONED EVERY {x} ROWS".format(x=num_rows)
        select_stmt = """
            SELECT {key} as field_name,
                {time_info} as time_stamp,
                {observation} as observation
            FROM {table_name}
            WHERE isnotnull({key}) AND isnotnull({observation})
            {extra_where}
            INTO {cos_out} STORED AS PARQUET {partition_clause}
            """.format(table_name=table_name, cos_out=tmp_cos, key=key, observation=observation, time_info=time_info, extra_where=extra_where,
                partition_clause=partition_clause)
        if self._has_with_clause and not self._has_select_clause:
            self._sql_stmt = self._sql_stmt + select_stmt
        else:
            self._sql_stmt = select_stmt
        result = None
        if dry_run:
            print_sql(self._sql_stmt)
            select_container_id_full_location = "cos://dry_run/"
        else:
            result = self.run_sql(self._sql_stmt)
            select_container_id_full_location = self.get_job(result.job_id)['resultset_location']

        cos_in = ""
        if granularity == "raw":
            return result
        else:
            cos_in = select_container_id_full_location

        def query_min():
            """
            return:
                None or 'result'
            """
            nonlocal cos_in
            import re
            p = re.compile('per_[0-9]*min')
            p2 = re.compile('per_[0-9]+min')
            level = "raw"
            num_min = 1
            if p.match(granularity):
                level = "minute"
                if p2.match(granularity):
                    temp = re.findall(r'\d+', granularity)
                    num_min = list(map(int, temp))[0]
                    assert(60 % num_min == 0)
            else:
                return None

            if level is "minute":
                sql_stmt = """
                select
                    field_name,
                    to_date(time_stamp) as time_stamp_date,
                    hour(time_stamp) as time_stamp_hour,
                    (floor(minute(time_stamp)/{num_min})) * {num_min} as time_stamp_minute, -- within [current, current+{num_min}) minute time-window
                    {ops}(observation) as {observation}
                from {cos_in} stored as parquet
                group by field_name,  to_date(time_stamp), hour(time_stamp), (floor(minute(time_stamp)/{num_min})) * {num_min}
                INTO {cos_out} STORED AS PARQUET {partition_clause}
                """.format(cos_in=cos_in, cos_out=tmp_cos, key=key, observation=observation, time_info=time_info, num_min=num_min,
                    partition_clause=partition_clause, ops=ops)
                if dry_run:
                    print_sql(sql_stmt)
                    result = None
                else:
                    result = self.run_sql(sql_stmt)

                # Restore timestamp as single column
                if dry_run:
                    cos_in = "cos://dry_run/"
                else:
                    cos_in = self.get_job(result.job_id)['resultset_location']
                sql_stmt = """
                select
                    field_name, -- as {key},
                    to_timestamp(concat(date(time_stamp_date), " ", time_stamp_hour, ":", time_stamp_minute), "yyyy-MM-dd HH:mm") as time_stamp,
                    {observation} as observation
                from {cos_in} stored as parquet
                INTO {cos_out} STORED AS PARQUET {partition_clause}
                """.format(cos_in=cos_in, cos_out=cos_out, key=key, observation=observation, time_info=time_info,
                    partition_clause=partition_clause)
                if dry_run:
                    print_sql(sql_stmt)
                    result = None
                else:
                    result = self.run_sql(sql_stmt)
            return result

        def query_sec():
            """
            return:
                None or 'result'
            """
            import re
            p = re.compile('per_[0-9]*sec')
            p2 = re.compile('per_[0-9]+sec')
            level = "raw"
            num_sec = 1
            if p.match(granularity):
                level = "sec"
                if p2.match(granularity):
                    temp = re.findall(r'\d+', granularity)
                    num_sec = list(map(int, temp))[0]
                    assert(60 % num_sec == 0)
            else:
                return None

            if level is "sec":
                sql_stmt = """
                select
                    field_name,
                    to_date(time_stamp) as time_stamp_date,
                    hour(time_stamp) as time_stamp_hour,
                    minute(time_stamp) as time_stamp_minute,
                    (floor(second(time_stamp)/{num_sec})) * {num_sec} as time_stamp_second, -- within [current, current+{num_sec}) second time-window
                    {ops}(observation) as {observation}
                from {cos_in} stored as parquet
                group by field_name,  to_date(time_stamp), hour(time_stamp), minute(time_stamp), (floor(second(time_stamp)/{num_sec})) * {num_sec}
                INTO {cos_out} STORED AS PARQUET {partition_clause}
                """.format(cos_in=cos_in, cos_out=tmp_cos, key=key, observation=observation, time_info=time_info, num_sec=num_sec,
                    partition_clause=partition_clause, ops=ops)
                if dry_run:
                    print_sql(sql_stmt)
                    result = None
                else:
                    result = self.run_sql(sql_stmt)

                # Restore timestamp as single column
                if dry_run:
                    init_cos = "cos://dry_run/"
                else:
                    init_cos = self.get_job(result.job_id)['resultset_location']
                sql_stmt = """
                select
                    field_name, -- as {key},
                    to_timestamp(concat(date(time_stamp_date), " ", ":".join([time_stamp_hour, time_stamp_minute, time_stamp_second]), "yyyy-MM-dd HH:mm:ss") as time_stamp,
                    {observation} as observation
                from {cos_in} stored as parquet
                INTO {cos_out} STORED AS PARQUET {partition_clause}
                """.format(cos_in=cos_in, cos_out=cos_out, key=key, observation=observation, time_info=time_info,
                    partition_clause=partition_clause)
                if dry_run:
                    print_sql(sql_stmt)
                    result = None
                else:
                    result = self.run_sql(sql_stmt)
            return result

        result = query_min()
        if result is None:
            result = query_sec()
        return result