FROM python:2.7.15-slim-jessie

SHELL [ "bash", "-c" ]

ENV V_REPO=https://github.com/VOLTTRON/volttron
ENV VA_REPO=https://github.com/VOLTTRON/volttron-applications
ENV VA_GIT_BRANCH=master
ENV V_GIT_BRANCH=releases/5.x
ENV VOLTTRON_USER_HOME=/home/volttron

ENV VOLTTRON_HOME=${VOLTTRON_USER_HOME}/.volttron
ENV VOLTTRON_ROOT=/code/volttron
ENV VOLTTRON_APPLICATIONS_ROOT=/code/volttron-applications
ENV VOLTTRON_USER=volttron

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    python-dev \
    openssl \
    libssl-dev \
    libevent-dev \
    python-pip \
    git \
    gnupg \
    dirmngr \
    && pip install PyYAML \
    && rm -rf /var/lib/apt/lists/*

# add gosu for easy step-down from root
ENV GOSU_VERSION 1.7
RUN set -x \
	&& apt-get update && apt-get install -y --no-install-recommends ca-certificates wget && rm -rf /var/lib/apt/lists/* \
	&& wget -O /usr/local/bin/gosu "https://github.com/tianon/gosu/releases/download/$GOSU_VERSION/gosu-$(dpkg --print-architecture)" \
	&& wget -O /usr/local/bin/gosu.asc "https://github.com/tianon/gosu/releases/download/$GOSU_VERSION/gosu-$(dpkg --print-architecture).asc" \
	&& export GNUPGHOME="$(mktemp -d)" \
	&& gpg --keyserver hkp://p80.pool.sks-keyservers.net:80 --recv-keys B42F6819007F00F88E364FD4036A9C25BF357DD4 \
	&& gpg --batch --verify /usr/local/bin/gosu.asc /usr/local/bin/gosu \
	&& rm -rf "$GNUPGHOME" /usr/local/bin/gosu.asc \
	&& chmod +x /usr/local/bin/gosu \
	&& gosu nobody true \
&& apt-get purge -y --auto-remove wget

RUN adduser --disabled-password --gecos "" $VOLTTRON_USER

RUN mkdir -p /code/volttron
WORKDIR /code/volttron
COPY . .
RUN chown $VOLTTRON_USER.$VOLTTRON_USER /code -R
USER $VOLTTRON_USER
RUN ls -la
RUN python bootstrap.py --testing --market
RUN echo "source /code/volttron/env/bin/activate">${VOLTTRON_USER_HOME}/.bashrc
USER root

RUN mkdir /startup
COPY ci-integration/virtualization/entrypoint.sh /startup/entrypoint.sh
RUN chmod +x /startup/entrypoint.sh
WORKDIR ${VOLTTRON_ROOT}
ENTRYPOINT ["/startup/entrypoint.sh"]
CMD ["/bin/bash"]
