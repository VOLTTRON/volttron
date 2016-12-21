"use strict";

var WsPubSubError = require('./error');

var sockets = {}
var authorization = null;
 
function bind(fn, me) { 
    return function() { 
        return fn.apply(me, arguments); 
    }; 
};

function setAuthorization(auth) {
    authorization = auth;
}

function _buildEndpoint(suffix) {
    let prefix = (window.location.protocol === "https:" ? "wss://" : "ws://");
    let ws_root = prefix + window.location.host;
    return ws_root + "/vc/ws/" + authorization + "/" + suffix
}

function openManagementWS(onmessage) {
    let endpoint = _buildEndpoint("management");
    if (sockets[endpoint] == null){

        sockets[endpoint] = new SuperSocket(endpoint);
    }
    sockets[endpoint].addOnMessageCallback(onmessage);
}

function openConfigureWS(onmessage) {
    let endpoint = _buildEndpoint("configure");
    if (sockets[endpoint] == null){
        console.log("Creating new SuperSocket for configure")
        sockets[endpoint] = new SuperSocket(endpoint);
    }
    else {
        console.log("Using existing socket.")
    }
    sockets[endpoint].addOnMessageCallback(onmessage);
}

function openIAmWS(onmessage) {
    let endpoint = _buildEndpoint("iam");
    if (sockets[endpoint] == null){
        sockets[endpoint] = new SuperSocket(endpoint);
    }
    sockets[endpoint].addOnMessageCallback(onmessage);
}

class SuperSocket { 

    constructor(endpoint) {

        if (window.WebSocket) {
            this.ws = new WebSocket(endpoint);
        }
        else if (window.MozWebSocket) {
            this.ws = MozWebSocket(endpoint);
        }

        this.endpoint = endpoint;
        this.onMessage = bind(this.onMessage, this);
        this.ws.onmessage = this.onMessage;
        this.ws.onerror = this.onError;
        this.ws.onclose = this.onClose;
        this.callbacks = [];
    }

    addOnMessageCallback(callback) {
        return this.callbacks.push(callback);
    }

    onMessage(event) {
        var callback, i, len, ref, results;
        ref = this.callbacks;
        results = [];

        for (i = 0, len = ref.length; i < len; i++) {
          callback = ref[i];
          results.push(callback.call(this, event.data));
        }
        return results;        
    }

    onClose(event) {
        var callback, i, len, ref, results;
        ref = this.callbacks;
        results = [];
        for (i = 0, len = ref.length; i < len; i++) {
          callback = ref[i];
          results.push(callback.call(this, event.data));
        }
        return results;   
    }

    onErorr(event) {
        var callback, i, len, ref, results;
        ref = this.callbacks;
        results = [];
        for (i = 0, len = ref.length; i < len; i++) {
          callback = ref[i];
          results.push(callback.call(this, event.data));
        }
        return results;
    }
}


module.exports = {
    openManagementWS: openManagementWS,
    openConfigureWS: openConfigureWS,
    openIAmWS: openIAmWS,
    setAuthorization: setAuthorization
} // let pubsub = ws; //let pubsub =  new WsPubSub(ws_root);