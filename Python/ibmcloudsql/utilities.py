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
# flake8: noqa = W503
import getpass
import sys
import time
from datetime import datetime

import ibm_boto3
import ibm_botocore
import requests


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


def confirm_action(action_name=None):
    """
    Ask user to enter Y or N (case-insensitive).
    :return: True if the answer is Y.
    :rtype: bool
    """
    answer = ""
    msg = "OK to push to continue [Y/N]? "
    if action_name is not None:
        msg = "OK to {} [Y/N]? ".format(action_name)
    while answer not in ["y", "n"]:
        answer = input(msg).lower()
    return answer == "y"


class IBMCloudAccess:
    """
    This class provides APIs to get credentials to interact with IBM Cloud services, e.g. COS, SQL Query

    Parameters
    ----------
    cloud_apikey : str, optional
        an account-level API key [manage/Access (IAM)/IBM Cloud API keys]

    client_info : str, optional
        a description

    thread_safe: bool, optional
        a new Session object is created if not provided

    session: ibm_boto3.session.Session, optional
        provide a Session object so that it can be reused

    staging: bool, optional
        if True, then uses the test IAM endpoint
    iam_max_tries: int, optional
        Number of tries to connect to IAM service
    """

    def __init__(
        self,
        cloud_apikey="",
        client_info="",
        staging=False,
        thread_safe=False,
        session=None,
        iam_max_tries: int = 1,
    ):
        self.apikey = cloud_apikey
        self.staging = staging
        self._iam_max_tries = iam_max_tries
        assert self._iam_max_tries >= 1
        if client_info == "":
            self.user_agent = "IBMCloudAccess"
        else:
            self.user_agent = client_info
        self.request_headers = {"Content-Type": "application/json"}
        self.request_headers.update({"Accept": "application/json"})
        self.request_headers.update({"User-Agent": self.user_agent})
        self.request_headers_xml_content = {
            "Content-Type": "application/x-www-form-urlencoded"
        }
        self.current_token = None

        self.logged_on = False
        self.last_logon = None
        self._thread_safe = thread_safe
        if session is None:
            self._session = self.get_session()
        else:
            self._session = session

        self.request_headers_xml_content.update({"Accept": "application/json"})
        self.request_headers_xml_content.update({"User-Agent": self.user_agent})

    @property
    def cos_session(self):
        return self._session

    @property
    def thread_safe(self):
        return self._thread_safe

    def get_session(self):
        thread_safe = self._thread_safe
        if thread_safe is False:
            session = self._get_default_session()
        else:
            session = self._get_new_session()
        return session

    def configure(self, cloud_apikey=None):
        """
        Update Cloud API key
        """
        if cloud_apikey is None:
            self.apikey = (
                getpass.getpass(
                    "Enter IBM Cloud API Key (leave empty to use previous one): "
                )
                or self.apikey
            )
        else:
            self.apikey = cloud_apikey
        self._session._session.set_credentials(ibm_api_key_id=self.apikey)
        self.logged_on = False
        self.last_logon = None

    def _get_new_session(self):
        """return a new ibm_boto3.session.Session object"""
        if self.staging:
            return ibm_boto3.session.Session(
                ibm_api_key_id=self.apikey,
                ibm_auth_endpoint="https://iam.test.cloud.ibm.com/identity/token",
            )
        else:
            return ibm_boto3.session.Session(ibm_api_key_id=self.apikey,)

    def _get_default_session(self):
        # setup DEFAULT_SESSION global variable = a boto3 session for the given IAM API key
        if self.staging:
            ibm_boto3.setup_default_session(
                ibm_api_key_id=self.apikey,
                ibm_auth_endpoint="https://iam.test.cloud.ibm.com/identity/token",
            )
        else:
            ibm_boto3.setup_default_session(ibm_api_key_id=self.apikey)
        return ibm_boto3._get_default_session()

    def logon(self, force=False):
        """
        Establish a connection to IBM Cloud

        Notes
        -----
            An AIM token is needed for any operations to IBM cloud services (e.g. COS)
            A new AIM token is created after 300 seconds.
            A token is valid for 3600 seconds

        Raises
        ---------
        AttributeError:
           The exception is raised when the token cannot be retrieved using the current credential.

        """
        if (
            self.logged_on
            and not force
            and (datetime.now() - self.last_logon).seconds < 300
            and (
                "authorization" in self.request_headers
                and "None" not in self.request_headers["authorization"]
            )
        ):
            return True

        # TODO refactor construction to avoid calling private method
        self.logged_on = False
        boto3_session = self._session
        # ibm_boto3._get_default_session()
        complete = False
        count = 0
        retry_delay = 2
        ro_credentials = None
        while not complete and count < self._iam_max_tries:
            try:
                # set this to ensure a new token is retrieved
                boto3_session.get_credentials().token_manager._expiry_time = (
                    boto3_session.get_credentials().token_manager._time_fetcher()
                )
                ro_credentials = (
                    boto3_session.get_credentials().get_frozen_credentials()
                )
                self.current_token = ro_credentials.token
                complete = True
            except ibm_botocore.exceptions.CredentialRetrievalError:
                count += 1
                if count > self._iam_max_tries:
                    msg = (
                        "Login fails: credential cannot be validated"
                        "- check either (1) the key or (2) if IBM  cloud service is available"
                    )
                    raise AttributeError(msg)
            except requests.exceptions.ReadTimeout:
                count += 1
                if count > self._iam_max_tries:
                    msg = (
                        "Increase iam_max_tries (current set to {}),"
                        " or relaunch again as no response from IAM"
                    ).format(self._iam_max_tries)
                    raise AttributeError(msg)
            except Exception as e:
                raise e
            finally:
                time.sleep(retry_delay)
                retry_delay = min(retry_delay + 1, 10)

        self.request_headers = {"Content-Type": "application/json"}
        self.request_headers.update({"Accept": "application/json"})
        self.request_headers.update({"User-Agent": self.user_agent})

        self.request_headers.update(
            {"authorization": "Bearer {}".format(ro_credentials.token)}
        )
        self.logged_on = True
        self.last_logon = datetime.now()
