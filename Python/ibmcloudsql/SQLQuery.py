# ------------------------------------------------------------------------------
# Copyright IBM Corp. 2020
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
# flake8: noqa F522
import os
import sys
import tempfile
import time
import types
import urllib
import xml.etree.ElementTree as ET
from collections import namedtuple
from pprint import pformat

import backoff
import dateutil.parser
import numpy as np
import pandas as pd
import requests
from requests.exceptions import HTTPError

try:
    from exceptions import (
        RateLimitedException,
        CosUrlNotFoundException,
        CosUrlInaccessibleException,
        SqlQueryCrnInvalidFormatException,
        SqlQueryInvalidPlanException,
        SqlQueryFailException,
        SqlQueryInvalidFormatException,
        InternalError502Exception,
    )
except Exception:
    from .exceptions import (
        RateLimitedException,
        CosUrlNotFoundException,
        CosUrlInaccessibleException,
        SqlQueryCrnInvalidFormatException,
        SqlQueryInvalidPlanException,
        SqlQueryFailException,
        SqlQueryInvalidFormatException,
        InternalError502Exception,
    )
try:
    from .cos import COSClient
    from .utilities import rename_keys
    from .sql_magic import SQLMagic, format_sql, print_sql
    from .catalog_table import HiveMetastore
except ImportError:
    from cos import COSClient
    from utilities import rename_keys
    from sql_magic import SQLMagic, format_sql, print_sql
    from catalog_table import HiveMetastore
import logging
from functools import wraps
import json
from json import JSONDecodeError
import inspect
import re

logger = logging.getLogger(__name__)


def validate_job_status(f):
    """check if input about job status, via `status` argument is corrected"""

    @wraps(f)
    def wrapped(*args, **kwargs):
        self = args[0]
        dictionary = inspect.getcallargs(f, *args, **kwargs)
        status = dictionary["status"]
        supported_job_status = ["running", "completed", "failed"]
        if status not in supported_job_status:
            raise ValueError(
                "`status` must be a value in {}".format(supported_job_status)
            )
        else:
            return f(*args, **kwargs)

    return wrapped


