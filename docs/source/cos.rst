.. _cos-label:

ibmcloudsql.cos
================================================

:mod:`ibmcloudsql.cos` provides 3 classes

* :py:class:`ibmcloudsql.cos.ParsedUrl` class which provides APIs to extract information from a given URL, e.g. COS URL
* :py:class:`ibmcloudsql.cos.COSClient` class which (1) does what ParsedUrl can, (2) provides APIs to interact with COS - an extension to ibm-cos-sdk
* :py:class:`ibmcloudsql.cos.ProjectLib` class which provides APIs to read/write data to Project's COS.

ParsedUrl
---------

:class:`ParsedUrl` provides the APIs to parse a COS URL.

ProjectLib
----------

:class:`ProjectLib` class maintains a reference to an object of IBM Watson Studio's ProjectLib 
which can read a file stored as an asset and load them into the current notebook.

This file can be used in a number of scenarios, such as 

1. store/reload progress information
2. load external Python packages
3. store/reload data files

*Example*:
When SQLQuery launches many jobs, there is a chance that the progress can be stopped, and
you don't want to restart from the beginning. The above setting enables the SQLQuery to skip the 
completed sql queries. The ``file_name`` argument reference to the name of the file 
to be used for saving and restoring the job progress.

.. code-block:: python

    from project_lib import Project
    project = Project(project_id=your_project_id,
                      project_access_token=your_project_cos_acess_token)

    # default file extension: json
    file_name = "aiops"
    sqlClient.connect_project_lib(project, file_name)



COSClient
---------

:class:`.COSClient` is also an :class:`.IBMCloudAccess` and a :class:`.ParsedUrl`.

COSClient class further provides the APIs

.. 1. interact with COS URL: based on :py:class:`ibmcloudsql.cos.ParsedUrl` class

* interact with COS instance:

    1. :meth:`.delete_objects`
    2. :meth:`.delete_empty_objects`
    3. :meth:`.list_cos_objects`
    4. :meth:`.update_bucket`
    5. :meth:`.get_bucket_info`
    6. :meth:`.get_cos_summary`

* interact with ProjectLib's data:

    1. :meth:`.connect_project_lib`
    2. :meth:`.read_project_lib_data`
    3. :meth:`.write_project_lib_data`
