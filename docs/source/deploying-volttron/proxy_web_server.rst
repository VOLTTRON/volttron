.. _Apache-Reverse-Proxy-Setup:

*********************************************
Reverse Proxy Example for VOLTTRON Deployment
*********************************************

The purpose of this section is to review the necessary dependencies and configurations for setting up and deploying
a reverse proxy for VOLTTRON using apache2 as the proxy on Ubuntu.

Configuring VOLTTRON
====================

For this setup, VOLTTRON should be web enabled, using the http protocol and default web port of 8080. The
bind-web-address and volttron-central-address should be set to localhost (http://localhost:8080).
The proxy will handle requiring https. Refer to :ref:`this section <VOLTTRON-Central-Deployment>` for guidance
on setting up an instance of VOLTTRON Central.

Install Dependencies
====================

To set up a reverse proxy using apache for VOLTTRON, install apache2
and enable the ssl, rewrite, headers, proxy, and proxy_http modules.
This will require sudo access and a restart of the apache2 service.

.. code-block::

    sudo apt-get install apache2
    sudo a2enmod ssl
    sudo a2enmod rewrite
    sudo a2enmod headers
    sudo a2enmod proxy
    sudo a2enmod proxy_http
    sudo service apache2 restart


Configuring Apache2
===================

In ubuntu, the apache configuation is divided into a series of directories. For setting up a basic reverse proxy
for VOLTTRON, there are three that we need to modify, apache2.conf, ssl.conf, and 000-default.conf.


apache2.conf File
-----------------

The apache2.conf sits in the root apache2 directory and serves as a top level configuration file
for the apache2 web server. This is the main Apache server configuration file. It contains the configuration directives
that give the server its instructions. Debian's apache2 configuration is split into several files forming a
configuration hierarchy. The apache2.conf file puts the pieces together by including all
remaining configuration files when starting up the web server. The default location for this file is at
/etc/apache2/apache2.conf.

An example apache2.conf config file can be found within the volttron repository at
volttron/scripts/admin/apache-proxy/apache2.conf. Within the file, you will need to set the
User and Group options, with ServerAdmin being optional.

.. code-block:: console

    # apache2.conf

    ServerRoot "/etc/apache2"

    # Set User, Group, and ServerAdmin based on your system and organization

    # User will be a non-root unix user that the server will use to respond to requests.
    # It is recommended to create a new user group specifically for the apache server.
    # The user and group should not have the ability to access any files that are not
    # intended to be available through the VOLTTRON web service, or have the ability to
    # execute code beyond the anticipated scope. This user does not need permissions for
    # all of VOLTTRON, only the web hosted materials.
    User <user name>
    Group <group name>


    # ServerAdmin will be an email address.
    ServerAdmin admin@volttron

    <Directory />
        AllowOverride none
        Require all denied
    </Directory>

    <IfModule dir_module>
        DirectoryIndex index.html
    </IfModule>

    <Files ".ht*">
        Require all denied
    </Files>

    ErrorLog "logs/error_log"
    LogLevel warn

    <IfModule log_config_module>
        LogFormat "%h %l %u %t \"%r\" %>s %b \"%{Referer}i\" \"%{User-Agent}i\"" combined
        LogFormat "%h %l %u %t \"%r\" %>s %b" common
        <IfModule logio_module>
          LogFormat "%h %l %u %t \"%r\" %>s %b \"%{Referer}i\" \"%{User-Agent}i\" %I %O" combinedio
        </IfModule>
        CustomLog "logs/access_log" combined
    </IfModule>

    <IfModule mime_module>
        TypesConfig /etc/mime.types
        AddType application/x-compress .Z
        AddType application/x-gzip .gz .tgz
        AddType text/html .shtml
        AddOutputFilter INCLUDES .shtml
    </IfModule>

    AddDefaultCharset UTF-8

    <IfModule mime_magic_module>
        MIMEMagicFile conf/magic
    </IfModule>

    EnableSendfile on

    # Set Security headers
    ServerTokens Prod
    TraceEnable Off
    Header always set X-Frame-Options "SAMEORIGIN"
    Header always set X-Xss-Protection "1; mode=block"
    Header always set X-Content-Type-Options "nosniff"
    Header always set X-Permitted-Cross-Domain-Policies "none"
    Header unset ETag
    FileETag None
    Header Unset X-Powered-By

    # Force redirect of http to https
    RewriteEngine On
    RewriteCond %{HTTPS} off
    RewriteRule ^/+(.*) https://%{HTTP_HOST}%{REQUEST_URI} [R=permanent,L]

    # Include module configuration:
    IncludeOptional mods-enabled/*.load
    IncludeOptional mods-enabled/*.conf

    # Include list of ports to listen on
    Include ports.conf

    # Include generic snippets of statements
    IncludeOptional conf-enabled/*.conf

    # Include the virtual host configurations:
    IncludeOptional sites-enabled/*.conf



000-default.conf File
---------------------

The 000-default.conf contains the site specific configuration to serve the proxy server for the VOLTTRON web server
and to enforce https. 000-default.conf is the default file name used by apache2 to sort the default site on a multi-site
system. On installation, the default file can be found at /etc/apache2/sites-available/000-default.conf.

An example to use as a starting point for the volttron reverse proxy can be found within the volttron repository at
volttron/scripts/admin/apache-proxy/000-default.conf.


.. code-block:: console

    # 000-default.conf

    <VirtualHost *:80>
        # Force redirect of http to https
        RewriteEngine On
        RewriteCond %{HTTPS} off
        RewriteRule ^/+(.*) https://%{HTTP_HOST}%{REQUEST_URI} [R=permanent,L]
    </VirtualHost>


ssl.conf File
-------------

The ssl.conf contains the proxy, cert, and https configuration details. By default, the file can be found
at /etc/apache2/mods-available/ssl.conf.

An example ssl.conf file is provided with volttron and can be found within the volttron repository at
volttron/scripts/admin/apache-proxy/ssl.conf. The SSLCertificateFile, and SSLCertificateKeyFile paths need
to be set to appropriate cert and key file path. The default values are set to use the built-in
(for Debian-based systems) `snakeoil <http://manpages.ubuntu.com/manpages/bionic/man8/make-ssl-cert.8.html>`_
cert and key. These will work for testing, but are not the preferred values for a production environment.

.. warning::

    While we use a self-signed certificate for the demo, it is not recommended to use a self-signed certificate
    in a production environment. Instead use certificates signed by your institution's CA or a trusted 3rd party,
    e.g. `Let's Encrypt <https://letsencrypt.org/>`_. This is provided for education and demonstrative purposes only.

 Once you have set these values, decided to use the self-signed cert, verify that the ProxyPass and ProxyPassReverse
 options, as well as the /vc path found under the RewriteRule option are all appropriate for your use case.
 This simple use-case routes all web traffic through the proxy to your VOLTTRON instance running on your localhost.


.. code-block:: console

    # ssl.conf

    <IfModule mod_ssl.c>
        SSLPassPhraseDialog  exec:/usr/share/apache2/ask-for-passphrase
        SSLSessionCache		shmcb:${APACHE_RUN_DIR}/ssl_scache(512000)
        SSLSessionCacheTimeout  300
        SSLRandomSeed startup file:/dev/urandom  256
        SSLRandomSeed connect builtin
        SSLCryptoDevice builtin

        <VirtualHost _default_:443>
            ErrorLog logs/ssl_error_log
            TransferLog logs/ssl_access_log
            LogLevel warn
            SSLEngine on
            # Require TLS 1.2 only
            SSLProtocol -all +TLSv1.2
            # Require Strong Ciphers
            SSLCipherSuite "EECDH:!RC4:!3des:!SHA"
            # Require Cipher Order
            SSLHonorCipherOrder on

            # Using the included (Debian based systems) self-signed snakeoil certificate and key.
            # These should be replaced with a key cert pair signed by your
            # institution's CA or a trusted 3rd party.

            #CHANGE PATH TO CERT ISSUED BY APPROVED CA
            SSLCertificateFile      /etc/ssl/certs/ssl-cert-snakeoil.pem

            #CHANGE PATH TO APPROVED KEY
            SSLCertificateKeyFile /etc/ssl/private/ssl-cert-snakeoil.key

            <Files ~ "\.(cgi|shtml|phtml|php3?)$">
                SSLOptions +StdEnvVars
            </Files>
            BrowserMatch "MSIE [2-5]" \
                     nokeepalive ssl-unclean-shutdown \
                     downgrade-1.0 force-response-1.0
            CustomLog logs/ssl_request_log \
                      "%t %h %{SSL_PROTOCOL}x %{SSL_CIPHER}x \"%r\" %b"

            #Setup proxy for volttron
            ProxyRequests Off
            ProxyPreserveHost Off
            ProxyVia Off
            # Set proxy path as appropriate.
            ProxyPass          /     http://localhost:8080/ timeout=60
            ProxyPassReverse   /     http://localhost:8080/ timeout=60

            #Setup websockets to proxy for volttron central
            RewriteEngine On
            RewriteCond %{HTTP:UPGRADE} ^WebSocket$ [NC]
            RewriteCond %{HTTP:CONNECTION} Upgrade$ [NC]
            # Set proxy path as appropriate
            # This is only needed if VC is installed.
            RewriteRule /vc/index.html#/dashboard(.*) ws://localhost:8080/vc/index.html#/dashboard$1 [P]

            #Add HSTS header:
            Header always set Strict-Transport-Security "max-age=31536000"

        </VirtualHost>
    </IfModule>


Setting Up Apache2
^^^^^^^^^^^^^^^^^^

.. note::

    We will be overwriting some of the default config files in the apache2 service directory as part
    of this setup. You may want to create backup copies of these files for future reference.

Once all the config files have been properly configured, use them to overwrite the default config files
within the apache2 service directory. Sudo permissions are needed for this operation. After these files
have been overwritten, restart the apache service, and the proxy will be in place.

Change directory to volttron/scripts/admin/apache-proxy/

.. code-block:: console

    cd volttron/scripts/admin/apache-proxy/

Copy configuration files to their appropriate locations

.. code-block:: console

    sudo cp apache2.conf /etc/apache2/apache2.conf
    sudo cp 000-default.conf /etc/apache2/sites-available/000-default.conf
    sudo cp ssl.conf /etc/apache2/mods-available/ssl.conf
    sudo service apache2 restart


Troubleshooting
^^^^^^^^^^^^^^^

Any errors encountered while starting/restarting the service can be examined by checking the status

.. code-block:: console

    service apache2 status

If the service has started correctly, but unexpected behaviour is still occurring, check the logs.
The four relevant log files can be found in /etc/apache2/logs: access_log, error_log, ssl_access_log, and ssl_error_log.
Error_log and ssl_error_log are particularly helpful.




