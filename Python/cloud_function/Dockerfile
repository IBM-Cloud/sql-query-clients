FROM ibmfunctions/action-python-v3

RUN pip install ibmcloudsql

ADD sqlfunction.py /action/sqlfunction.py
RUN echo '#!/bin/bash\n\
python /action/sqlfunction.py "$1"' > /action/exec
RUN chmod +x /action/exec

CMD ["/bin/bash", "-c", "cd actionProxy && python -u actionproxy.py"]

