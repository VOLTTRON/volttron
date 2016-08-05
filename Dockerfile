FROM ubuntu:14.04
MAINTAINER David Conroy  <dave@crtlabs.org>
RUN adduser --disabled-password --gecos '' vdev
ADD  . /home/vdev/
WORKDIR /home/vdev/
RUN chown -R vdev:vdev /home/vdev
RUN apt-get update &&  apt-get install -y build-essential python-dev openssl libssl-dev libevent-dev git nano
USER vdev
RUN python2.7 bootstrap.py
