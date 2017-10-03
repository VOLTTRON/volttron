.. _MarketServiceAgent:

====================
Market Service Agent
====================

Introduction
============

The MarketServiceAgent implements a variation of a double-blind auction, in which each market participant bids
to buy or sell a commodity for a given price.

In contrast to other common implementations, participants do not bid single price-quantity pairs.
Instead, they bid a price-quantity curve, or “flexibility curve” into their respective markets.
Market participants may be both buyers in one market and sellers in another.
Settling of the market is a “single shot” process that begins with bidding that progresses from the bottom up
and concludes with a clearing of the markets from the top down. This is termed “single shot” because there is no
iteration required to find the clearing price or quantity at any level of the market structure.
Once the market has cleared, the process begins again for the next market interval, and
new bids are submitted based on the updated states of the agents.

Market Timing
-------------

The MarketServiceAgent is driven by the Director.  The Director
drives the MarketServiceAgent through a timed loop.  The Director has just a few parameters
that are configured by default with adequate values.  They are:

1. The market_period with a default value of 5 minutes
2. The reservation_delay with a default value of 0 minutes
3. The offer_delay with a default value of 2 minutes

The timing loop works as follows:

* The market period begins.
* A request for reservations is published after the reservation delay.
* A request for offers/bids  is published after the offer delay.
* The aggregate demand curve is published as soon all the buy offers are completed for the market.
* The aggregate supply curve is published as soon all the sell offers are completed for the market.
* The cleared price is published as soon as all bids have been received.
* Error messages are published when discovered and usually occur at the end of one of the delays.
* The cycle repeats.

How to Use the MarketServiceAgent
=================================

A given agent participates in one or more markets by inheriting from the base MarketAgent.
The base MarketAgent handles all of the communication between the agent and the MarketServiceAgent.
The agent only needs to join each market with the
:py:meth:`join_market <volttron.platform.agent.base_market_agent.MarketAgent.join_market>`
method and then respond to the appropriate callback methods.  The callback methods are describe below.

Reservation Callback
--------------------

This callback is called at the beginning of each round of bidding and clearing.
The agent can choose whether or not to participate in this round.
If the agent wants to participate it returns true otherwise it returns false.
If the agent does not specify a callback routine a reservation will be made for each round automatically.
A market will only exist if there are reservations for at least one buyer or one seller.
If the market fails to achieve the minimum participation the error callback will be called.
If only buyers or only sellers make reservations any offers will be rejected
with the reason that the market has not formed.

Offer Callback
--------------

If the agent has made a reservation for the market and a callback has been registered this callback is called.
If the agent wishes to make an offer at this time the market agent computes either a supply or
a demand curve as appropriate and offers the curve to the market service by calling the
:py:meth:`make_offer <volttron.platform.agent.base_market_agent.MarketAgent.make_offer>`
method.
For each market joined either an offer callback, an aggregate callback, or a cleared price callback is required.

Aggregate Callback
------------------

When a market has received all its buy offers it calculates an aggregate demand curve.
When the market receives all of its sell offers it calculates an aggregate supply curve.
This callback delivers the aggregate curve to the market agent whenever the appropriate curve becomes available.
If the market agent wants to use this opportunity to make an offer on this or another market
it would do that using the
:py:meth:`make_offer <volttron.platform.agent.base_market_agent.MarketAgent.make_offer>`
method.
If the aggregate demand curve is received, obviously you could only make a supply offer on this market.
If the aggregate supply curve is received, obviously you could only make a demand offer on this market.
You can of course use this information to make an offer on another market.  The example AHUAgent does this.
For each market joined either an offer callback, an aggregate callback, or a cleared price callback is required.

Price Callback
--------------

This callback is called when the market clears.
If the market agent wants to use this opportunity to make an offer on this or another market
it would do that using the
:py:meth:`make_offer <volttron.platform.agent.base_market_agent.MarketAgent.make_offer>`
method.
Once the market has cleared you can't make an offer on that market.
You can of course use this information to make an offer on another market.  The example AHUAgent does this.
For each market joined either an offer callback, an aggregate callback, or a cleared price callback is required.

Error Callback
--------------

This callback is called when an error occurs isn't in response to an RPC call.
If a market fails to form this will be called at the offer time.
If the market doesn’t receive all its offers this will be called at the next reservation time.
If the market fails to clear this would be called at the next reservation time.
This allows agents to respond at or near the normal time points.  The error callback is optional, but
highly recommended.
