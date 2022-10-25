FROM amazonlinux

COPY ./processing_script.py .

RUN yum install python3 pip -y
RUN pip3 install boto3 pandas

CMD [ "python3", "./processing_script.py" ]