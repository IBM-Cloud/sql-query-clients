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

import ibmcloudsql
import ibm_boto3
from ibm_botocore.client import Config
import xml.etree.ElementTree as ET
import pandas as pd
import getpass
import time
from datetime import datetime
import requests
from pprint import pformat
from collections import namedtuple
try:
    from exceptions import RateLimitedException
except Exception:
    from .exceptions import RateLimitedException
try:
    from utilities import IBMCloudAccess
except Exception:
    from .utilities import IBMCloudAccess
from requests.exceptions import HTTPError
import json
import logging
logger = logging.getLogger(__name__)


# ------------------------------------------------------------------------------
# Helper class to interact with IBM Watson Studio projects
# ------------------------------------------------------------------------------
class ProjectLib():
    """
    This is used by SQLClient/COSClient via :py:meth:`read` and :py:meth:`write` methods

    Parameters
    ----------
    project: project_lib.Project
        The object

            `from project_lib import Project`
    file_name: str
        The file_name where the data about SQL queries' jobs should be read/stored

        The content of this file is used to track progress

    file_type: str, optional
        The file format of `file_name`

    .. todo::

        NOTE: Currently support only one file

        To support many files, we can switch to using dict such as self._data_out[file_name]
    """
    def __init__(self, project, file_name, file_type="json"):
        self._project = project
        self._target_filename = None
        self._file_type = None
        self._track_file(file_name, file_type)
        self._data_out = None

    def _track_file(self, filename, file_type):
        """ map to real file name """
        assert (file_type in ["json", "csv"])
        self._file_type = file_type
        self._target_filename = filename
        if not filename.endswith((".json", ".csv")):
            self._target_filename = self._target_filename + "." + file_type
        return self._target_filename

    @property
    def data(self):
        """ file-like object: storing the file-content """
        return self._data_out

    @property
    def project(self):
        """ Project: the project-lib object"""
        return self._project

    def read(self, file_name=None, file_type="json"):
        """
        Read from project-lib's file into file-like object

        Parameters
        ----------
        file_name: str, optional
            File name in the Watson Studio's project assets. If the file is not provided, then it reads the one passed into the object's constructor.

        file_type: str, optional
            The type of file, "json" or "csv"

        Returns
        -------
        file-like object:
            The content of the data, in dict (json) or pd.DataFrame (csv)
        """
        if file_name is None:
            file_name = self._target_filename
        # Fetch the file
        file_is_found = False
        if self._data_out is None:
            filename_list = self._project.get_files()
            for x in filename_list:
                if x["name"] == file_name:
                    file_is_found = True
                    file_content = self._project.get_file(file_name)
                    if file_type == "json":
                        # Read the CSV data file from the object storage into a pandas DataFrame
                        file_content.seek(0)
                        # import pandas as pd
                        # pd.read_json(my_file, nrows=10)
                        import json
                        self._data_out = json.load(file_content)
                    elif file_type == "csv":
                        # Read the CSV data file from the object storage into a pandas DataFrame
                        file_content.seek(0)
                        import pandas as pd
                        self._data_out = pd.read_csv(file_content, nrows=10)
        if file_is_found == False:
            if file_type == "json":
                self._data_out = dict()
            elif file_type == "csv":
                self._data_out = pd.DataFrame()
        return self._data_out

    def write(self, file_name=None, file_type="json"):
        """
        Write the file-like data back to project-lib's file

        Parameters
        ----------
        file_name: str
            File name
        file_type: str, optional
            The type of file, "json" or "csv"

        Returns
        ------
        dict

        Examples
        --------

        .. code-block:: python

            {'asset_id': '1deebaad-8ad3-4861-8c52-e714d8eef2a9',
            'bucket_name': 'projectlib351fb93e171c44369663ff79b938828d',
            'file_name': 'iris1.csv',
            'message': 'File iris1.csv has been written successfully to the associated OS'}

        """
        if file_name is None:
            file_name = self._target_filename
        else:
            file_name = self._track_file(file_name, file_type)
        if file_type == "json":
            out = json.dumps(self._data_out)
            result = self._project.save_data(file_name,
                                             out,
                                             set_project_asset=True,
                                             overwrite=True)
        elif file_type == "csv":
            out = self._data_out.to_csv(index=False)
            result = self._project.save_data(file_name,
                                             out,
                                             set_project_asset=True,
                                             overwrite=True)
        return result


