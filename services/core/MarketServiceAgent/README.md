# Market Service Agent

The Market Service Agent is used to allow agents to use transactive markets
to implement transactive control strategies.  The Market Service Agent provides
an implementation of double blind auction markets that can be used by multiple agents.

Agents that want to use the Market Service Agent inherit from the :ref:`base MarketAgent<Developing-Market-Agents>`.
The base MarketAgent handles all of the communication between the agent and the MarketServiceAgent.

## Configuration

1. "market_period" - The time allowed for a market cycle in seconds. After this amount of time the market starts again.
   Defaults to 300.
2. "reservation_delay" - The time delay between the start of a market cycle and the start of gathering market 
   reservations in seconds. Defaults to 0.
3. "offer_delay" - The time delay between the start of gathering market reservations and the start of gathering market 
   bids/offers in seconds. Defaults to 120.
4. "verbose_logging" - If True this enables verbose logging.  If False, there is little or no logging. Defaults to True.


## Sample configuration file

``` {.python}
    {
        "market_period": 300,
        "reservation_delay": 0,
        "offer_delay": 120,
        "verbose_logging": True
    }
```
