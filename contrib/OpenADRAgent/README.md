# OpenRTU - OpenADR/ VoltTron Lite Agent

This project is a collaboration between [EnerNOC](http://open.enernoc.com/) 
and the [Demand Response Research Center](http://drrc.lbl.gov/) at Lawrence 
Berkeley National Labs to create a simple OpenADR 2.0a agent for the VoltTron 
framework which was developed by PNNL.  

[VoltTron documentation](https://svn.pnl.gov/RTUNetwork/wiki)

[OpenADR client documentation](https://github.com/EnerNOC/oadr2-ven-python)


## Installation

Start by getting the Volttron Lite platform up and running: [RTUNetwork build 
instructions](https://svn.pnl.gov/RTUNetwork/wiki/BuildingTheProject).

You can find the [Volttron Lite source here](https://bitbucket.org/berkeleylab/rtunetwork/overview)

The dependencies for the agent are included in the requirements.txt. Obviously, these
need to be available in whatever environment you use to run the agent.

## Configuration

In order to use the OpenADR agent, you'll need an OpenADR VTN to communicate with.
The EnerNOC open source VTN is [available here](https://github.com/EnerNOC/oadr2-vtn-new).
Follow the instructions to get it set up and running locally.

You'll need to edit the launch.json for this agent as follows:

### ven_id

Regardless of what VTN you're using, you will have to set up a VEN id to
assign to the OpenADR agent. If you're using the EnerNOC VTN, click on
the "VENs" tab and create a new VEN. Associate it with a program and
assign it a VEN Name and a VEN ID. Copy the VEN ID to your launch.json.

### vtn_uri
This is the URI at which your VEN can be reached. If you're running the
EnerNOC VTN this will probably be: http://localhost:8080/oadr2-vtn-groov

### vtn_ids
This is the identifier for the VTN that you are communicating with. Again,
if you're using the EnerNOC VTN, the default id is: ENOCtestVTN1

### sMAP config
The sMAP config is pretty straight forward and defines where the event
data will be stored in sMAP.

## Messages

When this agent receives a new or updated OpenADR event payload, it will
publish some important fields to the message bus. The agent also publishes
a "heartbeat" that broadcasts whether or not any events are currently active.

## Future Development

As the usecase around this agent becomes more defined, we can easily update
the structure of the published messages to be as useful as possible to other
agents.



## License & Copyright

This was written by [Thom Nichols](mailto:tnichols@enernoc.com) of EnerNOC
and [Dave Riess](mailto:driess@lbl.gov) of LBNL.

&copy; 2013 
EnerNOC Inc.
