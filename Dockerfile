FROM ubuntu

ADD ./lib /data
WORKDIR /data

RUN sudo apt-get update
RUN sudo apt-get upgrade -y
RUN sudo apt-get install -y python

CMD ["python","stream.py"]
