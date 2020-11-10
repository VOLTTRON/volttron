.. _Simulation_Overview:

================================
Simulation Integration Framework
================================

This framework provides a way to integrate different types of simulation platforms with VOLTTRON.  Integration with
specific simulation platforms are all built upon the `BaseSimIntegration` class which provides common APIs needed to
interface with different types of simulation platforms.  Each of the concrete simulation class extends the
`BaseSimIntegration` class and is responsible for interfacing with a particular simulation platform.  Using these
concrete simulation objects, agents will be able to use the APIs provided by them to participate in a simulation, send
inputs to the simulation and receive outputs from the simulation and act on them.  Currently, we have implementations
for integrating with HELICS, GridAPPSD and EnergyPlus.  If one wants to integrate with a new simulation platform, then
one has to extend the `BaseSimIntegration` class and provide concrete implementation for each of the APIs provided by
the `BaseSimIntegration` class. For details on the `BaseSimIntegration` class, please refer to
``volttron/platform/agent/base_simulation_integration/base_sim_integration.py``


.. toctree::
    specifications/simulation_integration
    Simulation-Configuration
    Simulation-Integration

