Attached are the two agents that implement the load shaping algorithm developed by Olama and the team. I wanted to send you this sooner than later since you have deliverables based on this and I'll be on business travel through Wednesday. I have yet to run a few more validation tests to run but I've got the code running on 6 RPis, all on the same wireless ad-hoc network, with one as the master node.

Attached you'll find two agents:
MasterNodeAgent: This is the agent that does most of the work. It reads in three CSV files (please place these files in the agent-data directory of the install location; didn't explicitly package these in the setup.py) which contain regulation signal and outside air temperatures. The master node agent has a  "numberOfBuildings" : 1 value in its config file. I set this to 5 since I had 5 physical RPi model nodes. It should be set to the number of client nodes you plan to test on. The code only considers the cooling scenario with 2 stage hvac with consumption of 3 and 6 kw for the two stages. Heating is not considered as this is for a cooling day in May although I've coded it in a way to make it extensible.  The main periodic control function in reality was designed to run every 10 minutes. I set it to 2 seconds just to see my code run quickly. The MasterNode also computes all the ODEs for the clients currently. Future work should include making this ODE solving more distributed. 

ModelNodeAgent: This is a simple agent that registers itself with the master and then simply switches on and off as instructed by the master node. I installed this on 5 R-Pis and changed the numeric #  for "modelnodeplatform" : "modelnode0" in the config file to be unique. I went from 4 to 8 just because their IPs were 192.168.1.4 to ...8 and I just used the last octet. Fewer things to remember. The modelnodeplatform identifier is used by the masternode to publish node specific commands on the Volttron bus.

Both agents use the MultiBuilding Service agent to talk across nodes. The config file for the master node listed all the pub/sub platforms something like (my master node ip was 192.168.1.3):

{
    "building-publish-address": "tcp://0.0.0.0:12201",
    "building-subscribe-address": "tcp://0.0.0.0:12202",
    "uuid": "MultiBuildingService",
    "hosts": {
        "ORNL/masternode": {
            "pub": "tcp://192.168.1.3:12201",
            "sub": "tcp://192.168.1.3:12202"
        },
        "ORNL/modelnode4": {
            "pub": "tcp://192.168.1.4:12201",
            "sub": "tcp://192.168.1.4:12202"
        }, 
       "ORNL/modelnode5": {
            "pub": "tcp://192.168.1.5:12201",
            "sub": "tcp://192.168.1.5:12202"
        }, 
       "ORNL/modelnode6": {
            "pub": "tcp://192.168.1.6:12201",
            "sub": "tcp://192.168.1.6:12202"
        }, 
        "ORNL/modelnode7": {
            "pub": "tcp://192.168.1.7:12201",
            "sub": "tcp://192.168.1.7:12202"
        },
        "ORNL/modelnode8": {
            "pub": "tcp://192.168.1.8:12201",
            "sub": "tcp://192.168.1.8:12202"
        }
    }
}

The same for a model node had only two entries, itself, and the masternode, example for modelnode4:
{
    "building-publish-address": "tcp://0.0.0.0:12201",
    "building-subscribe-address": "tcp://0.0.0.0:12202",
    "uuid": "MultiBuildingService",
    "hosts": {
        "ORNL/masternode": {
            "pub": "tcp://192.168.1.3:12201",
            "sub": "tcp://192.168.1.3:12202"
        },
        "ORNL/modelnode4": {
            "pub": "tcp://192.168.1.4:12201",
            "sub": "tcp://192.168.1.4:12202"
        } 
    }
}

Note that you must start the master node first, then the modelnodes since each modelnode tries to register with master on init, and it just assumes the master node is up. It is also important to fire up the multibuilding service before anything else on the platforms.

Let me know if you have questions. I'll be working on this more after I return but I hope this will get you guys started.

Best,
Jibo