def check_saved_jobs_decorator(f):
    """a decorator that load data from ProjectLib, check for completed SQL
    Query job, before deciding to launch it"""

    @wraps(f)
    def wrapped(*args, **kwargs):
        self = args[0]
        dictionary = inspect.getcallargs(f, *args, **kwargs)
        prefix = dictionary["file_name"]  # Gets you the username, default or modifed
        sql_stmt = dictionary["sql_stmt"]
        # refine query
        sql_stmt = format_sql(sql_stmt)

        status_no_job_id = "not_launched"
        run_as_usual = True
        if self.project_lib is not None:
            # Use Watson Studio
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
                    if self.project_lib.data[sql_stmt]["status"] != status_no_job_id:
                        # query the status
                        job_result = self.get_job(job_id)
                        self.project_lib.data[sql_stmt]["job_info"] = job_result
                        try:
                            self.project_lib.data[sql_stmt]["status"] = job_result[
                                "status"
                            ]
                        except KeyError as e:
                            import pprint

                            pprint.pprint(job_id, "\n", job_result)
                            raise e
                        if job_result["status"] == "failed":
                            run_as_usual = True
                        self.write_project_lib_data()
                    else:
                        run_as_usual = True
        else:
            # use local file
            if prefix is None:
                if self._tracking_filename is None:
                    msg = "Please configure the JSON file via `set_tracking_file`"
                    raise ValueError(msg)
                else:
                    prefix = self._tracking_filename
            try:
                with open(prefix) as json_data:
                    self._data = json.load(json_data)
                if sql_stmt in self._data:
                    run_as_usual = False
                    job_id = self._data[sql_stmt]["job_id"]
                    if self._data[sql_stmt]["status"] == "completed":
                        print("Job {} completed".format(job_id))
                    else:
                        if self._data[sql_stmt]["status"] != status_no_job_id:
                            # query the status
                            job_result = self.get_job(job_id)
                            self._data[sql_stmt]["job_info"] = job_result
                            try:
                                self._data[sql_stmt]["status"] = job_result["status"]
                            except KeyError as e:
                                import pprint

                                pprint.pprint(job_result)
                                raise e
                            if job_result["status"] == "failed":
                                run_as_usual = True
                            with open(prefix, "w") as outfile:
                                json.dump(self._data, outfile)
                        else:
                            run_as_usual = True
            except FileNotFoundError:
                self._data = {}

        if run_as_usual:
            e_ = None
            job_id = ""
            status = "queued"
            try:
                job_id = f(*args, **kwargs)
                result = {"job_id": job_id, "status": status}
                if self.project_lib is not None:
                    self.project_lib.data[sql_stmt] = result
                    self.write_project_lib_data()
                else:
                    # use local file
                    self._data[sql_stmt] = result
                    with open(prefix, "w") as outfile:
                        json.dump(self._data, outfile)
            except Exception as e:
                e_ = e
                status = status_no_job_id

            if e_ is not None:
                if self.project_lib is not None:
                    self.project_lib.data[sql_stmt] = {
                        "job_id": job_id,
                        "status": status,
                    }
                    self.write_project_lib_data()
                else:
                    # use local file
                    self._data[sql_stmt] = {"job_id": job_id, "status": status}
                    with open(prefix, "w") as outfile:
                        json.dump(self._data, outfile)
            if e_ is not None:
                raise e_
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
    max_tries: int, optional
        The number of time :meth:`.submit_sql`, should try to request CloudSQL before giving up.
    iam_max_tries: int, optional
        The number of times to request credential from IAM. By default, token is returned from a request to `iam.cloud.ibm.com` which may not be responsive (i.e. timeout=5 seconds). This parameter controls how many times to try.
    thread_safe: bool, optional (=False)
        If thread-safe is used, a new Session object is created upon this object creation
    """

    def __init__(
        self,
        api_key,
        instance_crn,
        target_cos_url=None,
        client_info="IBM Cloud SQL Query Python SDK",
        thread_safe=False,
        max_concurrent_jobs=4,
        max_tries=1,
        iam_max_tries=1,
    ):
        staging_env = instance_crn.startswith("crn:v1:staging")
        if staging_env:
            self.api_hostname = "api.sql-query.test.cloud.ibm.com"
            self.ui_hostname = "sql-query.test.cloud.ibm.com"
        else:
            self.api_hostname = "api.sql-query.cloud.ibm.com"
            self.ui_hostname = "sql-query.cloud.ibm.com"
        COSClient.__init__(
            self,
            cloud_apikey=api_key,
            cos_url=target_cos_url,
            client_info=client_info,
            iam_max_tries=iam_max_tries,
            thread_safe=thread_safe,
            staging=staging_env,
        )
        SQLMagic.__init__(self)
        if target_cos_url is not None:
            HiveMetastore.__init__(self, target_cos_url)

        self.instance_crn = instance_crn
        self.target_cos_url = target_cos_url
        self.export_cos_url = target_cos_url
        self.user_agent = client_info

        self.max_tries = max_tries
        self.max_concurrent_jobs = (
            max_concurrent_jobs  # the current maximum concurrent jobs
        )

        # track the status of jobs - save the time to SQLQuery server
        self.jobs_tracking = {}
        self._tracking_filename = None

        logger.debug("SQLClient created successful")

    def set_tracking_file(self, file_name):
        """provides the file name which is used for tracking multiple SQL requests

        Notes
        -----
        This is the local file, which is used when you don't have access to Watson Studio
        """
        self._tracking_filename = file_name

    @property
    def my_jobs(self):
        """
        Return information about jobs already queried via :meth:`.get_job`
        issued by this SQLClient class object

        This is different from :py:meth:`.get_jobs`

        Returns
        -------
        dict

        """
        return self.jobs_tracking

    def configure(self, apikey=None, instance_crn=None, cos_out_url=None):
        """ update the configuration
        """
        COSClient.configure(self, apikey)
        if instance_crn is None:
            self.instance_crn = (
                input(
                    "Enter SQL Query Instance CRN (leave empty to use previous one): "
                )
                or self.instance_crn
            )
        else:
            self.instance_crn = instance_crn
        if cos_out_url is None:
            if self.target_cos_url is None or self.target_cos_url == "":
                while True:
                    self.target_cos_url = input("Enter target URI for SQL results: ")
                    if self.is_valid_cos_url(cos_url):
                        break
            else:
                old_cos_url = str(self.target_cos_url)
                while True:
                    self.target_cos_url = (
                        input(
                            "Enter target URI for SQL results (leave empty to use "
                            + self.target_cos_url
                            + "): "
                        )
                        or old_cos_url
                    )
                    if self.is_valid_cos_url(cos_url):
                        break
        else:
            self.target_cos_url = cos_out_url
        HiveMetastore.configure(self, self.target_cos_url)
        self.logon(force=True)

    def _response_error_msg(self, response):
        try:
            return response.json()["errors"][0]["message"]
        except:
            # if we get the error from some intermediate proxy, it may
            # not match the SQLQuery error format
            return "Non-parseable error: {txt}".format(txt=response.text[0:200])

    def _send_req(self, json_data):
        """send SQL data to API. return job id"""

        try:
            response = requests.post(
                "https://{}/v2/sql_jobs?instance_crn={}".format(
                    self.api_hostname, self.instance_crn
                ),
                headers=self.request_headers,
                json=json_data,
            )

            # Throw in case we hit the rate limit
            if response.status_code == 429:
                time.sleep(3)  # seconds
                raise RateLimitedException(
                    "SQL submission failed ({code}): {msg}".format(
                        code=response.status_code,
                        msg=self._response_error_msg(response),
                    )
                )
            # Throw in case we hit 502, which sometimes is sent by Cloudflare when API is temporarily unreachable
            if response.status_code == 502:
                time.sleep(3)  # seconds
                raise InternalError502Exception(
                    "Internal Error ({code}): {msg}".format(
                        code=response.status_code,
                        msg=self._response_error_msg(response),
                    )
                )

            # any other error but 429 will be raised here, like 403 etc
            response.raise_for_status()

            resp = response.json()
            if "job_id" in resp:
                return resp["job_id"]
            else:
                raise SyntaxError(
                    "Response {resp} contains no job ID".format(resp=resp)
                )
        except (HTTPError) as _:
            msg = self._response_error_msg(response)
            error_message = "SQL submission failed ({code}): {msg} - {query}".format(
                code=response.status_code, msg=msg, query=pformat(json_data)
            )
            crn_error = "Service CRN has an invalid format"
            crn_invalid_plan_error = "upgrade this instance"
            if crn_error in error_message:
                error_message = "SQL submission failed ({code}): {msg}".format(
                    code=response.status_code, msg=msg
                )
                raise SqlQueryCrnInvalidFormatException(error_message)
            elif crn_invalid_plan_error in error_message:
                error_message = "SQL submission failed ({code}): {msg}".format(
                    code=response.status_code, msg=msg
                )
                raise SqlQueryInvalidPlanException(error_message)
            else:
                raise SyntaxError(error_message)

    def submit(self, pagesize=None):
        """ run the internal SQL statement that you created using the APIs provided by SQLMagic
        """
        self.format_()
        return self.submit_sql(self._sql_stmt, pagesize=pagesize)

    def submit_sql(self, sql_stmt, pagesize=None):
        """
        Asynchronous call - submit and quickly return the job_id.

        Parameters
        ----------
        sql_stmt: str
            SQL Query string
        pagesize: int, optional
            an integer indicating the number of rows for each partition/page
            [using PARTITIONED EVERY <pagesize> ROWS syntax]

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

        Examples
        --------

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
        self.logon()
        sql_text = sql_stmt
        sqlData = {"statement": sql_text}

        def INTO_is_present(sql_text):
            """ check if INTO keyword is present in the SQL query"""
            tmp = sql_text.replace("\n", " ")
            return (" INTO " in tmp.upper()) or ("\nINTO " in tmp.upper())

        # If a valid pagesize is specified we need to append the proper PARTITIONED EVERY <num> ROWS clause
        if pagesize or pagesize == 0:
            if type(pagesize) == int and pagesize > 0:
                if self.target_cos_url and not INTO_is_present(sql_text):
                    sqlData["statement"] += " INTO {}".format(self.target_cos_url)
                elif not INTO_is_present(sql_text):
                    raise SyntaxError(
                        'Neither resultset_target parameter nor "INTO" clause specified.'
                    )
                elif " PARTITIONED " in sql_text.upper():
                    raise SyntaxError(
                        "Must not use PARTITIONED clause when specifying pagesize parameter."
                    )
                sqlData["statement"] += " PARTITIONED EVERY {} ROWS".format(pagesize)
            else:
                raise ValueError(
                    "pagesize parameter ({}) is not valid.".format(pagesize)
                )
        elif self.target_cos_url and not INTO_is_present(sql_text):
            sqlData.update({"resultset_target": self.target_cos_url})

        max_tries = self.max_tries
        intrumented_send = backoff.on_exception(
            backoff.expo,
            (RateLimitedException, InternalError502Exception),
            max_tries=max_tries,
        )(self._send_req)
        return intrumented_send(sqlData)

    @check_saved_jobs_decorator
    def submit_and_track_sql(self, sql_stmt, pagesize=None, file_name=None):
        """
        Each SQL Query instance is limited by the number of sql queries that it
        can handle at a time.  This can be a problem when you
        launch many SQL Query jobs, as such limitation may prevent you to
        complete all of them in one session. The `max_tries` options when creating
        the SQL Query client object allows
        you to re-send the job, which is still limited to one session.
        The time for one session is often limited when when using
        SQL Query client via Watson Studio, i.e. you
        will lose the session after having no interaction with the notebook for
        a period of time.

        This API provides the capability to put the information of each
        launched jobs in a `file_name` stored either

        * as an asset in the Watson Studio's Project.
        * as a regular file in the local machine.

        The SQL Query client will check the content of such file name to see
        if the given `sql_stmt` has been
        launched, and if so, whether it is completed or not. If not
        completed, then it relaunches the job, and update the content in this
        file. Otherwise, it skips the `sql_stmt`.

        To check if a `sql_stmt` has been issued or not, the
        :func:`.format_sql` transforms the query string into a style that can
        be used for string comparison that is tolerance to white spaces, new
        lines, comments, lower-case or upper-case uses in the query string.
        This is done by the decorator :meth:`check_saved_jobs_decorator`.

        This is beneficial in the scenario when you launch many many jobs, and don't want to restart from the beginning.

        Parameters
        ----------
        sql_stmt: str
            sql string
        pagesize: int, optional
            the page size
        file_name: str, optional
            The file name should be a JSON file, i.e. $file_name.json.
            You need to provide the file name if

            * (1) you use Watson studio notebook and you haven't provided it in :meth:`.connect_project_lib`,
            * (2) you use local notebook, and you want to use a local file to track it

            You don't need to provide the file name if you're using Watson studio, and the file name has been provided via :meth:`.connect_project_lib`.

        Notes
        -----
            To use this API in Watson Studio, the SQL Query client must already connected to the ProjectLib object via :meth:`.connect_project_lib` method.

            This APIs make use of :py:meth:`.COSClient.connect_project_lib`, :py:meth:`.COSClient.read_project_lib_data`.

        """
        return self.submit_sql(sql_stmt, pagesize=pagesize)

    def wait_for_job(self, jobId, sleep_time=2):
        """
        It's possible that the job's failed because of Spark's internal error
        which does not have any status. So "unknown" is added for such cases.

        Parameters
        -----------
        jobId: str
            The job-id

        sleep_time: int, optional
            The time interval to sleep before making a new check if the job is done

        Returns
        -------
            'failed', 'completed', or 'unknown'
        """

        def wait_for_job(jobId):
            while True:
                self.logon()
                response = requests.get(
                    "https://{}/v2/sql_jobs/{}?instance_crn={}".format(
                        self.api_hostname, jobId, self.instance_crn
                    ),
                    headers=self.request_headers,
                )

                if response.status_code == 200 or response.status_code == 201:
                    status_response = response.json()
                    jobStatus = status_response["status"]
                    if jobStatus == "completed":
                        break
                    if jobStatus == "failed":
                        print("Job {} has failed".format(jobId))
                        break
                else:
                    print(
                        "Job status check failed with http code {}".format(
                            response.status_code
                        )
                    )
                    break
                time.sleep(sleep_time)
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
        Return the queried data from the given job-id

        Parameters
        ----------
        jobId: int
            The value, if not stored, can be retrieved from :meth:`.get_jobs`
        pagenumber: int, optional
            If the data, from the given `job_id` is saved in pages/partitions, then this should be a value
            in the range from 1 to len(self.list_results(job_id))

        Returns
        -------
        dataframe
            The dataframe holding the queried data from a completed job


        Examples
        --------

        .. code-block:: console

            curl -XGET \\
                --url "https://api.sql-query.cloud.ibm.com/v2/sql_jobs?instance_crn=<YOUR_SQL_QUERY_CRN>" \\
                -H "Accept: application/json" \\
                -H "Authorization: Bearer <YOUR_BEARER_TOKEN>"  \\
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
        job_status = job_details.get("status")
        if job_status == "running":
            raise ValueError(
                "SQL job with jobId {} still running. Come back later.".format(jobId)
            )
        elif job_status != "completed":
            raise ValueError(
                "SQL job with jobId {} did not finish successfully. No result available.".format(
                    jobId
                )
            )

        if "resultset_location" not in job_details:
            return None

        url_parsed = self.analyze_cos_url(job_details["resultset_location"])
        result_location = "https://{}/{}?prefix={}".format(
            url_parsed.endpoint, url_parsed.bucket, url_parsed.prefix
        )
        result_format = job_details["resultset_format"]

        if result_format not in ["csv", "parquet", "json"]:
            raise ValueError(
                "Result object format {} currently not supported by get_result().".format(
                    result_format
                )
            )

        response = requests.get(result_location, headers=self.request_headers,)

        if response.status_code == 200 or response.status_code == 201:
            ns = {"s3": "http://s3.amazonaws.com/doc/2006-03-01/"}
            responseBodyXMLroot = ET.fromstring(response.text)
            bucket_objects = []
            # Find result objects with data
            for contents in responseBodyXMLroot.findall("s3:Contents", ns):
                key = contents.find("s3:Key", ns)
                if int(contents.find("s3:Size", ns).text) > 0:
                    bucket_objects.append(key.text)
                # print("Job result for {} stored at: {}".format(jobId, result_object))
        else:
            raise ValueError(
                "Result object listing for job {} at {} failed with http code {}".format(
                    jobId, result_location, response.status_code
                )
            )

        cos_client = self._get_cos_client(url_parsed.endpoint)

        # When pagenumber is specified we only retrieve that page. Otherwise we concatenate all pages to one DF:
        if pagenumber or pagenumber == 0:
            if " PARTITIONED EVERY " not in job_details["statement"].upper():
                raise ValueError(
                    "pagenumber ({}) specified, but the job was not submitted with pagination option.".format(
                        pagenumber
                    )
                )
            if type(pagenumber) == int and 0 < pagenumber <= len(bucket_objects):
                if result_format == "csv":
                    body = cos_client.get_object(
                        Bucket=url_parsed.bucket, Key=bucket_objects[pagenumber - 1]
                    )["Body"]
                    if not hasattr(body, "__iter__"):
                        body.__iter__ = types.MethodType(self.__iter__, body)
                    result_df = pd.read_csv(body)
                elif result_format == "parquet":
                    tmpfile = tempfile.NamedTemporaryFile()
                    tempfilename = tmpfile.name
                    tmpfile.close()
                    cos_client.download_file(
                        Bucket=url_parsed.bucket,
                        Key=bucket_objects[pagenumber - 1],
                        Filename=tempfilename,
                    )
                    result_df = pd.read_parquet(tempfilename)
                elif result_format == "json":
                    body = cos_client.get_object(
                        Bucket=url_parsed.bucket, Key=bucket_objects[pagenumber - 1]
                    )["Body"]
                    body = body.read().decode("utf-8")
                    result_df = pd.read_json(body, lines=True)

            else:
                raise ValueError("Invalid pagenumner ({}) specified".format(pagenumber))
        else:
            # Loop over result objects and read and concatenate them into result data frame
            for bucket_object in bucket_objects:

                if result_format == "csv":
                    body = cos_client.get_object(
                        Bucket=url_parsed.bucket, Key=bucket_object
                    )["Body"]
                    # add missing __iter__ method, so pandas accepts body as file-like object
                    if not hasattr(body, "__iter__"):
                        body.__iter__ = types.MethodType(self.__iter__, body)

                    partition_df = pd.read_csv(body, error_bad_lines=False)

                elif result_format == "parquet":
                    tmpfile = tempfile.NamedTemporaryFile()
                    tempfilename = tmpfile.name
                    tmpfile.close()
                    cos_client.download_file(
                        Bucket=url_parsed.bucket,
                        Key=bucket_object,
                        Filename=tempfilename,
                    )

                    partition_df = pd.read_parquet(tempfilename)

                elif result_format == "json":
                    body = cos_client.get_object(
                        Bucket=url_parsed.bucket, Key=bucket_object
                    )["Body"]
                    body = body.read().decode("utf-8")

                    partition_df = pd.read_json(body, lines=True)

                # Add columns from hive style partition naming schema
                hive_partition_candidates = bucket_object.replace(
                    url_parsed.prefix + "/", ""
                ).split("/")
                for hive_partition_candidate in hive_partition_candidates:
                    if (
                        hive_partition_candidate.count("=") == 1
                    ):  # Hive style folder names contain exactly one '='
                        column = hive_partition_candidate.split("=")
                        column_name = column[0]
                        column_value = column[1]
                        if (
                            column_value == "__HIVE_DEFAULT_PARTITION__"
                        ):  # Null value partition
                            column_value = np.nan
                        if len(column_name) > 0 and len(column_value) > 0:
                            partition_df[column_name] = column_value

                if "result_df" not in locals():
                    result_df = partition_df
                else:
                    result_df = result_df.append(partition_df, sort=False)

            if "result_df" not in locals():
                return None

        return result_df

    def list_results(self, jobId, wait=False):
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
        wait: bool, default:False
            If True, wait for the requested `job_id` to complete to get the information

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
            if job_details["status"] == "running":
                raise ValueError(
                    "SQL job with jobId {} still running. Come back later."
                )
            elif job_details["status"] != "completed":
                raise ValueError(
                    "SQL job with jobId {} did not finish successfully. No result available."
                )

            if "resultset_location" not in job_details:
                return None
            result_location = job_details["resultset_location"]
            url_parsed = self.analyze_cos_url(result_location)
            result_bucket = url_parsed.bucket
            result_endpoint = url_parsed.endpoint
            result_objects_df = self.list_cos_objects(job_details["resultset_location"])
            result_objects_df["Bucket"] = result_bucket
            result_objects_df["ObjectURL"] = result_objects_df.apply(
                lambda x: "cos://%s/%s/%s"
                % (result_endpoint, result_bucket, x["Object"]),
                axis=1,
            )
            return result_objects_df

        job_id = jobId
        if wait is True:
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
                time.sleep(2)
        else:
            x = list_results(job_id)
        return x

    def rename_exact_result(self, jobId, wait=False):
        """
        A SQL Query can store data into partitioned/paginated multiple objects, or single object.

        Even with single object, indeed, multiple objects are created, two of them has size 0.
        (<URL>/_SUCCESS, and <URL>/) beside the ones that hold data (<URL>/<data1>, <URL>/<data2>)

        This API deletes the two 0-size objects, and keep only the ones that hold data.

        Parameters
        ----------
        job_id : str
            A string representation of job_id

        wait: bool, optional
            The given `job_id` may not be completed yet, so you have the option to wait for it to completed first.

            Default is False

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
        job_status = job_details.get("status")

        if wait is True:
            job_status = self.wait_for_job(jobId)

        if job_status == "running":
            raise ValueError(
                "SQL job with jobId {} still running. Come back later.".format(jobId)
            )
        elif job_status != "completed":
            raise ValueError(
                "SQL job with jobId {} did not finish successfully. No result available.".format(
                    jobId
                )
            )

        if (
            "resultset_location" not in job_details
            or job_details["resultset_location"] is None
        ):
            return None
        url_parsed = self.analyze_cos_url(job_details["resultset_location"])
        cos_client = self._get_cos_client(url_parsed.endpoint)

        result_objects = self.list_results(jobId)

        if len(result_objects) > 3:
            raise ValueError(
                "Renaming partitioned results of jobId {} to single exact result object name not supported.".format(
                    jobId
                )
            )
        if (
            len(result_objects) == 3
            and (int(result_objects.Size[0]) != 0 or int(result_objects.Size[1]) != 0)
        ) or len(result_objects) < 3:
            raise ValueError(
                "Results of job_id {} don't seem to be regular SQL query output.".format(
                    jobId
                )
            )

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
                "Results of job_id {} don't seem to be regular SQL query output.".format(
                    jobId
                )
            )

        if len(result_objects) == 3:
            # basically copy the object[2] to object[0]
            # then delete object[2] and object[1]
            copy_source = result_objects.Bucket[2] + "/" + result_objects.Object[2]
            cos_client.copy_object(
                Bucket=result_objects.Bucket[0],
                CopySource=copy_source,
                Key=result_objects.Object[0],
            )
            cos_client.delete_object(
                Bucket=result_objects.Bucket[2], Key=result_objects.Object[2]
            )
            cos_client.delete_object(
                Bucket=result_objects.Bucket[1], Key=result_objects.Object[1]
            )
        else:  # len(result_objects) == 2
            cos_client.delete_object(
                Bucket=result_objects.Bucket[0], Key=result_objects.Object[0]
            )
        return

    def rename_exact_result_joblist(self, job_list, wait=False):
        """ The bulk mode of `rename_exact_result` method.

        Parameters
        ----------
        job_list: list
            A list of job_id
        wait: bool, optional
            The same meaning as the one used in :meth:`.rename_exact_result`

        """
        for job_id in job_list:
            self.rename_exact_result(job_id, wait=wait)

    def delete_result(self, jobId):
        """
        Delete the COS objects created by a given job-id

        Returns
        -------
        dataframe
            A dataframe, with 3 rows, and one field name "Deleted Object"

        Examples
        --------
        Delete 3 entries in the output COS

        .. code-block:: console

            cos://<cos-name>/bucket_name/jobid=<JOB-ID-NUMBER>/
            cos://<cos-name>/bucket_name/jobid=<JOB-ID-NUMBER>/_SUCCESS
            cos://<cos-name>/bucket_name/jobid=<JOB-ID-NUMBER>/[parquet|csv|json]

        Notes
        -----

        * The last entry holds the real data, and the last word also indicates the data format
        * 'JOBPREFIX NONE'  would avoid having 'jobid=JOB-ID-NAME' in the URL

        """
        self.logon()

        job_details = self.get_job(jobId)
        if job_details["status"] == "running":
            raise ValueError("SQL job with jobId {} still running. Come back later.")
        elif job_details["status"] != "completed":
            raise ValueError(
                "SQL job with jobId {} did not finish successfully. No result available."
            )

        if "resultset_location" not in job_details:
            return None
        result_location = job_details["resultset_location"]
        url_parsed = self.analyze_cos_url(result_location)
        bucket_name = url_parsed.bucket
        bucket_objects_df = self.list_cos_objects(result_location)[["Object"]]
        if bucket_objects_df.empty:
            print("There are no result objects for the jobid {}".format(jobId))
            return
        bucket_objects_df = bucket_objects_df.rename(columns={"Object": "Key"})
        bucket_objects = bucket_objects_df.to_dict("records")

        cos_client = self._get_cos_client(url_parsed.endpoint)

        response = cos_client.delete_objects(
            Bucket=bucket_name, Delete={"Objects": bucket_objects}
        )

        deleted_list_df = pd.DataFrame(columns=["Deleted Object"])
        for deleted_object in response["Deleted"]:
            deleted_list_df = deleted_list_df.append(
                [{"Deleted Object": deleted_object["Key"]}],
                ignore_index=True,
                sort=False,
            )

        return deleted_list_df

    def get_job(self, jobId):
        """
        Return the details of the job-id

        Returns
        -------
        dict
            a dict of job details (see keys below)

        Raises
        ----------
        ValueError
            when jobId is not correct
        HTTPError
            when RestAPI request fails
        JSONDEcodeError
            when RestAPI returns a non-JSON compliant result

        Notes
        -----

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

        Examples
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
                    "https://{}/v2/sql_jobs/{}?instance_crn={}".format(
                        self.api_hostname, jobId, self.instance_crn
                    ),
                    headers=self.request_headers,
                )
            except HTTPError as e:
                if e.response.status_code == 404:
                    raise ValueError("SQL jobId {} unknown".format(jobId))
                else:
                    raise e

            return response.json()

        if len(jobId) == 0:
            msg = "Invalid job_id: {}".format(jobId)
            raise ValueError(msg)

        job_id = jobId
        if (
            job_id in self.jobs_tracking
            and self.jobs_tracking[job_id].get("status") != "running"
            and self.jobs_tracking[job_id].get("status") != "queued"
        ):
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

        Exceptions
        ----------
        SqlQueryFailException: when a job list can't be queried


        Examples
        --------
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

            job_id	status	user_id	statement	resultset_location	submit_time	end_time	 ...
            <long-string> completed	<email-here>	<query-string> 	<cos-url-result-location> 2020-02-21T16:19:03.638Z	2020-02-21T16:19:13.691Z

            rows_read	rows_returned	bytes_read	error	error_message
            1760	29	41499	None	None

        Notes
        -----
            * get_jobs() is used by `export_job_history`(cos_out_url) which is used to save such data
        """
        self.logon()

        response = requests.get(
            "https://{}/v2/sql_jobs?instance_crn={}".format(
                self.api_hostname, self.instance_crn
            ),
            headers=self.request_headers,
        )
        if response.status_code == 200 or response.status_code == 201:
            job_list = response.json()
            job_list_df = pd.DataFrame(
                columns=[
                    "job_id",
                    "status",
                    "user_id",
                    "statement",
                    "resultset_location",
                    "submit_time",
                    "end_time",
                    "rows_read",
                    "rows_returned",
                    "bytes_read",
                    "objects_skipped",
                    "objects_qualified",
                    "error",
                    "error_message",
                ]
            )
            for job in job_list["jobs"]:
                response = requests.get(
                    "https://{}/v2/sql_jobs/{}?instance_crn={}".format(
                        self.api_hostname, job["job_id"], self.instance_crn
                    ),
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
                    objects_skipped = None
                    objects_qualified = None
                    end_time = ""
                    if "error" in job_details:
                        error = job_details["error"]
                    if "end_time" in job_details:
                        end_time = job_details["end_time"]
                    if "error_message" in job_details:
                        error_message = job_details["error_message"]
                    if "rows_read" in job_details:
                        rows_read = job_details["rows_read"]
                    if "rows_returned" in job_details:
                        rows_returned = job_details["rows_returned"]
                    if "bytes_read" in job_details:
                        bytes_read = job_details["bytes_read"]
                    if "objects_skipped" in job_details:
                        objects_skipped = job_details["objects_skipped"]
                    if "objects_qualified" in job_details:
                        objects_qualified = job_details["objects_qualified"]
                    resultset_loc = np.NaN
                    if "resultset_location" in job_details:
                        resultset_loc = job_details["resultset_location"]
                    job_list_df = job_list_df.append(
                        [
                            {
                                "job_id": job["job_id"],
                                "status": job_details["status"],
                                "user_id": job_details["user_id"],
                                "statement": job_details["statement"],
                                "resultset_location": resultset_loc,
                                "submit_time": job_details["submit_time"],
                                "end_time": end_time,
                                "rows_read": rows_read,
                                "rows_returned": rows_returned,
                                "bytes_read": bytes_read,
                                "objects_skipped": objects_skipped,
                                "objects_qualified": objects_qualified,
                                "error": error,
                                "error_message": error_message,
                            }
                        ],
                        ignore_index=True,
                        sort=False,
                    )
                else:
                    print(
                        "Job details retrieval for jobId {} failed with http code {}".format(
                            job["job_id"], response.status_code
                        )
                    )
                    break
        else:
            msg = "Job list retrieval failed with http code {}".format(
                response.status_code
            )
            raise SqlQueryFailException(msg)
        return job_list_df

    @validate_job_status
    def get_jobs_with_status(self, job_id_list, status):
        """ return the list of job_id, among those provided, that have the given status

        Parameters
        ----------
        job_id_list: list
            List of job_id to check
        status : str
            "completed", "running", or "failed"

        Returns
        --------
        list:
            List of job ids
        """
        results = []
        for job_id in job_id_list:
            response = self.get_job(job_id)
            if response["status"] == status:
                results.append(job_id)
        return results

    @validate_job_status
    def get_jobs_count_with_status(self, status):
        """ return the number of jobs in the SQL Query server for the given `status`

        It has the limitation as described in :meth:`.get_jobs`
        """
        jobs = self.get_jobs()
        num_jobs = len(jobs[jobs["status"] == status])
        return num_jobs

    def get_number_running_jobs(self):
        """ return the number of running jobs in the SQL Query server"""
        return self.get_jobs_count_with_status("running")

    def execute_sql(self, sql_stmt, pagesize=None, get_result=False):
        """
        Extend the behavior of :meth:`.run_sql`.
        It is a blocking call that waits for the job to finish (unlike :meth:`.submit_sql`), but it has the following features:

        1. returning of data (Pandas dataframe) is optional (controlled by `get_result` parameter): to help avoiding Python runtime memory overload.
            This is also useful when you run SQL statements such as DDLs that don't produce results at all.
        2. returns a namedtuple, in that result.data is the one returned by `run_sql`, while result.job_id is the one returned by `submit_sql`
        3. raise an exception for a failed job

        Parameters
        --------------
        sql_stmt: str
            the SQL statement to run

        pagesize: int, optional
            an integer indicating the number of rows for each partition/page [using PARTITIONED EVERY <pagesize> ROWS syntax]

        get_result: bool, optional (default=False)
            When set it will return only the job_id, but still wait for the job's completion.
            Later, you can get the data using :meth:`.get_result` (job_id, pagenumber)

        Returns
        -------
        namedtuple [`data`, `job_id`]
            `get_result` = True, then behavior like :meth:`.run_sql` which materializes the returned data as type
             pd.DataFrame in memory. The default behavior is opposite, to avoid unintended overload of memory.

        Raises
        ------
        KeyError
            when information about a failed job is missing (job_status, job_id, error, error_message)
        SqlQueryFailException
            when the sql query fails, e.g. time out on the server side

        """
        Container = namedtuple("RunSql", ["data", "job_id"])

        job_id = self.submit_sql(sql_stmt, pagesize=pagesize)
        data = None
        job_status = self.wait_for_job(job_id)
        logger.debug("Job " + job_id + " terminated with status: " + job_status)
        if job_status == "completed":
            if get_result is True:
                data = self.get_result(job_id)
        elif job_status == "unknown":
            job_status = self.wait_for_job(job_id)

        if job_status == "failed":
            details = self.get_job(job_id)
            try:
                error_message = "{status}: SQL job {job_id} failed while executing with error {error}. Detailed message: {msg}".format(
                    status=job_status,
                    job_id=job_id,
                    error=details["error"],
                    msg=details["error_message"],
                )
                raise SqlQueryFailException(error_message)
            except KeyError as e:
                pprint.pprint(details)
                raise e
        mycontainer = Container(data, job_id)
        return mycontainer

    def run_sql(self, sql_text, pagesize=None):
        """
        Submits a SQL job, waits for the job to finish (unlike :meth:`.submit_sql`) and return the result as Pandas DataFrame.

        Parameters
        --------------
        sql_text: str
            the SQL statement to run

        pagesize: int, optional
            an integer indicating the number of rows for each partition/page [using PARTITIONED EVERY <pagesize> ROWS syntax]

        Returns
        -------
            pd.DataFrame with the query results.

        Raises
        ------
        CosUrlNotFoundException
            the COS URL is not valid
        CosUrlInaccessibleException
            the COS URL is inaccessible - no access granted to the given API key
        SqlQueryInvalidFormatException
            the format provided to COS URL is incorrect
        KeyError
            the returned error message does not have job_id, error, or error_message
        Exception
            unexpected exception


        """
        self.logon()
        job_id = self.submit_sql(sql_text, pagesize)
        job_status = self.wait_for_job(job_id)
        if job_status == "failed":
            details = self.get_job(job_id)
            try:
                error_message = "SQL job {job_id} failed while executing \n{sql_text}\nwith error {error}. Detailed message: {msg}".format(
                    job_id=job_id,
                    sql_text=sql_text,
                    error=details["error"],
                    msg=details["error_message"],
                )
                cos_in_url_error_msg = "Specify a valid Cloud Object Storage location"
                cos_out_url_error_msg = (
                    "Specify a valid Cloud Object Storage bucket location"
                )
                cos_url_not_accessible_error_msg = "Accessing the specified Cloud Object Storage location is forbidden."
                cos_invalid_format_error_msg = "The input data doesn't have a correct"
                if cos_in_url_error_msg in error_message:
                    raise CosUrlNotFoundException(error_message)
                elif cos_out_url_error_msg in error_message:
                    raise CosUrlNotFoundException(error_message)
                elif cos_url_not_accessible_error_msg in error_message:
                    raise CosUrlInaccessibleException(error_message)
                elif cos_invalid_format_error_msg in error_message:
                    raise SqlQueryInvalidFormatException(error_message)
                else:
                    raise Exception(error_message)
            except KeyError as e:
                pprint.pprint(details)
                raise e
        return self.get_result(job_id)

    def run(self, pagesize=None, get_result=False):
        """ run the internal SQL statement provided by SQLMagic using :meth:`.execute_sql`
        """
        self.format_()
        return self.execute_sql(
            self._sql_stmt, pagesize=pagesize, get_result=get_result
        )

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
                        job_result["end_time"]
                    ) - dateutil.parser.parse(job_result["submit_time"])
                    job_time = delta.total_seconds()
                    if job_time < 2400:  # 40 minutes
                        new_job_id = self.submit_sql(job_result["statement"])
                        job_id_list[index] = new_job_id
                        complete_all = False
        return job_id_list

    def sql_ui_link(self):
        """ both print out and also return the string containing SQL Query URL"""
        self.logon()

        if sys.version_info >= (3, 0):
            result = "https://{}/sqlquery/?instance_crn={}".format(
                self.ui_hostname, urllib.parse.unquote(self.instance_crn)
            )
        else:
            result = "https://{}/sqlquery/?instance_crn={}".format(
                self.ui_hostname, urllib.unquote(self.instance_crn).decode("utf8")
            )
        print(result)
        return result

    def export_job_history(
        self,
        cos_url=None,
        export_file_prefix="job_export_",
        export_file_suffix=".parquet",
    ):
        """
        Export the most recent jobs to COS URL

        Parameters
        ----------
        cos_url : str
            A COS URL with prefix, i.e. cos://<cos-name>/<bucket>/<prefix>,
            where the data will be stored

        Raises
        ------
        ValueError
            if COS URL is invalid
        """
        if cos_url:
            # Default export location is target COS URL set at __init__
            # But we'll overwrite that with the provided export URL
            if not self.is_valid_cos_url(cos_url):
                msg = "Not a valid COS URL"
                raise ValueError(msg)
            self.export_cos_url = cos_url
        elif not self.export_cos_url:
            raise ValueError("No configured export COS URL.")
        if not self.export_cos_url.endswith("/"):
            self.export_cos_url += "/"
        url_parsed = self.analyze_cos_url(self.export_cos_url)

        job_history_df = (
            self.get_jobs()
        )  # Retrieve current job history (most recent 30 jobs)
        if sys.version_info < (3, 0):
            job_history_df["error"] = job_history_df["error"].astype(unicode)
            job_history_df["error_message"] = job_history_df["error_message"].astype(
                unicode
            )
        terminated_job_history_df = job_history_df[
            job_history_df["status"].isin(["completed", "failed"])
        ]  # Only export terminated jobs
        newest_job_end_time = terminated_job_history_df.loc[
            pd.to_datetime(terminated_job_history_df["end_time"]).idxmax()
        ].end_time

        # List all existing objects in export location and identify latest exported job timestamp:
        cos_client = self._get_cos_client(url_parsed.endpoint)
        paginator = cos_client.get_paginator("list_objects")
        page_iterator = paginator.paginate(
            Bucket=url_parsed.bucket, Prefix=url_parsed.prefix
        )
        newest_exported_job_end_time = ""
        expected_object_prefix = url_parsed.prefix + export_file_prefix
        for page in page_iterator:
            if "Contents" in page:
                for key in page["Contents"]:
                    object_name = key["Key"]
                    if not (object_name.startswith(expected_object_prefix)):
                        continue
                    prefix_end_index = len(expected_object_prefix)
                    suffix_index = object_name.find(export_file_suffix)
                    if not (prefix_end_index < suffix_index):
                        continue
                    job_end_time = object_name[prefix_end_index:suffix_index]
                    if job_end_time > newest_exported_job_end_time:
                        newest_exported_job_end_time = job_end_time

        # Export all new jobs if there are some:
        if newest_exported_job_end_time < newest_job_end_time:
            import pyarrow
            from packaging import version

            tmpfile = tempfile.NamedTemporaryFile()
            tempfilename = tmpfile.name
            new_jobs_df = terminated_job_history_df[
                terminated_job_history_df["end_time"] > newest_exported_job_end_time
            ]
            if version.parse(pd.__version__) >= version.parse("1.0.0"):
                new_jobs_df.to_parquet(
                    engine="pyarrow",
                    path=tempfilename,
                    compression="snappy",
                    index=False,
                )
            else:
                new_jobs_df.to_parquet(
                    engine="pyarrow",
                    fname=tempfilename,
                    compression="snappy",
                    index=False,
                )
            export_object = (
                url_parsed.prefix
                + export_file_prefix
                + newest_job_end_time
                + export_file_suffix
            )
            cos_client.upload_file(
                Bucket=url_parsed.bucket, Filename=tempfilename, Key=export_object
            )
            print("Exported {} new jobs".format(new_jobs_df["job_id"].count()))
            tmpfile.close()
        else:
            print("No new jobs to export")

    def get_schema_data(self, cos_url, type="json", dry_run=False):
        """
        Return the schema of COS URL

        Parameters
        ----------
        cos_url : str
            The COS URL where data is stored
        type : str, optional
            The format type of the data, default is 'json'
            Use from ['json', 'csv', 'parquet'] with case-insensitive
        dry_run: bool, optional
            This option, once selected as True, returns the internally generated SQL statement, and no job is queried.

        Returns
        -------
        DataFrame
            3 columns: name (object), nullable (bool), type (object)

        Raises
        -------
        ValueError
            in either scenarios: (1) target COS URL is not set, (2) invalid type, (3) invalid COS URL

        """
        supported_types = ["JSON", "CSV", "PARQUET"]

        if self.target_cos_url is None:
            msg = "Need to pass target COS URL when creating SQL Client object"
            raise ValueError(msg)
        if type.upper() not in supported_types:
            msg = "Expected 'type' value: " + str(supported_types)
            raise ValueError(msg)
        if not self.is_valid_cos_url(cos_url):
            msg = "Not a valid COS URL"
            raise ValueError(msg)
        sql_stmt = """
        SELECT * FROM DESCRIBE({cos_in} STORED AS {type})
        INTO {cos_out} STORED AS JSON
        """.format(
            cos_in=cos_url, type=type.upper(), cos_out=self.target_cos_url
        )
        if dry_run:
            print(sql_stmt)
            return None
        else:
            df = self.run_sql(sql_stmt)
            if (df.name[0] == "_corrupt_record") or (
                "�]�]L�" in df.name[0] and "PAR1" in df.name[0]
            ):
                msg = (
                    "ERROR: Revise 'type' value, underlying data format maybe different"
                )
                raise ValueError(msg)
            return df

    def analyze(self, job_id, print_msg=True):
        """Provides some insights about the data layout from the current SQL statement

        Parameters
        -------------
        job_id : str
            The job ID

        print_msg: bool, optional
            Default is True: print out the hints to the console

        .. todo::

            1. new sql only when max_obj_size > 300MB
            2. check if STORED AS is used, if not suggested adding to sql with PARQUET or JSON
            3. add PARITIONED ... not at the end, but right after STORED AS (which can be missing in original SQL)
        """

        def INTO_is_present(sql_text):
            """ check if INTO keyword is present in the SQL query"""
            return (" INTO " in sql_text.upper()) or ("\nINTO " in sql_text.upper())

        BestPracticeContainer = namedtuple("SqlBestPractice", ["size", "max_objs"])
        best_practice = BestPracticeContainer("128 MB", 50)

        result = self.get_job(job_id)
        # make use of 'resultset_location' and 'resultset_format'
        if not INTO_is_present(result["statement"]):
            cos_out = result["resultset_location"]
            if "jobid=" in result["resultset_location"]:
                cos_out = cos_out[: cos_out.rfind("jobid=")]
            result["statement"] += (
                " INTO " + cos_out + " STORED AS " + result["resultset_format"]
            )
        if result["status"] != "completed":
            msg = "Job {job_id} is {status} - no more insights".format(
                job_id=job_id, status=result["status"]
            )
            return msg

        cos_url = result["resultset_location"]
        if not cos_url:
            msg = "Job {job_id} does not return anything - no more insights".format(
                job_id=job_id
            )
            return msg

        cos_result = self.get_cos_summary(cos_url)

        def get_total_objects():
            # total_objects = cos_result['total_objects']  #not exact
            r = self.list_results(job_id)
            seriesObj = r.apply(lambda x: True if int(x["Size"]) > 0 else False, axis=1)
            return seriesObj.to_list().count(True)

        total_objects = get_total_objects()

        def get_size_in_MB(size_info):
            num, unit = size_info.split(" ")
            mapping = {"TB": 1048576, "GB": 1024, "MB": 1}

            if unit in mapping:
                size_MB = float(num) * mapping[unit]
            else:
                size_MB = 1.0
            return size_MB

        largest_size_MB = get_size_in_MB(cos_result["largest_object_size"])

        if largest_size_MB < float(best_practice.size.split(" ")[0]) * 2:
            msg = "Job {job_id} looks fine - no more insights".format(job_id=job_id)
            return msg

        total_volume_MB = get_size_in_MB(cos_result["total_volume"])
        SqlContainer = namedtuple(
            "SqlStatus",
            ["job_id", "total_data_objects", "total_volume", "max_object_size"],
        )
        query = SqlContainer(job_id, total_objects, total_volume_MB, largest_size_MB)
        mappings = {
            "job_id": job_id,
            "total_objects": total_objects,
            "total_volume_MB": total_volume_MB,
        }
        msg_01 = "Job {job_id} has {total_objects} object{s}, with {total_volume_MB} MB in total.".format(
            **mappings, s="s" if mappings["total_objects"] > 1 else ""
        )
        if mappings["total_objects"] > 1:
            msg_01 = msg_01 + " Current object size is ~ {size} MB".format(
                size=mappings["total_volume_MB"] / mappings["total_objects"]
            )

        mappings = {"size": best_practice.size}
        msg_02 = "Best practices: object sizes ~ {size}".format(**mappings)

        mappings = {
            "num_objs": min(
                best_practice.max_objs,
                int(query.total_volume / float(best_practice.size.split(" ")[0])),
            )
        }

        msg_03 = "Current SQL:\n {sql}\n".format(sql=result["statement"])

        def revise_storage(sql_stmt, storage="parquet"):
            url_storage = re.search(r"INTO (cos)://[^\s]* STORED AS", sql_stmt)
            if url_storage:
                loc = url_storage.span(0)[1]
                pre = sql_stmt[: loc + 1]
                post = sql_stmt[loc + 1 :]
                detected_storage = re.search(r"^[^\s]*", post).group(0)
                if storage.upper() != detected_storage:
                    post = post.replace(detected_storage, storage.upper(), 1)
                sql_stmt = pre + post
            else:
                url = re.search(r"INTO (cos)://[^\s]*", sql_stmt)
                if url:
                    loc = url.span(0)[1]
                    sql_stmt = (
                        sql_stmt[:loc]
                        + " STORED AS  "
                        + storage.upper()
                        + sql_stmt[loc + 1 :]
                    )
                else:
                    # no explicit INTO
                    msg = "Error: needs INTO <cos-url> clause"
                    raise Exception(msg)
            return sql_stmt

        def msg_partition_into():
            msg_sub = [None] * 2
            msg_sub[
                0
            ] = "Consider using: PARTITIONED INTO {num_objs} OBJECTS/BUCKETS".format(
                **mappings
            )

            new_sql = result["statement"]
            if "PARTITION" not in new_sql:
                new_sql = format_sql(revise_storage(new_sql, "parquet"))
                import re

                url = re.search(
                    r"INTO (cos)://[^\s]*[\s]+STORED[\s]+AS[\s]+PARQUET", new_sql
                )
                loc = url.span(0)[1]
                new_sql = (
                    new_sql[:loc]
                    + " PARTITIONED INTO {num_objs} OBJECTS".format(**mappings)
                    + new_sql[loc + 1 :]
                )

            result["rows_returned"]
            msg_sub[1] = "Suggested SQL:\n {sql}\n".format(sql=new_sql)
            return msg_sub

        def msg_partition_every():
            msg_05 = [None] * 2
            num_rows = int(
                float(result["rows_returned"])
                / (query.total_volume / float(best_practice.size.split(" ")[0]))
            )
            msg_05[0] = "Consider using: PARTITIONED EVERY {num_rows} ROWS".format(
                **mappings, num_rows=num_rows
            )

            new_sql = result["statement"]
            if "PARITION" not in new_sql:
                # new_sql = new_sql + " PARTITIONED EVERY {num_rows} ROWS".format(
                #    **mappings, num_rows=num_rows)
                new_sql = format_sql(revise_storage(new_sql, "parquet"))
                url = re.search(
                    r"INTO (cos)://[^\s]*[\s]+STORED[\s]+AS[\s]+PARQUET", new_sql
                )
                loc = url.span(0)[1]
                new_sql = (
                    new_sql[:loc]
                    + " PARTITIONED EVERY {num_rows} ROWS".format(
                        **mappings, num_rows=num_rows
                    )
                    + new_sql[loc + 1 :]
                )
            result["rows_returned"]
            msg_05[1] = "Suggested SQL:\n {sql}\n".format(sql=new_sql)
            return msg_05

        msg_04 = msg_partition_into()
        msg_05 = msg_partition_every()
        my_list = [msg_01, msg_02, msg_03]
        my_list.extend(msg_04)
        my_list.extend(msg_05)
        msg = os.linesep.join(my_list)

        if print_msg:
            print(msg)

        return msg
