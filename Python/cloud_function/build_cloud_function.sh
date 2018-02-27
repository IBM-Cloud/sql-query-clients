/usr/local/bin/virtualenv virtualenv
source virtualenv/bin/activate
pip install ibmcloudsql
pip uninstall --yes urllib3 simplejson six setuptools python-dateutil pytz pandas numpy jmespath docutils
rm ibmcloudsql_cloudfunction.zip
zip -r ibmcloudsql_cloudfunction.zip virtualenv __main__.py
bx wsk action delete ibmcloudsql_cloudfunction
bx wsk action create ibmcloudsql_cloudfunction --timeout 300000 --kind python-jessie:3 ibmcloudsql_cloudfunction.zip
