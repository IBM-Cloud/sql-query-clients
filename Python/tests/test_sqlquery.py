from datetime import datetime

import responses
import pytest

from ibmcloudsql import SQLQuery, RateLimitedException



@pytest.fixture
def sqlquery_client():
    sql_client = SQLQuery('mock-api-key', 'mock-crn', client_info='ibmcloudsql test')

    # disable authentication step for 300s
    sql_client.logged_on = True
    sql_client.last_logon = datetime.now()
    return sql_client

def test_init(sqlquery_client):
    assert(sqlquery_client.request_headers == {'Content-Type': 'application/json',
    'Accept': 'application/json',
    'User-Agent': sqlquery_client.user_agent
    })

@responses.activate
def test_submit_sql_no_retry(sqlquery_client):
    '''expect exception when getting status code 429'''
    mock_error_message = 'too many requests'
    responses.add(responses.POST, 'https://api.sql-query.cloud.ibm.com/v2/sql_jobs',
                  json={'errors': [{'message': mock_error_message}]}, status=429)

    with pytest.raises(RateLimitedException, match=mock_error_message) as exc_info:
        sqlquery_client.submit_sql('VALUES (1)')

    # assert str(exc_info) == 'SQL submission failed: too many requests'

    
def test_submit_sql_w_retry():
    '''retry when getting status code 429'''
    pass