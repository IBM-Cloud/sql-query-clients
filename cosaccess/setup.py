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
"""Setup file."""
import codecs
import os.path

from setuptools import setup
# read the contents of your README file
from pathlib import Path
this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text()


def readme():
    """Return README.rst content."""
    with open("README.rst") as f:
        return f.read()


def _read(rel_path):
    here = os.path.abspath(os.path.dirname(__file__))
    with codecs.open(os.path.join(here, rel_path), "r") as fp:
        return fp.read()


def get_version(rel_path):
    """Get package version."""
    for line in _read(rel_path).splitlines():
        if line.startswith("__version__"):
            delim = '"' if '"' in line else "'"
            return line.split(delim)[1]
    else:
        raise RuntimeError("Unable to find version string.")


setup(
    name="cosaccess",
    version=get_version("cosaccess/__init__.py"),
    python_requires=">=2.7, <4",
    install_requires=[
        "pandas",
        "ibm_cloud_sdk_core",
        "ibm_platform_services",
        "ibm-cos-sdk-config",
        "ibm-cos-sdk"
        "requests",
    ],
    description="Python client for managing IAM policies fine grained access control in IBM Cloud Object Storage",  # noqa
    long_description=long_description,
    long_description_content_type='text/markdown',
    url="https://github.com/IBM-Cloud/sql-query-clients/cosaccess",
    author="IBM Corp.",
    author_email="torsten@de.ibm.com",
    license="Apache 2.0",
    classifiers=[
        "License :: OSI Approved :: Apache Software License",
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3.8",
        "Topic :: Database",
    ],
    keywords="cloud object_storage IBM",
    packages=["cosaccess"],
)
