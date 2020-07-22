Introduction
================================================

ibmcloudsql
------------------------

Working with structured data in IBM Cloud Object Storage using SQL language, involves multiple capabilities:

1. `IBM Cloud access <https://cloud.ibm.com/docs/iam?topic=iam-manapikey>`_ that controls access to all IBM catalogs/resources.
2. `IBM COS instance <https://www.ibm.com/cloud/object-storage>`_ where input and outpout data is stored.
3. `IBM Cloud SQL Query instance <https://www.ibm.com/cloud/sql-query>`_ that offers the SQL-based data processing service.
4. Optionally: `IBM Watson Studio <https://www.ibm.com/cloud/watson-studio>`_: that provides notebook environment for running notebook, in that (Python) code and data asset are also stored, implicitly, in the Project's IBM Cloud Object Storage instance.
5. Visualization: can be done with Python code via IBM Watson Studio's notebook-

..
    6. Visualization: can be done via  ...
    7. The back-end server may be running on `IBM Cloud Function <https://cloud.ibm.com/functions/>`_. 

The **ibmcloudsql** library provides these multiple parts to Python applications. It comes with multiple submodules, each one links to another via subclass mechanism.

..  package extends the functionality of `ibmcloudsql <https://github.com/IBM-Cloud/sql-query-clients>`_

The submodules are the following:

* :ref:`utilities <utilities-label>` provides (A) - the IBM Cloud service connectivity-related functionality.
* :ref:`cos <cos-label>` provides (A, B) - the COS-related functionality.
* :ref:`SQLQuery <sql_query-label>` provides (A, B, C).
* (D, E) is done via notebook-based examples of user-specific code that also utilizes above submodules. For getting started, use this `starter notebook <https://dataplatform.cloud.ibm.com/exchange/public/entry/view/4a9bb1c816fb1e0f31fec5d580e4e14d>`_.


To install your package from source in this repository in editable mode, run the following:

.. code-block:: console

    cd sql-query-client/Python
    pip install -e .

To run the test on the package, run one of the following:

.. code-block:: console

    python -m pytest

    pytest

To install the published release of **ibmcloudsql** from `PyPi <https://pypi.org/project/ibmcloudsql/>`_, run the following:

 .. code-block:: console

     pip install ibmcloudsql
