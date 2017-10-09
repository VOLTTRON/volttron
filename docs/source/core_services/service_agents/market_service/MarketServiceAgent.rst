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

A given agent participates in one or more markets by inheriting from the
:ref:`base MarketAgent<Developing-Market-Agents>`.
The base MarketAgent handles all of the communication between the agent and the MarketServiceAgent.
The agent only needs to join each market with the
:py:meth:`join_market <volttron.platform.agent.base_market_agent.MarketAgent.join_market>`
method and then respond to the appropriate callback methods.  The callback methods are described at the
:ref:`base MarketAgent<Developing-Market-Agents>`.
