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

:class:`ProjectLib` class maintains a reference to an object of project_lib which can hold assets
that can be loaded into the current notebook.

A scenario where it is used is

1. store/reload progress information
2. load external Python packages
3. store/reload data files

*Example*:
When SQLClient launches many jobs, there is a chance that the progress can be stopped, and
you don't want to restart from the beginning. The above setting enables the SQLClient or AIOps
to skip the completed sql queries. The ``prefix_name`` is the file name to be used for saving and restoring the job progress.

.. code-block:: python

    from project_lib import Project
    project = Project(project_id=your_project_id,
                      project_access_token=your_project_cos_acess_token)

    prefix_name = "aiops_us_south_rgdal10_20200201"
    sqlClient.connect_project_lib(project, prefix_name)



COSClient
---------

:class:`COSClient` is also an :class:`IBMCloudAccess` and a :class:`ParsedUrl`.

COSClient class further provides the APIs

.. 1. interact with COS URL: based on :py:class:`ibmcloudsql.cos.ParsedUrl` class

* interact with COS instance:

    1. :meth:`.delete_objects`
    2. :meth:`.get_bucket_info`
    3. :meth:`.update_bucket`

* interact with ProjectLib's data:

    1. :meth:`.connect_project_lib`
    2. :meth:`.read_project_lib_data`
    3. :meth:`.write_project_lib_data`
