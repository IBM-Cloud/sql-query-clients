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


class RateLimitedException(Exception):
    """The error when number of requests exceeds the capacity"""

    def __init__(self, msg, original_exception=None):
        if original_exception is not None:
            super().__init__(msg + (": %s" % original_exception))
        else:
            super().__init__(msg)
        self.original_exception = original_exception


class InternalError502Exception(Exception):
    """The error when SQL Query returns a 502 internal error"""

    def __init__(self, msg, original_exception=None):
        if original_exception is not None:
            super().__init__(msg + (": %s" % original_exception))
        else:
            super().__init__(msg)
        self.original_exception = original_exception


class CosUrlNotFoundException(Exception):
    """The error when the Cloud-Object Storage (COS) URL being used is invalid or not accessible"""

    def __init__(self, msg, original_exception=None):
        if original_exception is not None:
            super().__init__(msg + (": %s" % original_exception))
        else:
            super().__init__(msg)
        self.original_exception = original_exception


class CosUrlInaccessibleException(Exception):
    """The error when the Cloud-Object Storage (COS) URL being used is not accessible"""

    def __init__(self, msg, original_exception=None):
        if original_exception is not None:
            super().__init__(msg + (": %s" % original_exception))
        else:
            super().__init__(msg)
        self.original_exception = original_exception


class SqlQueryCrnInvalidFormatException(Exception):
    """The error when the SQL Query CRN is not correct"""

    def __init__(self, msg, original_exception=None):
        if original_exception is not None:
            super().__init__(msg + (": %s" % original_exception))
        else:
            super().__init__(msg)
        self.original_exception = original_exception


class SqlQueryInvalidPlanException(Exception):
    """The error when the used feature is not supported by the current service plan -
    e.g. need to upgrade to Standard Plan or higher"""

    def __init__(self, msg, original_exception=None):
        if original_exception is not None:
            super().__init__(msg + (": %s" % original_exception))
        else:
            super().__init__(msg)
        self.original_exception = original_exception


class SqlQueryFailException(Exception):
    """The error raised when a running sql job fails, e.g. timeout"""

    def __init__(self, msg, original_exception=None):
        if original_exception is not None:
            super().__init__(msg + (": %s" % original_exception))
        else:
            super().__init__(msg)
        self.original_exception = original_exception


class SqlQueryCreateTableException(SqlQueryFailException):
    """The error raised when a running create-table sql job fails"""

    def __init__(self, msg, original_exception=None):
        if original_exception is not None:
            super().__init__(msg + (": %s" % original_exception))
        else:
            super().__init__(msg)
        self.original_exception = original_exception


class SqlQueryDropTableException(SqlQueryFailException):
    """The error raised when a running drop-table sql job fails"""

    def __init__(self, msg, original_exception=None):
        if original_exception is not None:
            super().__init__(msg + (": %s" % original_exception))
        else:
            super().__init__(msg)
        self.original_exception = original_exception


class SqlQueryInvalidFormatException(SqlQueryFailException):
    """The error raised when the format of COS URL is not valid"""

    def __init__(self, msg, original_exception=None):
        if original_exception is not None:
            super().__init__(msg + (": %s" % original_exception))
        else:
            super().__init__(msg)
        self.original_exception = original_exception


class UnsupportedStorageFormatException(Exception):
    """The error when the SQL uses a format of data that has not been supported yet"""

    def __init__(self, msg, original_exception=None):
        if original_exception is not None:
            super().__init__(msg + (": %s" % original_exception))
        else:
            super().__init__(msg)
        self.original_exception = original_exception
