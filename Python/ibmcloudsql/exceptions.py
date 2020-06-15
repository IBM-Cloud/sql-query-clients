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

