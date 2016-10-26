Archiver Agent
--------------

The **ArchiverAgent** is a platform services agent that uses the smap
web services api for retrieving data. The agent listens for a request on
the message bus that includes the smap path and a time range, and
returns the data retrieved from smap to the requesting agent via the
message bus.

Configuration
~~~~~~~~~~~~~

The configuration is done in the launch config file for the agent. The
required elements are the archiver\_url, and the source\_name. The
archiver\_url is the url for the server, and includes the path to the
web services api (typically /backend/api/query). The source\_name
corresponds to the Metadata/SourceName in smap and is used as a default
in case the requester did not include the source name in the headers for
the request.

This is a sample launch configuration:

::

    {
        "agent": {
            "exec": "archiveragent-0.1-py2.7.egg --config \"%c\" --sub \"%s\" --pub \"%p\""
        },
        "archiver_url": "http://<your smap url here>/backend/api/query",
        "agentid": "Archiver1",
        "source_name": "<Your Source Here>"
    }

Usage
~~~~~

::

    publish('archiver/request/campus1/building1/realcatalyst1/CoolCall1',{},'(now -1h, now)')

    publish('archiver/request/campus1/building1/realcatalyst1/CoolCall1',{},'(1374192541000.0, 1374193541000.0)')

The agent listens for messages on archiver/request. The path that
follows this prefix is extracted and used in the Archiver query and
represents the path to the value desired. There is also a source name
that needs to be specified in one form or another. A default source name
can be specified as part of the launch config. Alternatively, the
requester may specify the source name as a property in the header of the
message. The Agent looks for a **SourceName** property and will use that
if it is given. The message portion of the request is a time range in
the form of (start time, end time), and is passed as a simple string.
The times may be specified in any way that smap recognizes time. The
smap archiver page indicates that you can use a variety of ways to
specify the time:

    You can select the time region queried using a range query, or a
    query relative to a reference time stamp. In all these cases, the
    reference times must either be a timestamp in units of UNIX
    milliseconds, the string literal now, or a quoted time string. Valid
    time strings match a time format of either%m/%d/%Y, %m/%d/%Y %M:%H,
    or %Y-%m-%dT%H:%M:%S. For instance “10/16/1985” and “2/29/2012
    20:00” are valid. These strings are interpreted relative to the
    timezone of the server.

    The reference may be modified by appending a relative time string,
    using unix “at”-style specifications. You can for instance say now +
    1hour or now -1h -5m for the last 1:05. Available relative time
    quantities are days, hours, minutes, and seconds.

The data is returned as a list of lists where the first element in the
interior list is the timestamp in unix form, and the second element is
the data as it is returned from smap:

::

    [[1371851254000.0,1.0],[1371851314000.0,1.0],[1371851374000.0,1.0],[1371851434000.0,1.0],
     [1371851494000.0,1.0],[1371851554000.0,1.0],[1371851614000.0,1.0],[1371851674000.0,1.0],
     [1371851734000.0,1.0],[1371851794000.0,1.0],[1371851854000.0,1.0],[1371851914000.0,1.0],
     [1371851974000.0,1.0],[1371852034000.0,1.0],[1371852094000.0,1.0],[1371852154000.0,1.0],
     [1371852214000.0,1.0],[1371852274000.0,1.0],[1371852334000.0,1.0],[1371852394000.0,1.0],
     [1371852454000.0,1.0],[1371852514000.0,1.0],[1371852574000.0,1.0],[1371852634000.0,1.0],
     [1371852694000.0,1.0],[1371852754000.0,1.0],[1371852814000.0,1.0],[1371852874000.0,1.0],
     [1371852934000.0,1.0],[1371852994000.0,1.0],[1371853054000.0,1.0],[1371853114000.0,1.0],
     [1371853174000.0,1.0],[1371853234000.0,1.0],[1371853294000.0,1.0],[1371853354000.0,1.0],
     [1371853414000.0,1.0],[1371853474000.0,1.0],[1371853534000.0,1.0],[1371853594000.0,1.0],
     [1371853654000.0,1.0],[1371853714000.0,1.0],[1371853774000.0,1.0],[1371853834000.0,1.0],
     [1371853894000.0,1.0],[1371853954000.0,1.0],[1371854005000.0,1.0]]

There is a known issue where smap returns only up to 10000 data points
using the web service, and does so silently. For this reason, requests
should avoid broad time ranges to avoid having data request truncated.
If necessary, split your desired time range into smaller pieces and join
the data together after each request.
