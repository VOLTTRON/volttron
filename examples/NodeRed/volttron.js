module.exports = function(RED) {
    // Set these variables to be valid file paths
    var volttron_env = '';
    var volttron_home = '';
    var python_path = '';

    function VolttronInputNode(config) {
        RED.nodes.createNode(this,config);
        var node = this;
        var pyshell = null;
        this.on('close', function(done) {
            setTimeout(function() {
                /* do some asynchronous cleanup before calling done */
                if (pyshell && !pyshell.terminated && pyshell.childProcess)
                    pyshell.childProcess.kill('SIGINT');
                done();
            });
        });
        setTimeout(function() {
            var PythonShell = require('python-shell');
            process.env['VIRTUAL_ENV'] = volttron_env;
            process.env['VOLTTRON_HOME'] = volttron_home;
            var options = {
                mode: 'json',
                pythonPath: python_path,
                scriptPath: __dirname,
            };
            var path = require('path');
            node.warn(__dirname);
            var scriptName = 'node_red_subscriber.py';
            var scriptPath = path.resolve(__dirname, scriptName);
            node.warn(scriptPath);
            pyshell = new PythonShell(scriptName, options);

            pyshell.on('message', function (data) {
                msg = {};
                msg.topic = node.name;
                msg.payload = data;
                node.send(msg);
            });

            pyshell.end(function (err) {
                node.error(err);
            });

        });
    }
    RED.nodes.registerType("volttron-input", VolttronInputNode);

    function VolttronOutputNode(config) {
        RED.nodes.createNode(this,config);
        var node = this;
        this.on('close', function(done) {
            setTimeout(function() { /* do some asynchronous cleanup before calling done */ done(); });
        });
        this.on("input", function (msg) {
            setTimeout(function() { // send asynchronously
                var PythonShell = require('python-shell');
                process.env['VIRTUAL_ENV'] = volttron_env;
                process.env['VOLTTRON_HOME'] = volttron_home;
                var options = {
                    mode: 'json',
                    pythonPath: python_path,
                    scriptPath: __dirname,
                    args: [msg.payload.topic, msg.payload.data]
                };
                var path = require('path');
                var scriptName = 'node_red_publisher.py';
                var scriptPath = path.resolve(__dirname, scriptName);
                PythonShell.run(scriptName, options, function(err, result) {
                    if (err) node.error(err);
                    if (result) node.warn(result);
                });
            });

        });
    }
    RED.nodes.registerType("volttron-output",VolttronOutputNode);

}

