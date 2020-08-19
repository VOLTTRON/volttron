.. _Developing-Market-Agents:

========================
Developing Market Agents
========================

VOLTTRON provides a convenient base class for developing new market agents.  The base class automatically subscribes to all pertinent topics,
and spells out a simple interface for concrete implementation to make a working Market Agent.

Markets are implemented by the Market Service Agent which is a core service agent.  The Market Service Agent publishes
information on several topics to which the base agent automatically subscribes.  The base agent also provides all the
methods you will need to interact with the Market Service Agent to implement your market transactions.

MarketAgent
===========

All Market Agents must inherit from the MarketAgent class in `volttron.platform.agent.base_market_agent` and call the
following method:

.. code-block:: python

    self.join_market(market_name, buyer_seller, reservation_callback, offer_callback, aggregate_callback, price_callback, error_callback)

This method causes the market agent to join a single market.  If the agent wishes to participate in several
markets it may be called once for each market.  The first argument is the name of the market to join and this name must
be unique across the entire volttron instance because all markets are implemented by a single market service agent for
each volttron instance.  The second argument describes the role that this agent wished to play in this market.
The value is imported as:

.. code-block:: python

    from volttron.platform.agent.base_market_agent.buy_sell import BUYER, SELLER

Arguments 3-7 are callback methods that the agent may implement as needed for the agent's participation in the market.


The Reservation Callback
------------------------

.. code-block:: python

    reservation_callback(self, timestamp, market_name, buyer_seller)

This method is called when it is time to reserve a slot in the market for the current market cycle.  If this callback is
not registered a slot is reserved for every market cycle.  If this callback is registered it is called for each market
cycle and returns `True` if a reservation is wanted and `False` if a reservation is not wanted.

The name of the market and the roll being played are provided so that a single callback can handle several markets.
If the agent joins three markets with the same reservation callback routine it will be called three times with the
appropriate market name and buyer/seller role for each call.  The MeterAgent example illustrates the use of this of this
method and how to determine whether to make an offer when the reservation is refused.

A market will only exist if there are reservations for at least one buyer or one seller.  If the market fails to achieve
the minimum participation the error callback will be called.  If only buyers or only sellers make reservations any
offers will be rejected with the reason that the market has not formed.


The Offer Callback
------------------

.. code-block:: python

    offer_callback(self, timestamp, market_name, buyer_seller)

If the agent has made a reservation for the market and a callback has been registered this callback is called.
If the agent wishes to make an offer at this time the market agent computes either a supply or
a demand curve as appropriate and offers the curve to the market service by calling the
:py:meth:`make_offer <volttron.platform.agent.base_market_agent.MarketAgent.make_offer>` method.

.. code-block:: python
    `make_offer <volttron.platform.agent.base_market_agent.MarketAgent.make_offer>`

The name of the market and the roll being played are provided so that a single callback can handle several markets.

For each market joined either an offer callback, an aggregate callback, or a cleared price callback is required.


The Aggregate Callback
----------------------

.. code-block:: python

    aggregate_callback(self, timestamp, market_name, buyer_seller, aggregate_curve)

When a market has received all its buy offers it calculates an aggregate demand curve.  When the market receives all of
its sell offers it calculates an aggregate supply curve.  This callback delivers the aggregate curve to the market agent
whenever the appropriate curve becomes available.

If the market agent wants to use this opportunity to make an offer on this or another market it would do that using the
:py:meth:`make_offer <volttron.platform.agent.base_market_agent.MarketAgent.make_offer>` method.

* If the aggregate demand curve is received, only a supply offer may be submitted for this market
* If the aggregate supply curve is received, only make a demand offer will be accepted by this market.

You may use this information to make an offer on another market;  The example AHUAgent does this.  The name of the
market and the roll being played are provided so that a single callback can handle several markets.

For each market joined, either an offer callback, an aggregate callback, or a cleared price callback is required.


The Price Callback
------------------

.. code-block:: python

    price_callback(self, timestamp, market_name, buyer_seller, price, quantity)

This callback is called when the market clears.  If the market agent wants to use this opportunity to make an offer on
this or another market it would do that using the
:py:meth:`make_offer <volttron.platform.agent.base_market_agent.MarketAgent.make_offer>` method.

Once the market has cleared you can not make an offer on that market. Again, you may use this information to make an
offer on another market as in the example AHUAgent.  The name of the market and the roll being played are provided so
that a single callback can handle several markets.

For each market joined either an offer callback, an aggregate callback, or a cleared price callback is required.


The Error Callback
------------------

.. code-block:: python

    error_callback(self, timestamp, market_name, buyer_seller, error_code, error_message, aux)

This callback is called when an error occurs isn't in response to an RPC call. The error codes are documented in:

.. code-block:: python

    from volttron.platform.agent.base_market_agent.error_codes import NOT_FORMED, SHORT_OFFERS, BAD_STATE, NO_INTERSECT

* NOT_FORMED - If a market fails to form this will be called at the offer time.
* SHORT_OFFERS - If the market doesn’t receive all its offers this will be called while clearing the market.
* BAD_STATE - This indicates a bad state transition while clearing the market  and should never happen, but may be called  while clearing the market.
* NO_INTERSECT - If the market fails to clear this would be called while clearing the market and an auxillary array will be included.  The auxillary array contains comparisons between the supply max, supply min, demand max and demand min.  They allow the market client to make determinations about why the curves did not intersect that may be useful.

The error callback is optional, but highly recommended.
