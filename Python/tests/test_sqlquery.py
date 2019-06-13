import json

from ibmcloudsql import SQLQuery

def test_init():
    sqlClient = SQLQuery('mock-api-key', 'mock-crn', client_info='ibmcloudsql test')

    assert type(sqlClient.client).__name__ is 'HTTPClient'
