 .. _RabbitMQ-Overview:
=================
RabbitMQ Overview
=================
RabbitMQ is the most popular messaging library with over 35,000 production deployments.
It is highly scalable, easy to deploy and runs on many operating systems and cloud
environments. It supports many kinds of distributed deployment methodlogies such as
federation, shovels and clusters (More about these in section ).

RabbitMQ uses Advanced Message Queueing Protocol (AMQP). RabbitMQ uses the basic
producer consumer model. A consumer is program that consumes/receives messages and
produces is a program that sends the messages. Following are some important
definitions that we need to know before we proceed.

* Queue - Queues can be considered like a post box that stores messages until consumed
by the consumer. Each consumer must create a queue to receives messages that it is
interested in receiving. We can set properties to the queue during it's declaration. The
queue properties are
  * Name
  * Durable - Flag to indicate if the queue should survive broker restart.
  * Exclusive - Used only for one connection and it will be removed when connection is closed.
  * Auto-queue - Flag indicates if auto-delete is needed. The queue is deleted when
  last consumer unsubscribes from it.
  * Arguments - Optional, can be used to set message TTL (Time To Live), queue limit etc.

* Bindings - Consumers bind the queue to an exchange with binding keys or routing
patterns. Producers send messages and associate them with a routing key. Messages are
routed to one or many queues based on a matching between a message routing key and binding key.

* Exchanges - Exchanges are entities that are responsible for routing messages to the
queues based on the routing pattern/binding key used. They look at the routing key in the
message when deciding how to route messages to queues.
There are different types of exchanges and one must choose the type of exchange depending
on the application design requirements

* Fanout - It blindly broadcasts the message it receives to all the queues it knows.

* Direct - Here, the message is routed to a queue if the routing key of the message
exactly matches the binding key of the queue.

* Topic - Here, the message is routed to a queue based on pattern matching of the
routing key with the binding key. The binding key and the routing key pattern must be a
list of words delimited by dots, for example, "car.subaru.outback" or "car.subaru.*",
"car.#". A message sent with a particular routing key will be delivered to all the
queues that are bound with a matching binding key with some special rules as

* (star) - can match exactly one word in that position.
# (hash) - can match zero or more words

* Headers - If we need more complex matching then we can add a header to the message with
all the attributes set to the values that need to be matched. The message is considered
matching if the values of the attributes in the header is equal to that of the binding. Header
exchange ignore the routing key.

  We can set some properties to the exchange during it's declaration.
  * Name
  * Durable - Flag to indicate if the exchange should survive broker restart.
  * Auto-delete - Flag indicates if auto-delete is needed. If set to true, the exchange is
  deleted when the last queue is unbound from it.
  * Arguments - Optional, used by plugins and broker-specific features

Lets use an example to understand how they all fit together. Consider an example where there
are four consumers (Consumer 1 - 4) interested in receiving messages matching the pattern "green", "red" or
"yellow". In this example, we are using a direct exchange that will route the messages to the
queues only when there is an exact match of the routing key of the message with the binding key
of the queues. Each of the consumers declare a queue and bind the queue with the exchange with
a binding key of interest. Lastly, we have a producer that is continuously sending messages to
exchange with routing key "green". The exchange will check for an exact match and route the
messages to only Consumer 1 and Consumer 3.

For more information about queues, bindings, exchanges, please refer to RabbitMQ tutorial link
https://www.rabbitmq.com/getstarted.html


Distributed RabbitMQ Brokers
****************************

Federation
**********

Shovel
******

Clustering
**********


Authentication and Authorization in RabbitMQ
********************************************


Management Plugin
*****************
