"""
Agent to demonstrate how to make prediction requests to a Tensor_Model_Server serving a trained 'mnist' model.
Tensorflow client code for GRPC request is taken from
https://github.com/tensorflow/serving/tree/master/tensorflow_serving/example
And license information is available at https://github.com/tensorflow/serving/blob/master/LICENSE
"""

__docformat__ = 'reStructuredText'

from datetime import datetime
import gevent
import logging
import sys
import requests
import threading
import tensorflow as tf
import numpy as np
import grpc
from .mnist_input_data import read_data_sets
from tensorflow_serving.apis import predict_pb2
from tensorflow_serving.apis import prediction_service_pb2_grpc

from volttron.platform.agent import utils
from volttron.platform.vip.agent import Agent, Core, RPC

_log = logging.getLogger(__name__)
utils.setup_logging()
__version__ = "0.1"


def tensorflow_agent(config_path, **kwargs):
    """Parses the Agent configuration and returns an instance of
    the agent created using that configuration.

    :param config_path: Path to a configuration file.

    :type config_path: str
    :returns: TensorflowAgent
    :rtype: TensorflowAgent
    """
    try:
        config = utils.load_config(config_path)
    except Exception:
        config = {}

    if not config.get("hostport"):
        raise ValueError("Configuration must have a hostport entry.")
    hostport = config.get("hostport")

    api_request_type = config.get("api_request_type", "grpc")

    return TensorflowAgent(hostport, model_name, model_version, api_request_type, **kwargs)


class TensorflowAgent(Agent):
    """
    Agent that shows how to make request to tensor_model_server using RESTfull/Google RPC request APIs
    """

    def __init__(self, config, hostport, **kwargs):
        super(TensorflowAgent, self).__init__(enable_store=False, **kwargs)
        self.default_config = {
            "hostport": hostport,
            "model_name": "mnist",
            "model_version": "v1",
            "api_request_type": "grpc"
        }
        if config:
            self.default_config.copy(config)
        self.vip.config.set_default("config", self.default_config)
        self.vip.config.subscribe(self.configure_main,
                                  actions=["NEW", "UPDATE"],
                                  pattern="config")

        model_name = self.default_config.get("model_name")
        model_version = self.default_config.get("model_version")
        self.api_type = self.default_config.get("api_request_type")
        # The server URL specifies the endpoint of your server running the
        # model with the model name and using the predict interface.
        self.SERVER_URL = f'http://{hostport}/{model_version}/models/{model_name}:predict'

        self.num_tests = 100
        self.work_dir = "/tmp"
        self.config_update = False
        self.hostport = hostport

    def configure_main(self, config_name, action, contents, **kwargs):
        config = self.default_config.copy()
        config.update(contents)
        _log.debug("Update agent %s configuration -- config --  %s", self.core.identity, config)
        if action == "NEW" or "UPDATE":
            self.api_type = config.get("request_type")
            self.hostport = config.get("hostport")
            model_name = config.get("model_name")
            model_version = config.get("model_version")
            self.SERVER_URL = f'http://{self.hostport}/{model_version}/models/{model_name}:predict'
            self.prediction_request()
            self.config_update = True

    def prediction_request(self):
        if self.api_type == "grpc":
            self.core.spawn_later(5, self.prediction_request_via_grpc)
        else:
            self.core.spawn_later(5, self.prediction_request_via_rest_api)

    def prediction_request_via_rest_api(self):
        """
        Make prediction request to find error rate using REST api
        :return:
        """
        test_data_set = read_data_sets(self.work_dir).test
        error_cnt = 1
        for t in range(self.num_tests):
            batch_size = 1
            image, label = test_data_set.next_batch(1)
            batch = np.repeat(image, batch_size, axis=0).tolist()
            # Build signature definition for the request
            json_request = {
                "signature_name": 'predict_images',
                "instances": batch
            }

            response = requests.post(self.SERVER_URL, json=json_request)
            resp = response.json()['predictions'][0]
            prediction = np.argmax(resp)
            # Increment error count if prediction label does not match
            if label != prediction:
                error_cnt += 1
        error_rate = error_cnt / float(self.num_tests)
        _log.debug(f"PREDICTION error rate for mnist model via rest api: {error_rate}")

    def prediction_request_via_grpc(self):
        """
        Make prediction request using GRPC api to find error rate in prediction
        """
        _log.debug("prediction_request_via_grpc")
        test_data_set = read_data_sets(self.work_dir).test
        channel = grpc.insecure_channel(self.hostport)
        stub = prediction_service_pb2_grpc.PredictionServiceStub(channel)
        concurrency = 1
        result_counter = _ResultCounter(self.num_tests, concurrency)
        for _ in range(self.num_tests):
            request = predict_pb2.PredictRequest()
            request.model_spec.name = 'mnist'
            request.model_spec.signature_name = 'predict_images'
            image, label = test_data_set.next_batch(1)
            request.inputs['images'].CopyFrom(
                tf.make_tensor_proto(image[0], shape=[1, image[0].size]))
            result_counter.throttle()
            result_future = stub.Predict.future(request, 5.0)  # 5 seconds
            result_future.add_done_callback(
                self._create_rpc_callback(label[0], result_counter))
        _log.debug(f"PREDICTION ERROR rate for mnist model via grpc call: {result_counter.get_error_rate()}")

    def _create_rpc_callback(self, label, result_counter):
        """Creates RPC callback function.

      Args:
        label: The correct label for the predicted example.
        result_counter: Counter for the prediction result.
      Returns:
        The callback function.
      """

        def _callback(result_future):
            """Callback function.

        Calculates the statistics for the prediction result.

        Args:
          result_future: Result future of the RPC.
        """
            exception = result_future.exception()
            if exception:
                result_counter.inc_error()
                print(exception)
            else:
                sys.stdout.write('.')
                sys.stdout.flush()
                response = np.array(
                    result_future.result().outputs['scores'].float_val)
                prediction = np.argmax(response)
                if label != prediction:
                    result_counter.inc_error()
            result_counter.inc_done()
            result_counter.dec_active()

        return _callback


class _ResultCounter(object):
    """Counter for the prediction results."""

    def __init__(self, num_tests, concurrency):
        self._num_tests = num_tests
        self._concurrency = concurrency
        self._error = 0
        self._done = 0
        self._active = 0
        self._condition = threading.Condition()

    def inc_error(self):
        with self._condition:
            self._error += 1

    def inc_done(self):
        with self._condition:
            self._done += 1
            self._condition.notify()

    def dec_active(self):
        with self._condition:
            self._active -= 1
            self._condition.notify()

    def get_error_rate(self):
        with self._condition:
            while self._done != self._num_tests:
                self._condition.wait()
            return self._error / float(self._num_tests)

    def throttle(self):
        with self._condition:
            while self._active == self._concurrency:
                self._condition.wait()
            self._active += 1


def main():
    """Main method called to start the agent."""
    utils.vip_main(tensorflow_agent, version=__version__)


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
