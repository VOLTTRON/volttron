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

The MarketServiceAgent can be used with either the Director or the SynchronizedDirector.  The Director
drives the MarketServiceAgent through a timed loop and the SynchronizedDirector drives the MarketServiceAgent
with events so that you can run a simulation faster than real-time.  The Director has just a few parameters
that are configured by default with adequate values.  They are:

1. The market_period with a default value of 5 minutes
2. The reservation_delay with a default value of 0 minutes
3. The offer_delay with a default value of 2 minutes
4. The clear_delay with a default value of 2 minutes

The timing loop works as follows:

* The market period begins.
* A request for reservations is published after the reservation delay.
* A request for offers/bids  is published after the offer delay.
* The cleared price is published after the clear delay.
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
A market will only exist if there are reservations for at least one buyer and at least one seller.
If the market fails to achieve the minimum participation the error callback will be called.

Offer Callback
--------------

If the agent has made a reservation for the market this routine is called.
If the agent wishes to make an offer at this time the market agent computes either supply or
demand curves as appropriate and offers them to the market service by calling the make offer method.
For each market joined either an offer callback or an aggregate callback is required.
You can’t supply both for any single market.

Aggregate Callback
------------------

When a market has received all its buy offers it calculates an aggregate demand curve.
When the market receives all of its sell offers it calculates an aggregate supply curve.
This callback delivers the aggregate curve to the market agent whenever the appropriate curve becomes available.
If the market agent want to use this to make an offer it would do that using the make offer method.
For each market joined either an offer callback or an aggregate callback is required.
You can’t supply both for any single market.

Price Callback
--------------

This callback is called when the market clears. The price callback is optional.

Error Callback
--------------

This callback is called at appropriate time points or when an error occurs.
If a market fails to form this will be called at the offer time.
If the market doesn’t receive all its offers this will be called at market clear time.
If the market fails to clear this would be called at the next reservation time.
This allows agents to respond at or near the normal time points.  The error callback is optional.