# ---------------------------------------------------------------------------------------------
# Helper class to do client-side mapping of COS endpoints to aliases supported in SQL Query
# ---------------------------------------------------------------------------------------------
class ParsedUrl(object):
    """Use this class to extract information from COS URL

        `cos://<cos-name>/<bucket>/<prefix>/`
    """
    def __init__(self):
        """

        Endpoints to change:
        https://cloud.ibm.com/docs/cloud-object-storage?topic=cloud-object-storage-migrate-data-center
        """
        self.endpoint_alias_mapping = {
            "us-geo": "s3-api.us-geo.objectstorage.softlayer.net",
            "us": "s3-api.us-geo.objectstorage.softlayer.net",
            "dal-us-geo": "s3-api.dal-us-geo.objectstorage.softlayer.net",
            "wdc-us-geo": "s3-api.wdc-us-geo.objectstorage.softlayer.net",
            "sjc-us-geo": "s3-api.sjc-us-geo.objectstorage.softlayer.net",
            "eu-geo": "s3.eu-geo.objectstorage.softlayer.net",
            "eu": "s3.eu-geo.objectstorage.softlayer.net",
            "ams-eu-geo": "s3.ams-eu-geo.objectstorage.softlayer.net",
            "fra-eu-geo": "s3.fra-eu-geo.objectstorage.softlayer.net",
            "mil-eu-geo": "s3.mil-eu-geo.objectstorage.softlayer.net",
            "us-south": "s3.us-south.objectstorage.softlayer.net",
            "us-east": "s3.us-east.objectstorage.softlayer.net",
            "jp-tok": "s3.jp-tok.objectstorage.softlayer.net",
            "ap-geo": "s3.ap-geo.objectstorage.softlayer.net",
            "ap": "s3.ap-geo.objectstorage.softlayer.net",
            "tok-ap-geo": "s3.tok-ap-geo.objectstorage.softlayer.net",
            "seo-ap-geo": "s3.seo-ap-geo.objectstorage.softlayer.net",
            "hkg-ap-geo": "s3.hkg-ap-geo.objectstorage.softlayer.net",
            "eu-de": "s3.eu-de.objectstorage.softlayer.net",
            "eu-gb": "s3.eu-gb.objectstorage.softlayer.net",
            "ams03": "s3.ams03.objectstorage.softlayer.net",
            "che01": "s3.che01.objectstorage.softlayer.net",
            "mel01": "s3.mel01.objectstorage.softlayer.net",
            "tor01": "s3.tor01.objectstorage.softlayer.net",
            "mon01": "s3.mon01.objectstorage.softlayer.net",
            "osl01": "s3.osl01.objectstorage.softlayer.net",
            "sao01": "s3.sao01.objectstorage.softlayer.net",
            "seo01": "s3.seo01.objectstorage.softlayer.net"
        }
        # https://cloud.ibm.com/docs/cloud-object-storage?topic=cloud-object-storage-endpoints
        self._dedicated_endpoints = [
                "s3.us-south.cloud-object-storage.appdomain.cloud",
                "s3.us-east.cloud-object-storage.appdomain.cloud",
                "s3.eu-gb.cloud-object-storage.appdomain.cloud",
                "s3.eu-de.cloud-object-storage.appdomain.cloud",
                "s3.au-syd.cloud-object-storage.appdomain.cloud",
                "s3.jp-tok.cloud-object-storage.appdomain.cloud",
                # cross-region
                "s3.us.cloud-object-storage.appdomain.cloud",
                "s3.eu.cloud-object-storage.appdomain.cloud",
                "s3.ap.cloud-object-storage.appdomain.cloud",
                # single DC
                "s3.ams03.cloud-object-storage.appdomain.cloud",
                "s3.che01.cloud-object-storage.appdomain.cloud",
                "s3.hkg02.cloud-object-storage.appdomain.cloud",
                "s3.mex01.cloud-object-storage.appdomain.cloud",
                "s3.mil01.cloud-object-storage.appdomain.cloud",
                "s3.mon01.cloud-object-storage.appdomain.cloud",
                "s3.osl01.cloud-object-storage.appdomain.cloud",
                "s3.par01.cloud-object-storage.appdomain.cloud",
                "s3.sjc04.cloud-object-storage.appdomain.cloud",
                "s3.sao01.cloud-object-storage.appdomain.cloud",
                "s3.seo01.cloud-object-storage.appdomain.cloud",
                "s3.sng01.cloud-object-storage.appdomain.cloud",
                "s3.tor01.cloud-object-storage.appdomain.cloud"
                ]
        self.endpoint = None
        self.bucket = None
        self.prefix = None

    def get_exact_url(self, cos_url):
        """Convert COS URL from using alias to exact URL"""
        key = cos_url.split("/")[2]
        x = cos_url.replace(key, self.endpoint_alias_mapping.get(key, key), 1)
        return x

    def get_endpoint(self, cos_url):
        """ Return the endpoint string from COS URL"""
        self.endpoint = cos_url.split("/")[2]
        self.endpoint = self.endpoint_alias_mapping.get(
            self.endpoint, self.endpoint)
        return self.endpoint

    def get_bucket(self, cos_url):
        """ Return the bucket name from COS URL"""
        self.bucket = cos_url.split("/")[3]
        return self.bucket

    def get_prefix(self, cos_url):
        """ Return the prefix part from COS URL"""
        self.prefix = cos_url[cos_url.replace('/', 'X', 3).find('/') + 1:]
        if len(self.prefix) > 0 and self.prefix[-1] == '*':
            self.prefix = self.prefix[:-1]
            self.fourth_slash = cos_url.replace('/', 'X', 3).find('/')
        return self.prefix

    def analyze_cos_url(self, cos_url):
        """ Return a namedtuple containing the 3 fields

        * bucket
        * endpoint
        * prefix

        Parameters
        ----------
        cos_url : str
            COS URL
        """
        nt = namedtuple("COSURL", "endpoint bucket prefix")
        mycontainer = nt(self.get_endpoint(cos_url), self.get_bucket(cos_url),
                         self.get_prefix(cos_url))
        return mycontainer

    def is_valid_cos_url(self, cos_url):
        """ Validate if a string is COS URL

        Returns
        ------
        bool
        """
        origin = str(cos_url)
        cos_url = cos_url.strip()
        if not cos_url.startswith("cos://"):
            return False

        cos_url = cos_url[6:]
        if '/' not in cos_url:
            return False
        if cos_url[-1] != '/':
            cos_url += '/'
        if cos_url.count('/') < 2:
            return False
        endpoint = self.get_endpoint(origin)
        if not endpoint in self.endpoint_alias_mapping.values() and \
        not endpoint in self._dedicated_endpoints:
            return False

        return True


