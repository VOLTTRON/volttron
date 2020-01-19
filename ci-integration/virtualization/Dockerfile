ARG image_user=laroque
ARG image_repo=volttron-docker
ARG image_tag=deps-master-amd64

FROM ${image_user}/${image_repo}:${image_tag} as volttron_deps

# Note I couldn't get variable expansion on the chown argument to work here
# so must hard code the user.  Note this is a feature request for docker
# https://github.com/moby/moby/issues/35018
COPY --chown=volttron:volttron . ${VOLTTRON_ROOT}

USER $VOLTTRON_USER

# The following lines ar no longer necesary because of the copy command above.
#WORKDIR /code
#RUN git clone https://github.com/VOLTTRON/volttron -b ${VOLTTRON_GIT_BRANCH}

WORKDIR /code/volttron
#RUN pip install --user -r requirements.txt
RUN pip install -e . --user

############################################
# RABBITMQ SPECIFIC INSTALLATION
############################################
USER root
RUN ./scripts/rabbit_dependencies.sh $OS_TYPE $DIST

RUN mkdir /startup $VOLTTRON_HOME && \
    chown $VOLTTRON_USER.$VOLTTRON_USER $VOLTTRON_HOME
COPY ./ci-integration/virtualization/core/entrypoint.sh /startup/entrypoint.sh
COPY ./ci-integration/virtualization/core/bootstart.sh /startup/bootstart.sh
RUN chmod +x /startup/entrypoint.sh && \
    chmod +x /startup/bootstart.sh

USER $VOLTTRON_USER
RUN mkdir $RMQ_ROOT
RUN set -eux \
    && wget -P $VOLTTRON_USER_HOME https://github.com/rabbitmq/rabbitmq-server/releases/download/v3.7.7/rabbitmq-server-generic-unix-3.7.7.tar.xz \
    && tar -xf $VOLTTRON_USER_HOME/rabbitmq-server-generic-unix-3.7.7.tar.xz --directory $RMQ_ROOT \
    && $RMQ_HOME/sbin/rabbitmq-plugins enable rabbitmq_management rabbitmq_federation rabbitmq_federation_management rabbitmq_shovel rabbitmq_shovel_management rabbitmq_auth_mechanism_ssl rabbitmq_trust_store
RUN pip install gevent-pika --user
############################################


########################################
# The following lines should be run from any Dockerfile that
# is inheriting from this one as this will make the volttron
# run in the proper location.
########################################

# WORKDIR ${VOLTTRON_USER_HOME}
# ENTRYPOINT ["/startup/entrypoint.sh"]
# CMD ["/startup/bootstart.sh"]


