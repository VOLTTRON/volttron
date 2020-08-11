.. _Monitoring-RMQ:

Monitoring and Controlling RabbitMQ
===================================

Some of the important native RabbitMQ control and management commands are now
integrated with "volttron-ctl" utility. Using volttron-ctl rabbitmq management
utility, we can control and monitor the status of RabbitMQ message bus.

.. code-block:: bash

    vctl rabbitmq --help
    usage: vctl command [OPTIONS] ... rabbitmq [-h] [-c FILE] [--debug]
                                                    [-t SECS]
                                                    [--msgdebug MSGDEBUG]
                                                    [--vip-address ZMQADDR]
                                                    ...
    subcommands:

        add-vhost           add a new virtual host
        add-user            Add a new user. User will have admin privileges
                            i.e,configure, read and write
        add-exchange        add a new exchange
        add-queue           add a new queue
        list-vhosts         List virtual hosts
        list-users          List users
        list-user-properties
                            List users
        list-exchanges      add a new user
        list-exchange-properties
                            list exchanges with properties
        list-queues         list all queues
        list-queue-properties
                            list queues with properties
        list-bindings       list all bindings with exchange
        list-federation-parameters
                            list all federation parameters
        list-shovel-parameters
                            list all shovel parameters
        list-policies       list all policies
        remove-vhosts       Remove virtual host/s
        remove-users        Remove virtual user/s
        remove-exchanges    Remove exchange/s
        remove-queues       Remove queue/s
        remove-federation-parameters
                            Remove federation parameter
        remove-shovel-parameters
                            Remove shovel parameter
        remove-policies     Remove policy

