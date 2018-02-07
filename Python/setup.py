from setuptools import setup

def readme():
    with open('README.rst') as f:
        return f.read()

setup(name='ibmcloudsql',
      version='0.1.1',
      install_requires=['pandas','urllib3','simplejson','tornado','botocore','ibm-cos-sdk'],
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
