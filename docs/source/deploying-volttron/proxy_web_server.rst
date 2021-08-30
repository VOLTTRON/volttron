.. _Apache-Reverse-Proxy-Setup:

*****************
Apache Web Server
*****************

The purpose of this section is to review the necessary dependencies and configurations for setting up a
simple reverse proxy for VOLTTRON using apache2.

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
for the apache2 web server. The default location is at /etc/apache2/apache2.conf.

An example apache2.conf config file can be found at volttron/scripts/admin/apache-proxy/apache2.conf.
Within the file, you will need to set the User and Group options, with ServerAdmin being optional.

.. code-block:: console

    ServerRoot "/etc/apache2"

    # Set User, Group, and ServerAdmin based on your system and organization

    # User will be a unix user
    User volttron

    # Group will be a unix group
    Group volttron

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

The 000-default.conf contains the site specific configuration to serve the VOLTTRON web server from and enforce https.
By default, the file can be found at /etc/apache2/sites-enabled/000-default.conf.

An example to use as a starting point for the volttron reverse proxy can be found at
volttron/scripts/admin/apache-proxy/000-default.conf. Within this file, DocumentRoot and Directory will need to be set.
Both DocumentRoot and Directory should be set to <path to volttron directory>/volttron/volttron/platform/web/static.


.. code-block:: console

    <VirtualHost *:80>
        # Set DocumentRoot file path to
        # <path to volttron>/volttron/volttron/platform/web/static
        # DO NOT include a '/' at the end of the file path!
        DocumentRoot "<VOLTTRON_ROOT>/volttron/volttron/platform/web/static"

        # Set Directory file path to match DocumentRoot
        <Directory "<VOLTTRON_ROOT>/volttron/volttron/platform/web/static">
            Options Indexes FollowSymLinks
            AllowOverride None
            Require all granted
        </Directory>

        # Force redirect of http to https
        RewriteEngine On
        RewriteCond %{HTTPS} off
        RewriteRule ^/+(.*) https://%{HTTP_HOST}%{REQUEST_URI} [R=permanent,L]
    </VirtualHost>


ssl.conf File
-------------

The ssl.conf contains the proxy, cert, and https configuration details. By default, the file can be found
at /etc/apache2/mods-enabled/ssl.conf.

An example ssl.conf file is provided with volttron and can be found at volttron/scripts/admin/apache-proxy/ssl.conf.
The file will need to be modified. The SSLCertificateFile, and SSLCertificateKeyFile paths need to be set to appropriate
cert and key file path.

Generating self-signed Certs
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The following instructions are based on directions for generating a self-signed certificate
provided by Ubuntu: `https://ubuntu.com/server/docs/security-certificates <https://ubuntu.com/server/docs/security-certificates>`_.


.. warning::

    While we generate a self-signed certificate for the demo, it is not recommended to use a self-signed certificate
    in a production environment, as this is not a secure practice. Instead use your institution's CA and certificates or a
    trusted 3rd party, e.g. `Let's Encrypt <https://letsencrypt.org/>`_. This is provided for education and demonstrative
    purposes only.

First, generate a server key:

.. code-block::

    openssl genrsa -des3 -out server.key 2048

This key will require a pass-phrase on startup of the proxy service which can become inconvenient.
It is possible to create a version of the key that does not require a pass-phrase, though this is less secure.
This will be done for this demo, but is not recommended (see warning and link above)

.. code-block::
    openssl rsa -in server.key -out server.key.insecure
    mv server.key server.key.secure
    mv server.key.insecure server.key

Generate a CSR.

.. code-block::
    openssl req -new -key server.key -out server.csr

Create the certificate file using the CSR and key files:

.. code-block::

    openssl x509 -req -days 365 -in server.csr -signkey server.key -out server.crt

server.key can now be used for the SSLCertificateKeyFile entry,
and server.crt can now be used for the SSLCertificateFile entry.


 Once that is complete, verify that ProxyPass and ProxyPassReverse options,
as well as the /vc path found under the RewriteRule option are all appropriate for your use case. This simple use-case
routes all web traffic through the proxy to your VOLTTRON instance running on your localhost.


.. code-block:: console

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
            SSLCertificateFile <path to cert file provided by CA>
            SSLCertificateKeyFile <path to key file>
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
            RewriteRule /vc/index.html#/dashboard(.*) ws://localhost:8080/vc/index.html#/dashboard$1 [P]

            #Add HSTS header:
            Header always set Strict-Transport-Security "max-age=31536000"

        </VirtualHost>
    </IfModule>

Setting Up Apache2
^^^^^^^^^^^^^^^^^^

Once all the config files have been properly configured, use them to overwrite the default config files
within the apache2 service directory. Sudo permissions are needed for this operation. After these files
have been overwritten, restart the apache service, and the proxy will be in place. You may want to make
a backup copy of the default config files found in the apache2 service directory for future reference.

Navigate to volttron/scripts/admin/apache-proxy/

.. code-block:: console

    cd volttron/scripts/admin/apache-proxy/

Copy configuration files to their appropriate locations

.. code-block:: console

    sudo cp apache2.conf /etc/apache2/apache2.conf
    sudo cp 000-default.conf /etc/apache2/sites-enabled/000-default.conf
    sudo cp ssl.conf /etc/apache2/mods-enabled/ssl.conf
    sudo service apache2 restart


Troubleshooting
^^^^^^^^^^^^^^^

Any errors encountered while starting/restarting the service can be examined by checking the status

.. code-block:: console

    service apache2 status

If the service has started correctly, but unexpected behaviour is still occurring, check the logs.
The four relevant log files can be found in /etc/apache2/logs: access_log, error_log, ssl_access_log, and ssl_error_log.
Error_log and ssl_error_log are particularly helpful.




