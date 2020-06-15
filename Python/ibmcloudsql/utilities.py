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

import ibm_boto3
from ibm_botocore.client import Config
from datetime import datetime


def rename_keys(d, keys):
    """Rename keys from `d` that are present as a key in `keys` by the
    corresponding value in `keys`.

    Arguments:
        d {dict} -- [a dict whose certain keys need to be updated]
        keys {dict} -- [a dict that map old key to new key]

    Returns:
        [dict] -- [an updated dict]
    """
    return dict([(keys.get(k, k), v) for k, v in d.items()])


def static_vars(**kwargs):
    """
    use this as a decorator to a function to assign default value to static variable, e.g. var_stat

    .. code-block:: python

        @static_vars(var_stat=0)
        def func():
            func.var_stat = func.var_stat + 1

    IMPORTANT: Inside the function, access to the variable should be using the function name, e.g. func.var_stat
    """
    def decorate(func):
        for k in kwargs:
            setattr(func, k, kwargs[k])
        return func

    return decorate


class IBMCloudAccess():
    """Provide APIs to get credentials to interact with IBM Cloud services, e.g. COS, SQL Query
    """
    def __init__(self, cloud_apikey="", client_info=""):
        self.apikey = cloud_apikey
        if client_info == '':
            self.user_agent = 'IBMCloudAccess'
        else:
            self.user_agent = client_info
        self.request_headers = {'Content-Type': 'application/json'}
        self.request_headers.update({'Accept': 'application/json'})
        self.request_headers.update({'User-Agent': self.user_agent})
        self.request_headers_xml_content = {
            'Content-Type': 'application/x-www-form-urlencoded'
        }

        self.logged_on = False
        self.last_logon = None
        self._session = self._get_default_session()

        self.request_headers_xml_content.update({'Accept': 'application/json'})
        self.request_headers_xml_content.update(
            {'User-Agent': self.user_agent})

    def _get_default_session(self):
        # setup DEFAULT_SESSION global variable = a boto3 session for the given IAM API key
        ibm_boto3.setup_default_session(ibm_api_key_id=self.apikey, )
        return ibm_boto3._get_default_session()

    def logon(self, force=False):
        """"
            An AIM token is needed for any operations to IBM cloud services (e.g. COS)
            A new AIM token is created after 300 seconds.
            A token is valid for 3600 seconds

            """
        if self.logged_on and not force and (datetime.now() -
                                            self.last_logon).seconds < 300 and \
                                            ('authorization' in self.request_headers and
                                            'None' not in self.request_headers['authorization']):
            return

        ## TODO refactor construction to avoid calling private method
        boto3_session = self._session
        # ibm_boto3._get_default_session()
        ro_credentials = boto3_session.get_credentials(
        ).get_frozen_credentials()

        self.request_headers = {'Content-Type': 'application/json'}
        self.request_headers.update({'Accept': 'application/json'})
        self.request_headers.update({'User-Agent': self.user_agent})
        self.request_headers.update(
            {'authorization': 'Bearer {}'.format(ro_credentials.token)})
        self.logged_on = True
        self.last_logon = datetime.now()
