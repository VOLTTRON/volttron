Improvements Based on Results
=============================


Here is the list of scalability improvements so far:

Reduced the overhead of the base historian by removing unneeded writes
to the backup db. Significantly improved performance on low end devices.

Added options to reduce the number of publishes per device per scrape.
Common cases where per point publishes and breadth first topics are not
needed the driver can be configured only publish the depth first “all”
or any combination per device the operator needs. This dramatically
decreases the platform hardware requirements while increasing the number
of devices that can be scraped.

Added support for staggering device scrapes to reduce CPU load during a
scrape.

Further ideas:

| Determine if how we use ZMQ is reducing its efficiency.
| Remove an unneeded index in historian backup db.
| Increase backup db page count.