# ---------------------------------------------------------------------------
# Helper class to query information or manipulate data as objects on COS
# which can also be used from SQL Query
# ---------------------------------------------------------------------------
class COSClient(ParsedUrl, IBMCloudAccess):
    """
    This class handles the interaction with IBM COS storage

    Parameters
    ----------
    cloud_apikey : str, optional
        an account-level API key [manage/Access (IAM)/IBM Cloud API keys]

        https://cloud.ibm.com/docs/iam/users_roles.html
        https://cloud.ibm.com/docs/services/cloud-object-storage?topic=cloud-object-storage-getting-started

    cos_url : str, optional
        the COS URL where retrieved data is stored

    client_info : str, optional
        User-defined string

    See also
    ---------

        * https://cloud.ibm.com/apidocs/cos/cos-configuration
        * https://ibm.github.io/ibm-cos-sdk-python/
        * https://cloud.ibm.com/docs/services/cloud-object-storage/iam?topic=cloud-object-storage-service-credentials
    """
    def __init__(self, cloud_apikey="", cos_url="", client_info="COS Client"):
        ParsedUrl.__init__(self)
        IBMCloudAccess.__init__(self,
                                cloud_apikey=cloud_apikey,
                                client_info=client_info)

        if cos_url is not None and len(cos_url) > 0:
            if not self.is_valid_cos_url(cos_url):
                msg = "Not a valid COS URL: {}".format(cos_url)
                raise ValueError(msg)
        self.cos_url = cos_url
        # a dict holding all retrieved bucket's information
        self.buckets_info = {}

        # track Project-Lib object
        self._project = None

    def _get_cos_client(self, endpoint):
        return self._get_default_cos_client(endpoint)

    def _get_default_cos_client(self, endpoint=None):
        '''
        Create a low-level service client of COS from the default session
        '''
        def _get_default_s3_client(endpoint=None):
            '''
            Create a low-level service client of COS from the default session
            '''
            if endpoint is None:
                endpoint = self.endpoint
            assert (endpoint is not None)
            return ibm_boto3.client('s3',
                                    config=Config(signature_version='oauth'),
                                    endpoint_url='https://{}'.format(endpoint))

        return _get_default_s3_client(endpoint)

    def list_cos_objects(self, cos_url):
        """
        List all objects in the current COS URL.

        Parameters
        ------------
        url: str
            A URI prefix. e.g., cos://us-south/<bucket-name>/object_path/

        Returns
        ----------
        pd.DataFrame
            The following columns ("Object", "Size", "StorageClass")

        Notes
        ------
        Having a trailing slash (/) makes a difference in the returned result, as an asterisk is added at the end. So,
        "/prefix" would consider things like "/prefix_unexpected/value" and "/prefix/expected_value"; while
        "/prefix/" only consider "/prefix/expected_value".

        Examples
        ------------
            Only "list_objects' work for IBM COS, not 'list_objects_v2'

            `IBM-COS-SDK <https://ibm.github.io/ibm-cos-sdk-python/reference/services/s3.html#S3.Client.list_objects_v2>`_

        Raises
        -------
        ValueError
            if COS URL is invalid
        """
        if not self.is_valid_cos_url(cos_url):
            msg = "Not a valid COS URL: {}".format(cos_url)
            raise ValueError(msg)
        self.logon()

        cos_url = self.get_exact_url(cos_url)
        url_parsed = self.analyze_cos_url(cos_url)
        cos_client = self._get_default_cos_client(url_parsed.endpoint)
        paginator = cos_client.get_paginator("list_objects")
        page_iterator = paginator.paginate(Bucket=url_parsed.bucket,
                                           Prefix=url_parsed.prefix)

        result = None
        for page in page_iterator:
            if "Contents" in page:
                #print(page['Contents'])
                page_df = pd.DataFrame.from_dict(page['Contents'],
                                                 orient='columns')
                if result is None:
                    result = page_df
                else:
                    result = result.append(page_df, sort=False)
        if result is not None:
            result = result.drop(columns=['ETag', 'Owner']).rename(
                columns={"Key": "Object"})
        else:
            result = pd.DataFrame()
            # result = pd.DataFrame(columns=['Object', 'LastModified', 'Size', 'StorageClass'])
        return result

    def delete_empty_objects(self, cos_url):
        """
        Delete zero-size objects. Reference to :meth:`.list_cos_objects` for further details.

        Raises
        -------
        ValueError
            if COS URL is invalid
        """
        if not self.is_valid_cos_url(cos_url):
            msg = "Not a valid COS URL: {}".format(cos_url)
            raise ValueError(msg)
        result_objects = self.list_cos_objects(cos_url)
        url_parsed = self.analyze_cos_url(cos_url)
        cos_client = self._get_default_cos_client(url_parsed.endpoint)
        bucket = url_parsed.bucket
        max_row_index = len(result_objects)
        for row in range(0, max_row_index):
            if int(result_objects.Size[row]) == 0:
                cos_client.delete_object(Bucket=bucket,
                                         Key=result_objects.Object[row])

    def delete_objects(self, cos_url, dry_run=False):
        """Delete all objects stored at the given COS URL

        https://<cos-url>/<bucket>?prefix=<prefix-path>

        Notes
        ------

        Reference: `AWS doc <https://awsdocs.s3.amazonaws.com/S3/latest/s3-qrc.pdf>`_

        .. code-block:: console

            curl -XGET \
                --url "https://<COS-exact-URL>/<bucket-name>?prefix=<YOUR_PREFIX>"

            https://s3.us-south.objectstorage.softlayer.net/sql-query-cos-access-ts?prefix=aiops/Location=us-south/DC=rgdal10/Year=2020/Month=02/Date=06

            response.content returns a string in XML format
            -----------
            (' response = b\'<?xml version="1.0" encoding="UTF-8" '
            'standalone="yes"?><ListBucketResult ' 'xmlns="http://s3.amazonaws.com/doc/2006-03-01/">
            <Name>sql-query-cos-access-ts</Name>
            <Prefix>aiops/Location=us-south/DC=rgdal10/Year=2020/Month=02/Date=05</Prefix>
            <Marker></Marker>
            <MaxKeys>1000</MaxKeys>
            <Delimiter></Delimiter>
            <IsTruncated>false</IsTruncated>

            --> 0 or more
            <Contents>
                   <Key>aiops/Location=us-south/DC=rgdal10/Year=2020/Month=02/Date=05/Hour=1/part-00066-fd76d4c7-ea0a-40c3-8170-8f281a19ab5f-attempt_20200310232241_0027_m_000066_0.c000.snappy.parquet</Key>
                   <LastModified>2020-03-10T23:26:55.957Z</LastModified>
                   <ETag>&quot;9b9c012a341fe7f4b9988c59cab96757&quot;</ETag>
                   <Size>1771294485</Size>
                   <Owner>
                        <ID>899ab340-5a4d-4ae2-a1f7-5e39299735b4</ID>
                        <DisplayName>899ab340-5a4d-4ae2-a1f7-5e39299735b4</DisplayName></Owner>
                   <StorageClass>STANDARD</StorageClass></Contents>

            </ListBucketResult>\'')

        As the entity tag (ETag) is a hash of the object, we can use it to reliably check whether the object has changed - better
        than just file size and modification date. Sample code to handle `request.response <https://sdbrett.com/BrettsITBlog/2017/03/python-parsing-api-xml-response-data/>`_

        Raises
        -------
        ValueError
            if COS URL is invalid
        """
        if not self.is_valid_cos_url(cos_url):
            msg = "Not a valid COS URL: {}".format(cos_url)
            raise ValueError(msg)
        self.logon()

        print("COS URL: {}\n".format(cos_url))
        cos_url = self.get_exact_url(cos_url)
        result_location = cos_url.replace("cos", "https", 1)
        url_parsed = self.analyze_cos_url(cos_url)

        fourth_slash = result_location.replace('/', 'X', 3).find('/')

        http_string = result_location[:
                                      fourth_slash] + '?prefix=' + result_location[
                                          fourth_slash + 1:]
        response = requests.get(
            http_string,
            headers=self.request_headers,
        )
        if dry_run is True:
            import pprint
            print("http request {}".format(http_string))
            pprint.pprint(" response = {}".format(response.content))

        if response.status_code == 200 or response.status_code == 201:
            ns = {'s3': 'http://s3.amazonaws.com/doc/2006-03-01/'}
            responseBodyXMLroot = ET.fromstring(response.content)
            bucket_name = responseBodyXMLroot.find('s3:Name', ns).text
            bucket_objects = []
            if responseBodyXMLroot.findall('s3:Contents', ns):
                for contents in responseBodyXMLroot.findall('s3:Contents', ns):
                    key = contents.find('s3:Key', ns)
                    bucket_objects.append({'Key': key.text})
            else:
                print(
                    'There are no result objects for the COS URL {url}'.format(
                        url=cos_url))
                return
        else:
            print(
                "Result object listing for COS URL at {} failed with http code {}"
                .format(result_location, response.status_code))
            return

        cos_client = self._get_default_cos_client(url_parsed.endpoint)

        if dry_run is True:
            print(type(cos_client))
            print(cos_client)
            deleted_list_df = pd.DataFrame(columns=['Deleted Object'])
        else:
            response = cos_client.delete_objects(
                Bucket=bucket_name, Delete={'Objects': bucket_objects})

            deleted_list_df = pd.DataFrame(columns=['Deleted Object'])
            for deleted_object in response['Deleted']:
                deleted_list_df = deleted_list_df.append(
                    [{
                        'Deleted Object': deleted_object['Key']
                    }],
                    ignore_index=True,
                    sort=False)

        return deleted_list_df

    def _list_objects(self, cos_url):
        """List all objects from a given COS URL

        TO BE REMOVED

        Arguments:
            cos_url {str} -- The COS URL
        """
        if not self.is_valid_cos_url(cos_url):
            msg = "Not a valid COS URL: {}".format(cos_url)
            raise ValueError(msg)
        self.logon()

        cos_url = self.get_exact_url(cos_url)
        url_parsed = self.analyze_cos_url(cos_url)
        cos_client = self._get_default_cos_client(url_parsed.endpoint)
        paginator = cos_client.get_paginator("list_objects")
        page_iterator = paginator.paginate(Bucket=url_parsed.bucket,
                                           Prefix=url_parsed.prefix)

        result = None
        for page in page_iterator:
            if "Contents" in page:
                #print(page['Contents'])
                page_df = pd.DataFrame.from_dict(page['Contents'],
                                                 orient='columns')
                if result is None:
                    result = page_df
                else:
                    result = result.append(page_df, sort=False)
        if result is not None:
            result = result.drop(columns=['ETag', 'Owner']).rename(
                columns={"Key": "Object"})
        else:
            result = pd.DataFrame()
        return result

    def get_bucket_info(self, cos_url):
        """ Return the information of the given bucket

        Raises
        -------
        ValueError
            if invalid COS URL

        Examples
        --------

        .. code-block:: console

            curl https://config.cloud-object-storage.cloud.ibm.com/v1/b/my-bucket \
            -H 'authorization: bearer <IAM_token>'

        200 status code:

        .. code-block:: python

            {
            "name": "my-new-bucket",
            "crn": "crn:v1:bluemix:public:cloud-object-storage:global:a/ 3bf0d9003abfb5d29761c3e97696b71c:xxxxxxx-6c4f-4a62-a165-696756d63903:bucket:my-new-bucket",
            "service_instance_id": "xxxxxxx-6c4f-4a62-a165-696756d63903",
            "service_instance_crn": "crn:v1:bluemix:public:cloud-object-storage:global:a/3bf0d9003abfb5d29761c3e97696b71c:xxxxxxx-6c4f-4a62-a165-696756d63903::",
            "time_created": "2018-03-26T16:23:36.980Z",
            "time_updated": "2018-10-17T19:29:10.117Z",
            "object_count": 764265234,
            "bytes_used": 28198745752445144
            }

        .. todo::

            https://cloud.ibm.com/apidocs/cos/cos-configuration?code=python
        """
        if not self.is_valid_cos_url(cos_url):
            msg = "Not a valid COS URL: {}".format(cos_url)
            raise ValueError(msg)
        from cos_config.resource_configuration_v1 import ResourceConfigurationV1
        bucket = self.get_bucket(cos_url)

        if bucket in self.buckets_info:
            return self.buckets_info[bucket]
        else:
            client = ResourceConfigurationV1(iam_apikey=self.apikey)
            config = client.get_bucket_config(bucket)
            self.buckets_info[bucket] = config
            return config
        # bucket = ParsedUrl().get_bucket(cos_url)
        # response = requests.get(
        #     "https://config.cloud-object-storage.cloud.ibm.com/v1/b/{bucket}".
        #     format(bucket=bucket),
        #     headers=self.request_headers,
        # )

        # if response.status_code == 200 or response.status_code == 201:
        #     status_response = response.json()
        #     jobStatus = status_response['status']
        #     if jobStatus == 'completed':
        #         break
        #     if jobStatus == 'failed':
        #         print("Job {} has failed".format(jobId))
        #         break
        # else:
        #     print("Job status check failed with http code {}".format(
        #         response.status_code))
        #     break
        # time.sleep(2)

    def _update_bucket(self, cos_url):
        """
        Update the bucket given by COS URL

        .. todo::

           revise this
        """
        if not self.is_valid_cos_url(cos_url):
            msg = "Not a valid COS URL: {}".format(cos_url)
            raise ValueError(msg)
        from cos_config.resource_configuration_v1 import ResourceConfigurationV1

        api_key = self.apikey
        bucket = self.get_bucket(cos_url)

        client = ResourceConfigurationV1(iam_apikey=api_key)

        client.update_bucket_config(
            bucket,
            firewall={"allowed_ip": ["10.142.175.0/22", "10.198.243.79"]})

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
        """
        def sizeof_fmt(num, suffix='B'):
            for unit in ['', 'K', 'M', 'G', 'T', 'P', 'E', 'Z']:
                if abs(num) < 1024.0:
                    return "%3.1f %s%s" % (num, unit, suffix)
                num /= 1024.0
            return "%.1f %s%s" % (num, 'Y', suffix)

        self.logon()

        if url[-1] != '/':
            url = url + '/'
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

    # -----------------
    # The methods below are for interacting with a file stored as an asset in a Watson Studio's Project.
    # -----------------
    def connect_project_lib(self, project, file_name=None):
        """
        Connect to an IBM Watson Studio Project's COS bucket for its own assets

        Parameters
        ----------
        project: Project
            The project-lib object

        file_name: str, optional
            The name of the file in ProjectLib's COS bucket where data will be read/stored
        """
        self._project = ProjectLib(project, file_name)
        if file_name is not None:
            self.read_project_lib_data(file_name)

    def read_project_lib_data(self, file_name=None):
        """Read the content from the given file (via ProjectLib in IBM Watson Studio's COS bucket)

        Parameters
        ----------
        file_name: str, optional
            If not specified, use the one defined from the beginning
        """
        if self._project is None:
            print("Please connect to your ProjectLib object with `connect_project_lib` API")
        else:
            self._project.read(file_name)

    def write_project_lib_data(self, file_name=None):
        """Write the content to the given file (via ProjectLib in IBM Watson Studio's COS bucket)

        Parameters
        ----------
        file_name: str, optional
            If not specified, use the one defined from the beginning
        """
        if self._project is None:
            print("Please connect to your ProjectLib object with `connect_project_lib` API")
        else:
            self._project.write(file_name)

    @property
    def project_lib(self):
        """ Project: IBM Watson Studio ProjectLib object"""
        return self._project

if __name__ == "__main__":
    cos = COSClient()
    cos_url = "cos://us-south/sql-query-cos-access-ts/aiops_test/Location=us-south/DC=rgfra02/Year=2019/Month=10/Date=23/Hour=01/"
    print("From: ", cos_url)
    print("To : ", cos.get_exact_url(cos_url))

    cos_url = "cos://s3.us-south.cloud-object-storage.appdomain.cloud/sql-query-cos-access-ts/aiops_test/Location=eu-de/DC=rgfra02/Year=2019/Month=10/Date=23/Hour=01/"
    cos.delete_objects(cos_url)
