from datetime import datetime
import responses
import pytest

from ibmcloudsql import cos

@pytest.fixture
def parsedurl_instance():
    return cos.ParsedUrl()

@pytest.fixture
def cos_url():
    cos_url = "cos://us-south/cos-access-ts/test/Location=us-south/DC=rgfra02/Year=2019/Month=10/D"
    return cos_url

def test_get_endpoint(parsedurl_instance, cos_url):
    x = parsedurl_instance.get_endpoint(cos_url)
    assert(x == "s3.us-south.cloud-object-storage.appdomain.cloud")

def test_get_bucket(parsedurl_instance, cos_url):
    x = parsedurl_instance.get_bucket(cos_url)
    assert(x == "cos-access-ts")

def test_get_prefix(parsedurl_instance, cos_url):
    x = parsedurl_instance.get_prefix(cos_url)
    assert(x == "test/Location=us-south/DC=rgfra02/Year=2019/Month=10/D")

def test_get_exact_url(parsedurl_instance, cos_url):
    x = parsedurl_instance.get_exact_url(cos_url)
    assert(x == "cos://s3.us-south.cloud-object-storage.appdomain.cloud/cos-access-ts/test/Location=us-south/DC=rgfra02/Year=2019/Month=10/D")

def test_analyze_cos_url(parsedurl_instance, cos_url):
    x = parsedurl_instance.analyze_cos_url(cos_url)
    assert(x.prefix == "test/Location=us-south/DC=rgfra02/Year=2019/Month=10/D")
    assert(x.bucket == "cos-access-ts")
    assert(x.endpoint == "s3.us-south.cloud-object-storage.appdomain.cloud")

@pytest.fixture
def cos_instance():
    cos_url = "cos://us-south/cos-access-ts/test/"
    cos_instance = cos.COSClient('mock-api-key', cos_url, client_info='ibmcloudsql test')

    # TODO mock method .logon() instead of hacking
    # disable authentication step for 300s
    cos_instance.logged_on = True
    cos_instance.last_logon = datetime.now()
    cos_instance.request_headers.update(
        {'authorization': 'Bearer {}'.format("mock")})
    return cos_instance

def test_cos_init(cos_instance):
    assert(cos_instance.request_headers == {'Content-Type': 'application/json',
    'Accept': 'application/json',
    'User-Agent': cos_instance.user_agent,
    'authorization': 'Bearer {}'.format("mock")
    })
