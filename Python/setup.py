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

from setuptools import setup

def readme():
    with open('README.rst') as f:
        return f.read()

setup(name='ibmcloudsql',
      version='0.2.16',
      install_requires=['pandas','urllib3','simplejson','tornado<=4.5.2','botocore','ibm-cos-sdk','numpy'],
      description='Python client for interacting with IBM Cloud SQL Query service',
      url='https://github.com/IBM-Cloud/sql-query-clients',
      author='IBM Corp.',
      author_email='torsten@de.ibm.com',
      license='Apache 2.0',
      classifiers=[
        'Development Status :: 4 - Beta',
        'License :: OSI Approved :: Apache Software License',
        'Programming Language :: Python :: 2.7',
        'Topic :: Database',
      ],
      keywords='sql cloud object_storage IBM',
      packages=['ibmcloudsql']
     )
