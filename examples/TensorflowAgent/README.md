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

2. Go to VOLTTRON source directory. Activate the environment and Install Tensorflow and Tensorflow Serving APIs for client within the activated environment.

    a. Install Tensorflow python package

    ```
    pip install --upgrade pip
    pip install tensorflow==2.1.0
    pip install tensorflow-serving-api
    ```

3. Open another teminal. Clone tensorflow serving source code from git

    ```
    cd ~
    git clone https://github.com/tensorflow/serving.git
    
    ```

4. Activate VOLTTRON environment and run example Tensorflow script to train a 'mnist' model and save the model in specified path after training is complete. Since tensorflow package is installed within VOLTTRON's environment we need to run this example script in a VOLTTRON activated terminal.

    ```
    cd ~/serving/tensorflow_serving/example
    python mnist_saved_model.py --work-dir ~/test_mnist_dir
    ```

5. Open another terminal (outside VOLTTRON environment) and start running Tensorflow Serving and load our saved model. After it loads we can start making inference requests either using REST (serves on port 8501) or GRPC apis (serves on port 8500). There are some important parameters:

    - rest_api_port: The port that you'll use for REST requests.
    - model_name: You'll use this in the URL of REST requests. It can be anything.
    - model_base_path: This is the path to the directory where you've saved your model.

    ```
    tensorflow_model_server --rest_api_port=8501 --model_name=mnist --model_base_path=/home/volttron/test_mnist_dir

    2020-05-04 08:35:00.783339: I tensorflow_serving/model_servers/server_core.cc:462] Adding/updating models.
    2020-05-04 08:35:00.783368: I tensorflow_serving/model_servers/server_core.cc:573]  (Re-)adding model: mnist
    2020-05-04 08:35:00.887364: I tensorflow_serving/core/basic_manager.cc:739] Successfully reserved resources to load servable {name: mnist version: 1}
    2020-05-04 08:35:00.887397: I tensorflow_serving/core/loader_harness.cc:66] Approving load for servable version {name: mnist version: 1}
    2020-05-04 08:35:00.887409: I tensorflow_serving/core/loader_harness.cc:74] Loading servable version {name: mnist version: 1}
    2020-05-04 08:35:00.887428: I external/org_tensorflow/tensorflow/cc/saved_model/reader.cc:31] Reading SavedModel from: /home/volttron/test_mnist_dir/1
    2020-05-04 08:35:00.892463: I external/org_tensorflow/tensorflow/cc/saved_model/reader.cc:54] Reading meta graph with tags { serve }
    2020-05-04 08:35:00.892499: I external/org_tensorflow/tensorflow/cc/saved_model/loader.cc:264] Reading SavedModel debug info (if present) from: /home/volttron/test_mnist_dir/1
    2020-05-04 08:35:00.894931: I external/org_tensorflow/tensorflow/core/platform/cpu_feature_guard.cc:142] Your CPU supports instructions that this TensorFlow binary was not compiled to use: AVX2
    2020-05-04 08:35:00.956586: I external/org_tensorflow/tensorflow/cc/saved_model/loader.cc:203] Restoring SavedModel bundle.
    2020-05-04 08:35:01.036182: I external/org_tensorflow/tensorflow/cc/saved_model/loader.cc:152] Running initialization op on SavedModel bundle at path: /home/volttron/test_mnist_dir/1
    2020-05-04 08:35:01.070318: I external/org_tensorflow/tensorflow/cc/saved_model/loader.cc:333] SavedModel load for tags { serve }; Status: success: OK. Took 182879 microseconds.
    2020-05-04 08:35:01.070663: I tensorflow_serving/servables/tensorflow/saved_model_warmup.cc:105] No warmup data file found at /home/volttron/test_mnist_dir/1/assets.extra/tf_serving_warmup_requests
    2020-05-04 08:35:01.070856: I tensorflow_serving/core/loader_harness.cc:87] Successfully loaded servable version {name: mnist version: 1}
    2020-05-04 08:35:01.085097: I tensorflow_serving/model_servers/server.cc:358] Running gRPC ModelServer at 0.0.0.0:8500 ...
    2020-05-04 08:35:01.092899: I tensorflow_serving/model_servers/server.cc:378] Exporting HTTP/REST API at:localhost:8501 ...
    [evhttp_server.cc : 238] NET_LOG: Entering the event loop ...
    ```


Configure Tensorflow agent with Tensorflow model server's hostname, port, model version, model name and the request type

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

## Run the agent

1. Start the VOLTTRON platform

```
source env/bin/activate
./start-volttron
```

2. Start the tensorflow agent. The agent make prediction request for a set of images a pre-set number of times (100) and calculates prediction error rate. The request is made 
using GRPC request APIs

```
python scripts/install-agent.py -s examples/TensorflowAgent/ -c examples/TensorflowAgent/config.yml -i tensorflowagent_grpc --start
```

Check for the below line in volttron.log

```
__main__ DEBUG: PREDICTION error rate for mnist model via grpc api: 0.07
```

3. Install the same agent again but this time change configuration such that request is made via REST api


```` yml

#hostname/ipaddress of tensor_model_server and port number
#Default port number for serving GPRC API requests -> 8500
#Default port number for serving REST API requests -> 8501
hostport: localhost:8501
#Version number of the model
model_version: v1
#Model name
model_name: mnist
#Request type -> grpc or rest
api_request_type: rest


````

```
python scripts/install-agent.py -s examples/TensorflowAgent/ -c examples/TensorflowAgent/config.yml -i tensorflowagent_rest --start
```

Check for the below line in volttron.log

```
__main__ DEBUG: PREDICTION error rate for mnist model via rest api: 0.08

```

