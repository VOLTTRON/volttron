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
        if (!this.websockets.hasOwnProperty(topic)){

            if (window.WebSocket) {
                ws = new WebSocket(wspath);
            }
            else if (window.MozWebSocket) {
                ws = MozWebSocket(wspath);
            }

            self.websockets[topic] = ws;

            ws.onerror = function(evt) {
                console.log("ERROR: ");
                console.log(evt);
            }

            ws.onopen = function(evt) {
                console.log("OPENING: " + evt.data);
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
                        cb(topic, "CLOSING");
                    });
                }
                delete self.websockets[topic]
            }
        }

        if (!self.subscriptions.hasOwnProperty(topic)){
            self.subscriptions[topic] = new Set();
        }

        self.subscriptions[topic].add(onmessage)

    }

    unsubscribe(topic, onmessage) {
        if (!this.subscriptions.hasOwnProperty(topic)){
            throw new WsPubSubError({
                message: "Topic not found in subscriptions."
            });
        }
    }
    //
    // publish(topic, message) {
    //
    // }
}

export let pubsub = new WsPubSub(); //let pubsub =  new WsPubSub(ws_root);