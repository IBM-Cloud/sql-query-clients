import sys
import pandas as pd

if sys.version_info > (3, 3):
    from unittest.mock import MagicMock, patch, PropertyMock
else:
    from mock import MagicMock, patch, PropertyMock

from ibmcloudsql import SQLQuery

def test_init():
    sqlClient = SQLQuery('mock-api-key', 'mock-crn', client_info='ibmcloudsql test')

    assert(sqlClient.request_headers == {'Content-Type': 'application/json',
    'Accept': 'application/json',
    'User-Agent': sqlClient.user_agent
    })

@patch('ibmcloudsql.SQLQuery._get_cos_resource')
def test_list_objects(mock_cos):
    OBJECT_SUMMARY_ATTRS = ['bucket_name', 'key']
    mock_obj = MagicMock(spec=OBJECT_SUMMARY_ATTRS)
    type(mock_obj).bucket_name = PropertyMock(return_value='bucket-1')
    type(mock_obj).key = PropertyMock(return_value='prefix-2/1')

    mock_cos.return_value.Bucket.return_value.objects.filter.return_value = [mock_obj]

    sql_client = SQLQuery('mock-api-key', 'mock-crn', client_info='ibmcloudsql test')
    result = sql_client.list_cos_objects('cos://us-south/bucket-1/prefix-2/')

    mock_cos.assert_called_once_with('s3.us-south.objectstorage.softlayer.net')
    mock_cos.return_value.Bucket.assert_called_once_with('bucket-1')
    mock_cos.return_value.Bucket.return_value.objects.filter.assert_called_once_with(Prefix='prefix-2/')

    assert list(result) == OBJECT_SUMMARY_ATTRS
    assert result.equals(pd.DataFrame({'bucket_name': ['bucket-1'], 'key': ['prefix-2/1']}))