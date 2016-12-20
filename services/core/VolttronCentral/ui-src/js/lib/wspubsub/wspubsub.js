"use strict";

var WsPubSubError = require('./error');

var sockets = {}
 
 function bind(fn, me) { 
    return function() { 
        return fn.apply(me, arguments); 
    }; 
};

function setAuthorization(authorization) {
    window.authorization = authorization;
    //authorization = authorization;
}

function _buildEndpoint(suffix) {
    let prefix = (window.location.protocol === "https:" ? "wss://" : "ws://");
    let ws_root = prefix + window.location.host;
    return ws_root + "/vc/ws/" + window.authorization + "/" + suffix
}

function open_management_ws(onmessage) {
    let endpoint = _buildEndpoint("management");
    if (sockets[endpoint] == null){

        sockets[endpoint] = new SuperSocket(endpoint);
    }
    sockets[endpoint].addOnMessageCallback(onmessage);
}

function open_configure_ws(onmessage) {
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

function open_iam_ws(onmessage) {
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
        console.log('IN ONMESSAGE');
        console.log(event)
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
          results.push(callback.call(this, event));
        }
        return results;   
    }

    onErorr(event) {
        var callback, i, len, ref, results;
        ref = this.callbacks;
        results = [];
        for (i = 0, len = ref.length; i < len; i++) {
          callback = ref[i];
          results.push(callback.call(this, event));
        }
        return results;
    }
}


/*
class SuperWebSocket
    @getConnection: (url)->
        superSockets[url] ?= new SuperWebSocket url
        superSockets[url]

    constructor: (url)->
        if arguments.callee.caller != SuperWebSocket.getConnection
            throw new Error "Calling the SuperWebSocket constructor directly is not allowed. Use SuperWebSocket.getConnection(url)"
        @ws = new WebSocket url
        events = ['open', 'close', 'message', 'error']
        @handlers = {}
        events.forEach (event)=>
            @handlers[event] = []
            @ws["on#{event}"] = (message)=>
                if message?
                    try
                        message = JSON.parse message.data
                    catch error
                for handler in @handlers[event]
                    handler message
                null

    on: (event, handler)=>
        @handlers[event] ?= []
        @handlers[event].push handler
        this

    off: (event, handler)=>
        handlerIndex = @handlers[event].indexOf handler
        if handlerIndex != -1
            @handlers[event].splice handlerIndex, 1
        this

    clear: (event)=>
        @handlers[event] = []
        this_session_key(session_key)

function add_management_callback(fn){

}

class WsPubSub{
    constructor(){
        console.log(window.vc_websockets);
        if (typeof someUndeclaredVariable === "undefined") {
            window.vc_websockets = this;    
        }
        else{
            console.log('Websocketpubsub already constructed');
            return window.vc_websockets;
        }
        console.log('Constructing wspubsub')
        let prefix = (window.location.protocol === "https:" ? "wss://" : "ws://");
        let ws_root = prefix + window.location.host;
        this.url = ws_root;
        this.session = null;
        this.subscriptions = {};
        this.websockets = {};

        return this;
    }

    set_authorization_key(session_key) {
        this.session = session_key;
    }

    _require_session_key(){
        if (this.session == null) {
            throw new WsPubSubError({
                message: "Session not set in WsPubSub"
            });
        }
    }

    _build_topic(prefix, suffix){
        return prefix + '/' + this.session + '/' + suffix
    }

    open_management_socket(onmessage) {
        this._require_session_key();
        let topic = this._build_topic("/vc/ws", "management");
        this.subscribe(topic, onmessage);
    }

    open_iam_socket(onmessage) {
        this._require_session_key();
        let topic = this._build_topic("/vc/ws", "iam");
        this.subscribe(topic, onmessage);

    }

    open_configure_socket(onmessage) {
        this._require_session_key();
        let topic = this._build_topic("/vc/ws", "configure");
        this.subscribe(topic, onmessage);        
    }

    // setSessionKey(session_key){
    //     this.session = session_key
    // }

    // TODO this works but it sucks.  The WsPub doesn't get elevated to global on the
    // page so that when a socket event is happening it is almost like a new scope is
    // added.  Perhaps we need to use window.WSPubsub somewhere to make it global?

    subscribe(topic, onmessage){

        let self = this;
        let wspath = this.url + topic;
        let ws = null;

        if (!this.websockets.hasOwnProperty(topic)){
            this.subscriptions[topic] = [];
        

            if (window.WebSocket) {
                ws = new WebSocket(wspath);
            }
            else if (window.MozWebSocket) {
                ws = MozWebSocket(wspath);
            }

            this.websockets[topic] = ws;

            ws.onerror = function(evt) {
                console.log("ERROR: ");
                console.log(evt);
            }

            ws.onopen = function(evt) {
                console.log("OPENING");
            }

            ws.onmessage = function(evt)
            {

                if(self.subscriptions.hasOwnProperty(topic)){

                    self.subscriptions[topic].forEach(function(cb){
                        cb(topic, evt.data);
                    });
                    // for (cb in self.subscriptions[topic]) {
                    //     console.log('Calling callback for '+ topic)
                    //     cb(topic, evt.data);
                    // }
                }

                else{
                    console.log('No subscription for '+topic);
                }
            }

            ws.onclose = function (evt)
            {

                if(self.subscriptions.hasOwnProperty(topic)){
                    self.subscriptions[topic].forEach(function(cb){
                        cb(this, "CLOSING");
                    }, topic);
                }
                delete self.websockets[topic];
            }
        }

        this.subscriptions[topic].push(onmessage);

    }

    unsubscribe(topic, onmessage) {
        if (!this.subscriptions.hasOwnProperty(topic)){
            throw new WsPubSubError({
                message: "Topic not found in subscriptions."
            });
        }

        this.websockets[topic].forEach(function(ws){
            console.log('Closing sockets')
            ws.close();
        });

        delete this.websockets[topic];

    }
    //
    // publish(topic, message) {
    //
    // }
}

let ws = new WsPubSub();*/


module.exports = {
    openManagementWS: open_management_ws,
    openConfigureWS: open_configure_ws,
    openIAmWS: open_iam_ws,
    setAuthorization: setAuthorization
} // let pubsub = ws; //let pubsub =  new WsPubSub(ws_root);