Introduction
================================================

ibmcloudsql
------------------------

The **ibmcloudsql** library provides to Python applications the APIs for working with structured data stored on IBM Cloud Object Storage using SQL language, which involves multiple resources/catalogs:

1. `IAM <https://cloud.ibm.com/docs/account?topic=account-iamoverview>`_ that controls access to all IBM cloud catalogs/resources.
2. `IBM COS <https://www.ibm.com/cloud/object-storage>`_ where input and outpout data is stored.
3. `IBM Cloud SQL Query <https://www.ibm.com/cloud/sql-query>`_ that offers the SQL-based data processing service.
4. `IBM Watson Studio <https://www.ibm.com/cloud/watson-studio>`_ (optional): that provides notebook environment for running notebook, in that (Python) code and data asset are also stored, implicitly, in the Project's IBM Cloud Object Storage instance. Such project asset can be accessed using the `project-lib library <https://dataplatform.cloud.ibm.com/docs/content/wsj/analyze-data/project-lib-python.html>`_.

..
    5. Visualization: can be done with Python code via IBM Watson Studio's notebook.
    6. Visualization: can be done via  ...
    7. The back-end server may be running on `IBM Cloud Function <https://cloud.ibm.com/functions/>`_. 

The **ibmcloudsql** library comes with multiple submodules, each contains one or many classes. The classes relate to each other via subclass mechanism.  The submodules are the following:

* :ref:`utilities <utilities-label>` provides access to (1) - the IBM Cloud service connectivity-related functionality.
* :ref:`cos <cos-label>` provides access to (1, 2, 4) - the COS-related functionality.
* :ref:`sql_magic <sql-magic-label>` provides the capability to construct a complex SQL statement, including time-series-related functionality.
* :ref:`SQLQuery <sql_query-label>` provides access to (3) and to those provided by these submodules (utilities, cos, sql_magic).

For getting started, use this `starter notebook <https://dataplatform.cloud.ibm.com/exchange/public/entry/view/4a9bb1c816fb1e0f31fec5d580e4e14d>`_.
which provides notebook-based examples of user-specific code that also utilizes above submodules. 

install 
------------------------

To install the published release of **ibmcloudsql** from `PyPi <https://pypi.org/project/ibmcloudsql/>`_, run the following:

 .. code-block:: console

     pip install ibmcloudsql

For development purpose, you can also checkout the source, and then install in editable mode:

.. code-block:: console

    git clone git@github.com:IBM-Cloud/sql-query-clients.git
    cd sql-query-client/Python
    pip install -e .

To run the test on the package, run one of the following:

.. code-block:: console

    python -m pytest

    pytest

