# OpenADRVen Agent

This agent provides the ability to connect to an OpenADR Virtual Top Node (VTN) via an OpenADR Virtual End Node (VEN). 
OpenADR (Automated Demand Response) is a standard for alerting and responding to the need to adjust electric power
consumption in response to fluctuations in grid demand. 

## Requirements

The OpenADRVen agent requires the openleadr pacakage. This package can be installed in an activated enviroment with:

```shell
pip install openleadr
```

## VTN Server setup

Depending on the type of VTN that you are using, you need to configure your VTN to send events so that the OpenADRVen agent
can receive such events from your VTN.

### IPKeys VTN setup

The community is currently testing this OpenADRVen agent against a IPKeys VTN. To configure the agent with the right
certificates, follow the instructions below:

* Get VEN certificates at https://testcerts.kyrio.com/#/. Certificates can be stored anywhere on your machine, however,
it is recommended to place your keypair files in your ~/.ssh/ folder and make those files read-only.

* Login to the IPKeys VTN web browser console at https://eiss2demo.ipkeys.com/ui/home/#/login

* To create an event, click "Events" tab. Then click the "+" icon to create an event. Use the template "PNNLTestEvent" or
"PNNLnontestevent" to create an event.

## Configuration

The required parameters for this agent are "ven_name", "vtn_url", and "openadr_client_type". Below is an example of a
correct configuration with optional parameters added.

```jsonpath
    {
        "ven_name": "PNNLVEN",
        "vtn_url": "https://eiss2demo.ipkeys.com/oadr2/OpenADR2/Simple/2.0b",
        "openadr_client_type": "IPKeysClient" # the list of valid client types are the class names of the OpenADRClient subclasses in ~openadr_ven/volttron_openadr_client.py

        # below are optional configurations

        # if you want/need to sign outgoing messages using a public-private key pair, provide the relative path to the cert_path and key_path
        # in this example, the keypair is stored in the directory named '~/.ssh/secret'
        "cert_path": "~/.ssh/secret/TEST_RSA_VEN_210923215148_cert.pem",
        "key_path": "~/.ssh/secret/TEST_RSA_VEN_210923215148_privkey.pem",

        # other optional configurations
        "debug": true,
        # if you are connecting to a legacy VTN (i.e. not conformant to OpenADR 2.0) you might want
        # to disable signatures when creating messages to be sent to a legacy VTN.
        "disable_signature": true
    }
```

Save this configuration in a JSON file in your preferred location. An example of such a configuration is saved in the
root of the OpenADRVenAgent directory; the file is named `config_example1.json`



## Installing the agent

* Start the Volttron platform on your machine.

```shell
volttron -vv -l volttron.log &
```

* Tail the logs so that you can observe the logs coming from the Volttron OpenADR VEN agent.

```shell
tail -f volttron.log
```

* Install the agent on Volttron in a secondary shell.

Open a secondary shell and run the following command:

```shell
vctl install <path to root directory of volttron-openadr-ven> \
--tag openadr \
--agent-config <path to agent config>
```

* Verify status of agent.

```shell
vctl status
```

* Start the agent.

```shell
vctl start --tag openadr
```


## Notes

The OpenADRVen agent uses a third-party library, [OpenLeader](https://openleadr.org/docs/index.html), as the actual client.
However, the OpenADRVen agent had to modify some parts of that client in order to connect to the IPKeys VTN for testing. Specifically,
OpenADRVen agent extends the OpenLeadr client class and overrides some class methods.

Those parts that were modified are located in ~/volttron_openadr_ven/volttron_openleadr.py. Future releases of OpenLeadr could potentially and adversely
affect OpenADRVen agent if those releases directly or indirectly affect the modified code blocks. Thus, maintenance of this agent should closely monitor future changes to OpenLeadr.
