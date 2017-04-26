PrometheusScrapeAgent
=====================
This agent will provide a Prometheus compatible metrics scrape page from any data
observed on the platforms message bus.
It does require that the web subsystem be active, and that a listening address be
configured in the platforms config file.
The metrics page will be served at http(s)://<volttron_listen_address>:<volttron_listen_port>/promscrape

Config
~~~~~~
The config is rather simple, currenly only supporting two options:
cache_timeout: 660

Cache timeout is the number of seconds that the agent will keep data
from a topic in memory after it's observed on the message bus. If the topic is 
not observed again before the timeout expires, the topic will be removed from 
the cache and not appear in subsequent scrapes until it is observed on the bus again.

tag_delimiter_re: "\s+|:|_|\.|/"

The tag delimiter is a python regex pattern that the topic will be split by in order 
to populate numerically ordered tags in formatted metrics. This allows you to split 
a topic name with meta-data encoded into tags that can be efficiently queried from
the prometheus database.
