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
import codecs
import os.path

from setuptools import setup


def readme():
    with open("README.rst") as f:
        return f.read()


def read(rel_path):
    here = os.path.abspath(os.path.dirname(__file__))
    with codecs.open(os.path.join(here, rel_path), "r") as fp:
        return fp.read()


def get_version(rel_path):
    for line in read(rel_path).splitlines():
        if line.startswith("__version__"):
            delim = '"' if '"' in line else "'"
            return line.split(delim)[1]
    else:
        raise RuntimeError("Unable to find version string.")


setup(
    name="ibmcloudsql",
    version=get_version("ibmcloudsql/__init__.py"),
    python_requires=">=2.7, <4",
    install_requires=[
        "pandas>=1.3.0",
        "requests>= 2.2.0",
        "ibm-cos-sdk-core>=2.7.0",
        "ibm-cos-sdk>=2.7.0",
        "numpy",
        "pyarrow",
        "backoff==1.10.0",
        "sqlparse>=0.4.2",
        "packaging",
        "pre-commit",
        "isodate",
        "importlib-metadata",
        "typing-extensions",
    ],
    description="Python client for interacting with IBM Cloud SQL Query service",
    url="https://github.com/IBM-Cloud/sql-query-clients",
    author="IBM Corp.",
    author_email="torsten@de.ibm.com",
    license="Apache 2.0",
    classifiers=[
        "Development Status :: 4 - Beta",
        "License :: OSI Approved :: Apache Software License",
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3.8",
        "Topic :: Database",
    ],
    keywords="sql cloud object_storage IBM",
    packages=["ibmcloudsql"],
)
