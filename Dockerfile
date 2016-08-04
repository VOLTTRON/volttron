FROM ubuntu:14.04
MAINTAINER David Conroy  <dave@crtlabs.org>
RUN adduser --disabled-password --gecos '' volttron-user
ADD  . /home/volttron-user/
WORKDIR /home/volttron-user/
RUN chown -R volttron-user:volttron-user /home/volttron-user/volttron
RUN apt-get update &&  apt-get install -y build-essential python-dev openssl libssl-dev libevent-dev git
USER volttron-user
RUN python2.7 bootstrap.py
