"use strict";

var WsPubSubError = require('./error');

class WsPubSub{
    constructor(){
        let prefix = (window.location.protocol === "https:" ? "wss://" : "ws://");
        let ws_root = prefix + window.location.host;
        this.url = ws_root;
        this.session = null;
        this.subscriptions = {};
        this.websockets = {};

        return this;
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
        // if (this.session == null){
        //     throw new WsPubSubError({"message":
        //         "Must setSessionKey before subscription"});
        // }
        // if (topic in this.subscriptions) {
        //
        // }
//        if (!this.websockets.hasOwnProperty(topic)){
        if (!this.websockets.hasOwnProperty(topic)){
            this.websockets[topic] = new Set();
        }

            if (window.WebSocket) {
                ws = new WebSocket(wspath);
            }
            else if (window.MozWebSocket) {
                ws = MozWebSocket(wspath);
            }

            self.websockets[topic].add(ws);

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

                self.websockets.delete(this);
                var topic = this;

                if(self.subscriptions.hasOwnProperty(topic)){
                    self.subscriptions[topic].forEach(function(cb){
                        cb(this, "CLOSING");
                    }, topic);
                }
                delete self.websockets[topic];
            }.bind(ws)
  //      }

        if (!self.subscriptions.hasOwnProperty(topic)){
            self.subscriptions[topic] = new Set();
        }

        self.subscriptions[topic].add(onmessage);

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

let ws = new WsPubSub();

export let pubsub = ws; //let pubsub =  new WsPubSub(ws_root);