.. _SimulationIntegrationSpec:
 
===================================================================
Specification For Simplifying Integration With Simulation Platforms
===================================================================
 
There are several simulation platforms that can be integrated with VOLTTRON
to run as a single cohesive simulated environment for different type of
applications. Some of the platforms are FNCS, HELICS, GridApps-D and
EnergyPlus. They all have unique application areas and differ in the type
of inputs they accept etc., but are similar in some of the basic steps   
in-terms of integrating with VOLTTRON.
 
1. Start simulation
2. Subscribe to outputs from the simulation
3. Publish outputs from simulation to VOLTTRON
4. Subscribe to topics from VOLTTRON
5. Send inputs to simulation
6. Advance simulation timestep
7. Pause simulation
8. Resume simulation
9. Stop simulation

Currently, VOLTTRON has individual implementations for integrating with
many of the above simulation platforms. Instead, in this specfication we
are proposing a base simulation integration class that will provide 
common APIs and concrete simulation integration classes that will have 
implementation of the these APIs as per the needs of the individual
simulation platforms. Users can use appropriate simulation classes based on
which simulation platform they want to integrate with.

*********
Features:
*********

1. Start simulation
    This will start the simulation or register itself to be participant in 
    the simulation.

2. Register for inputs from simulation
    A list of points need to be made available in a config file. The inputs 
    are then read from the config file and registered with simulation platform. 
    Whenever there is any change in those particular points, they are made
    available to this class to process. The agent using this class object 
    can process it or publish it over VOLTTRON message bus to be consumed by
    other agents.

3. Send outputs to simulation


4. Simulation time management
    Typically, in a simulation environment, one can applications in real time 
    mode or in fast execution mode. All the participants in the simulation have
    to be in sync with respect to time for simulation to be correct. There is 
    typically a central unit which acts as a global timekeeper. This timekeeper 
    can possibly be configured to use periodic time keeping, which means it 
    periodically advances in time (based on pre-configured time period). After 
    each advancement, it would send out all the output messages to the 
    registered participants. Another way of advancing the Subscribemulation 
    would be based on concept of time request-time grant. Each of the 
    participants would request for certain time after Insteadt is done with its
    work and get blocked until that is granted. The global time keeper would 
    grant time (and hence advance in simulation) that is lowest among the list
    of time requests.

5. Pause the simulation
    Some simulation platforms can pause the simulation if needed. We need provide
    wrapper API to call simulation specific pause API.

6. Resume the simulation
    Some simulation platforms can resume the simulation if needed. We need provide
    API to call simulation specific resume API.

7. Stop the simulation
    This will unregister itself from the simulation and stop the simulation. 

****
APIs
****

1. start_simulation
    - Connect to the simulation platform.
    - Register with the platform as a participant

2. register_inputs(topic_list)
    - Register with the simulation platform with list of topics

3. send_to_simulation(topic, message)
    - Send message to simulation

4. make_time_request
    - Make request to simulation to advance to next time delta

5. pause_simulation
    - Pause simulation

6. resume_simulation
    - Resume simulation

7. stop_simulation
    - Stops the simulation