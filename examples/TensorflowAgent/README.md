# Tensorflow Example Agent

This is an example agent demonstrating how a tensorflow agent makes request to Tensorflow Model Server 
using RESTfull or Google RPC interface. Tensorflow Model Server is generally used to serve/run a
trained model in a deployment setup. The Tensorflow clients can make requests (for example, prediction,
classification, regression) to Tensorflow Model Server either using RESTful or GRPC APIs. 
For more information about Tensorflow Model Server, please refer to tutorial in 
https://www.tensorflow.org/tfx/serving/serving_basic

Here, tensorflow client behavior is embedded within agent framework which will interact with Tensorflow
Serving with VOLTTRON environment.

The tensorflow client code is taken from https://github.com/tensorflow/serving/tree/master/tensorflow_serving/example/mnist_clint.py
And license information is available at https://github.com/tensorflow/serving/blob/master/LICENSE

# Installing pre-requisite packages
1. Install Tensor Model Server outside VOLTTRON environment

    a. Add TensorFlow Serving distribution URI as a package source (one time setup)
```
echo "deb [arch=amd64] <a href="http://storage.googleapis.com/tensorflow-serving-apt">http://storage.googleapis.com/tensorflow-serving-apt</a> stable tensorflow-model-server tensorflow-model-server-universal" | sudo tee /etc/apt/sources.list.d/tensorflow-serving.list && \
curl <a href="https://storage.googleapis.com/tensorflow-serving-apt/tensorflow-serving.release.pub.gpg">https://storage.googleapis.com/tensorflow-serving-apt/tensorflow-serving.release.pub.gpg</a> | sudo apt-key add -
```
    b. Install Tensor Model Server package
```
apt-get update && apt-get install tensorflow-model-server
``` 
2. Install Tensorflow and Tensorflow Serving APIs for client 

    a. Install Tensorflow python package
    ```
    pip install tensorflow-serving-api
    pip install tensorflow
    ```

## Running the agent.



## Tensorflow Agent Configuration

You can specify the configuration in  yaml format.  The yaml format is specified
below. 

```` yml

#hostname/ipaddress of tensor_model_server and port number
#Default port number for serving GPRC API requests -> 8500
#Default port number for serving REST API requests -> 8501
hostport: localhost:8500
#Version number of the model
model_version: v1
#Model name
model_name: mnist
#Request type -> grpc or rest
api_request_type: grpc


````

## FNCS example federate1

In an activated volttron environment, export LD_LIBRARY_PATH equal to fncs_install/lib.  This is
the only requirement in order for fncs to be located within the environment.  The following
commands will install the agent to a volttron instance.  If the fncs_broker is running
and this is the last federate to be launched, the code should start publishing on fncs to 
devices/abcd (on volttron fncs/abc will be available as well.).

````bash

    (volttron)osboxes@osboxes ~/git/volttron $ export LD_LIBRARY_PATH=<fncs_install>/lib
    (volttron)osboxes@osboxes ~/git/volttron $ python scripts/install-agent.py -s examples/FNCS \
        -c examples/FNCS/federate1.yml -i federate1_test --force --start   

````

