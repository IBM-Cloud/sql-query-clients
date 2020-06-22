Introduction
================================================

sql-query-client
------------------------

Working with data on the cloud, in the form of a SQL Query, involves multiple parts.

1. (A) `IBM Cloud access <https://cloud.ibm.com/docs/iam?topic=iam-manapikey>`_ which control access to all IBM catalogs/resources
2. (B) `IBM COS instance <https://www.ibm.com/cloud/object-storage>`_ where data is stored. This includes access to data asset as part of a IBM Watson Studio project.
3. (C) `IBM Cloud SQL Query instance <https://www.ibm.com/cloud/sql-query>`_ where the SQL-based query service is provided
4. (D) `IBM Watson Studio <https://www.ibm.com/cloud/watson-studio>`_: which provides notebook environment for running notebook, in that (Python) code and data asset are also stored, implicitly, in the Project's IBM COS instance.
5. (E) Visualization: can be done with Python code via IBM Watson Studio's notebook

..
    6. (F) Visualization: can be done via  ...
    7. (G) The back-end server may be running on `IBM Cloud Function <https://cloud.ibm.com/functions/>`_ 

This **sql-query-client** library makes the interacting across these multiple parts possible.

The **sql-query-client** library  comes with multiple submodules, each one links to another via subclass mechanism.

..  package extends the functionality of `ibmcloudsql <https://github.com/IBM-Cloud/sql-query-clients>`_

The submodules

* :ref:`utilities <utilities-label>` provides (A) - the IBM Cloud service connectivity-related functionality
* :ref:`cos <cos-label>` provides (A, B) - the COS-related functionality
* :ref:`sql_query <sql_query-label>` provides (A, B, C)
* (D, E) is done via notebook-based examples of user-specific code  which also utilizes above submodules


To install your package in “editable” mode

.. code-block:: console

    cd sql-query-client/Python
    pip install -e .

To run the test on the package, run either

.. code-block:: console

    python -m pytest

    pytest

