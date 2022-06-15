## Example Simple Web Agent
A simple web enabled agent that will hook up with a VOLTTRON message bus and allow interaction between it via HTTP. This example agent shows a simple file serving agent, a JSON-RPC based call, and a websocket based connection mechanism.

In order to start the simple web agent, we need to bind the VOLTTRON instance to the a web server. We need to specify the address and the port for the web server. For example, if we want to bind the localhost:8080 as the web server we start the VOLTTRON platform as follows:
```
./start-volttron --bind-web-address http://127.0.0.1:8080
```

Once the platform is started, we are ready to install and run the Simple Web Agent: 
```
vctl install examples/SimpleWebAgent/ --tag simpleWebAgent --vip-identity webagent --force --start
```

This will create a web server on http://localhost:8080. The *index.html* file under simpleweb/webroot/simpleweb/ can be any HTML page which binds to the VOLTTRON message bus. This provides a simple example of providing a web endpoint in VOLTTRON.