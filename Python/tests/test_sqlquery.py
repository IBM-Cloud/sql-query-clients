import json

from ibmcloudsql import SQLQuery

def test_init():
    sqlClient = SQLQuery('mock-api-key', 'mock-crn', client_info='ibmcloudsql test')

    assert(sqlClient.request_headers == {'Content-Type': 'application/json',
    'Accept': 'application/json',
    'User-Agent': sqlClient.user_agent
    })
