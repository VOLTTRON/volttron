.. _Developing-Market-Agents:

Developing Market Agents
===========================

VOLTTRON provides a convenient base class for developing new market
agents. The base class automatically subscribes to all pertinent topics,
and spells out a simple interface for concrete implementation to
make a working Market Agent.

Markets are implemented by the Market Service Agent which is a core service agent.
The Market Service Agent publishes information on several topics to which the base
agent automatically subscribes.  The base agent also provides all the methods you will
need to interact with the Market Service Agent to implment your market transactions.

MarketAgent
-------------

All Market Agents must inherit from the MarketAgent class in
volttron.platform.agent.base_market_agent and implement the following
methods:
