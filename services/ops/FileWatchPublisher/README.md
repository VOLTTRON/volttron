## File Watch Publisher Agent

The File Watch Publisher agent watches files listed in its configuration for changes.  The agent will detect changes to
those files and publish those changes line-by-line on the topic the user has associated with the file in the 
configuration.

The user should be careful about what files are being watched, and which historians are being used with the
File Watch Publisher.  Very long lines being output in individual messages on the message bus can result in some 
performance degradation.  Some configurations of the File Watch Publisher can affect the system (such as using I/O 
resources when a fast-moving log is being captured in a SQLite Historian), so the user should be intentional about which
files the agent is configured to watch and the topics used for publishes.


### Example Usage

The user wants to record logging information from the "myservice" service into a historian agent.

The user can configure the File Watch Publisher to point at the "myservice.log" file with a corresponding "record" 
topic -  for example "record/myservice/logs".  As "myservice" adds logging entries to its log file, the File Watch 
Publisher will capture each new log message and publish it to the "record/myservice/logs" topics on the message bus. 

Below is a File Watch Publisher example configuration to match the above scenario. 


#### Configuration

```json
{
    "files": [
        {
            "file": "/opt/myservice/logs/myservice.log",
            "topic": "record/myservice/logs"
        }
    ]
}
```


### Example Publish

The following is an example publish by the File Watch Publisher tracking changes for a file called test.txt and being
published to the topic "record/filewatcher/test".

    2021-01-25 14:54:43,483 (listeneragent-3.3 4150) __main__ INFO: Peer: pubsub, Sender: platform.filewatchpublisher1
    :, Bus: , Topic: record/filewatcher/test, Headers: {'min_compatible_version': '3.0', 'max_compatible_version': ''}, 
    Message: {'line': 'test text', 'timestamp': '2021-01-25T22:54:43.474352Z'}

