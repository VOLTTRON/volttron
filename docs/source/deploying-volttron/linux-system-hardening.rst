.. _Linux-System-Hardening:

======================
Linux System Hardening
======================


Introduction
============

VOLTTRON is built with modern security principles in mind [security-wp] and implements many security features for hosted
agents.  However, VOLTTRON is built on top of Linux and the underlying Linux platform also needs to be secured in order
to declare the resulting control system as "secure."

Any system is only as secure as its weakest link. This document is dedicated to making recommendations for hardening of
the underlying Linux platform that VOLTTRON is deployed to.

.. Warning::

   No system can be 100% secure and the cyber security strategy that is recommended in this document is based on risk
   management.  For the following guidance, it is intended that the user consider the risk, impact of risks, and perform
   the appropriate corresponding mitigation techniques.


Recommendations
===============

Here are the non-exhaustive recommendations for Linux hardening from the VOLTTRON team:

-  Physical Security: Keep the system in locked cabinets or a locked room.  Limit physical access to systems and to the
   networks to which they are attached.  The goal should be to avoid physical access by untrusted personnel.  This could
   be extended to blocking or locking USB ports, removable media drives, etc.

   Drive encryption could be used to avoid access via alternate-media booting (off USB stick or DVD) if physical access
   can't be guaranteed.  The downside of drive encryption would be needing to enter a passphrase to start system.
   Alternately, the `Trusted Platform Module` (TPM) may be used, but the drive might still be accessible to those with
   physical access.  Enable chassis intrusion detection and reporting if supported.  If available, use a physical tamper
   seal along with or in place of an interior switch.

-  Low level device Security:  Keep firmware of all devices (including BIOS) up-to-date.  Password-protect the BIOS.
   Disable unneeded/unnecessary devices:

       - serial
       - parallel
       - USB (Leaving a USB port enabled may be helpful if a breach occurs to allow saving forensic data to an external
         drive.)
       - Firewire, etc.
       - ports
       - optical drives
       - wireless devices, such as Wi-Fi and Bluetooth

-  Boot security:

   - Disable auto-mounting of external devices
   - Restrict the boot device:

      - Disable PXE and other network boot options (unless that is the primary boot method)
      - Disable booting from USB and other removable drives

   - Secure the boot loader:

      - Require an administrator password to do anything but start the default kernel
      - Do not allow editing of kernel parameters
      - Disable, remove, or password-protect emergency/recovery boot entries

-  Security Updates: First and foremost, configure the system to automatically download security updates.  Most security
   updates can be installed without rebooting the system, but some updated (e.g. shared libraries, kernel, etc) require
   the system to be rebooted.  If possible, configure the system to install the security updates automatically and
   reboot at a particular time.  We also recommend reserving the reboot time (e.g. 1:30AM on a Saturday morning) using
   the Actuator Agent so that no control actions can happen during that time.

-  System Access only via Secured Protocols:

      - Disallow all clear text access to VOLTTRON systems
      - No telnet, no rsh, no ftp and no exceptions!
      - Use ssh to gain console access, and scp/sftp to get files in and out of the system
      - Disconnect excessively idle SSH Sessions

-  Disable remote login for "root" users.  Do not allow a user to directly access the system as the "root" user from a
   remote network location.  Root access to privileged operations can be accomplished using ``sudo``.  This adds an
   extra level of security by restricting access to privileged operations and tracking those operations through the
   system log.

-  Manage users and usernames, limit the number of user accounts, use complex usernames rather than first names.

-  Authentication:  If possible, use two factor authentication to allow access to the system.  Informally, two factor
   authentication uses a combination of "something you know" and "something you have" to allow access to the system.
   RSA `SecurID` tokens are commonly used for two factor authentication but other tools are available.  When not using
   two-factor authentication, use strong passwords and do not share accounts.

-  Scan for weak passwords.  Use password cracking tools such as `John the Ripper <http://www.openwall.com/john/>`_ or
   `Nmap <http://nmap.org>`_ with password cracking modules to look for weak passwords.

-  Utilize `Pluggable Authentication Modules` (PAM) to strengthen passwords and the login process.  We recommend:

   -  *pam_abl*: Automated blacklisting on repeated failed authentication attempts
   -  *pam_captcha*: A visual text-based CAPTCHA challenge module for PAM
   -  *pam_passwdqc*: A password strength checking module for PAM-aware password changing programs
   -  *pam_cracklib*: PAM module to check the password against dictionary words
   -  *pam_pwhistory*: PAM module to remember last passwords

-  Disable unwanted services.  Most desktop and server Linux distributions come with many unnecessary services enabled.
   Disable all unnecessary services.  Refer to your distribution's documentation to discover how to check and disable
   these services.

-  Just as scanning for weak passwords is a step to more secure systems; regular network scans using
   `Nmap <http://nmap.org>`_ to find what network services are being offered is another step towards a more secure
   system.

   .. warning::

      use `Nmap` or similar tools very carefully on BACnet and modbus environments.  These scanning tools are known to
      crash/reset BACnet and modbus devices.

-  Control incoming and outgoing network traffic.  Use the built-in host-based firewall to control who/what can connect
   to this system.  Many `iptables` frontends offer a set of predefined rules that provide a default deny policy for
   incoming connections and provide rules to prevent or limit other well known attacks (i.e. rules that limit certain
   responses that might amplify a DDoS attack). `ufw` (uncomplicated firewall) is a good example.

   Examples:

   - If the system administrators for the VOLTTRON device are all located in ``10.10.10.0/24`` subnetwork, then allow
     SSH and SCP logins from only that IP address range.
   - If the VOLTTRON system exports data to a historian at ``10.20.20.1`` using TCP over port 443, allow outgoing
     traffic to that port on that server.

   The idea here is to limit the attack surface of the system.  The smaller the surface, the better we can analyze the
   communication patterns of the system and detect anomalies.

   .. note::

      While some system administrators disable network-based diagnostic tools such as ICMP ECHO responses, the VOLTTRON
      team believes that this hampers usability.  As an example, monitoring which incoming and outgoing firewall rules
      are triggering can be accomplished with this command:

      .. code-block:: bash

         watch --interval=5 'iptables -nvL | grep -v "0     0"'

-  Rate limit incoming connections to discourage brute force hacking attempts.  Use a tool such as
   `fail2ban <http://www.fail2ban.org/wiki/index.php/Main_Page>`_ to dynamically manage firewall rules to rate limit
   incoming connections and discourage brute force hacking attempts.  `sshguard <http://www.sshguard.net/>`_ is similar
   to `fail2ban` but only used for ssh connections.  Further rate limiting can be accomplished at the firewall level.
   As an example, you can restrict the number of connections used by a single IP address to your server using iptables.
   Only allow 4 ssh connections per client system:

   .. code-block:: bash

      iptables -A INPUT -p tcp --syn --dport 22 -m connlimit --connlimit-above 4 –j DROP

   You can limit the number of connections per minute.  The following example will drop incoming connections if an IP
   address makes more than 10 connection attempts to port 22 within 60 seconds:

   .. code-block:: bash

      iptables -A INPUT -p tcp –dport 22 -i eth0 -m state --state NEW -m recent --set
      iptables -A INPUT -p tcp –dport 22 -i eth0 -m state --state NEW -m recent --update –-seconds 60 -–hitcount 10 –j DROP

-  Use a file system integrity tool to monitor for unexpected file changes.  Tools such as `tripwire
   <http://sourceforge.net/projects/tripwire/>`_ monitor filesystems for changed files.  Another file integrity checking
   tool to consider is `AIDE (Advanced Intrusion Detect Environment) <http://aide.sourceforge.net/>`_.

-  Use filesystem scanning tools periodically to check for exploits.  Available tools such as `checkrootkit
   <http://www.chkrootkit.org>`_, `rkhunter <http://rkhunter.sourceforge.net>`_ and others should be used
   to check for known exploits on a periodic basis and report their results.

-  VOLTTRON does not use Apache or require it.  If Apache is being used, we recommend using the `mod_security` and
   `mod_evasive` modules.


Raspberry Pi
------------

System hardening recommendations for Raspberry Pi closely match those for other Linux operating systems such as Ubuntu.
VOLTTRON has only been officially tested with Raspbian, and there is one important consideration, which is noted in
the Raspbian documentation as well:

.. warning::

    The Raspbian operating system includes only the default `pi` user on install, which uses a well-known default
    password.  For any operational deployment, it is recommended to create a new user with a complex password (this user
    must have sudoers permissions.

    Summarizing the process of creating a new user `alice` from the Raspberry Pi documentation:

    .. code-block:: bash

        sudo adduser alice
        sudo usermod -a -G adm,dialout,cdrom,sudo,audio,video,plugdev,games,users,input,netdev,gpio,i2c,spi alice
        sudo su - alice
        sudo visudo /etc/sudoers.d/010_pi-nopasswd

    When the editor opens for the sudoer's file, add an entry for `alice`:

    .. code-block:: console

        alice ALL=(ALL) PASSWD: ALL

    Also, update the default `pi` user's default password:

    .. code-block:: console

        pi@raspberrypi:~/volttron$ passwd
        Changing password for pi.
        (current) UNIX password:
        Enter new UNIX password:
        Retype new UNIX password:
        passwd: password updated successfully

    .. note::

        The Raspberry Pi documentation states that ideally one would remove the `pi` user from the system, however this
        is not currently recommended as some aspects of the Raspberry Pi OS are tied to the `pi` user.  This will be
        changed in the future.

    For more information, please visit the
    `Raspberry Pi security site <https://www.raspberrypi.org/documentation/configuration/security.md>`_.


System Monitoring
-----------------

-  Monitor system state and resources. Use a monitoring tool such as `Xymon <http://xymon.sourceforge.net>`_ or
   `Big Brother <http://www.bb4.org/features.html>`_ to remotely monitor the system resources and state.  Set the
   monitoring tools to alert the system administrators if anomalous use of resources (e.g. connections, memory, etc) are
   detected.  An administrator can also use Unix commands such as `netstat` to look for open connections periodically.

-  Watch system logs and get logs off the system. Use a utility such as `logwatch
   <http://sourceforge.net/projects/logwatch/files/>`_ or `logcheck <http://logcheck.org>`_ to get a daily summary of
   system activity via email.  For Linux distributions that use `systemd` (such as Ubuntu), use `journalwatch
   <http://git.the-compiler.org/journalwatch/>`_ to accomplish the same task.

   Additionally, use a remote syslog server to collect logs from all VOLTTRON systems in the field at a centralized
   location for analysis.  A tool such as `Splunk` is ideal for this task and comes with many built-in analysis
   applications.  Another benefit of sending logs remotely off the platform is the ability to inspect the logs even when
   the platform may be compromised.

-  An active intrusion sensor such as `PSAD <http://cipherdyne.org/psad/>`_ can be used to look for intrusions as well.


Security Testing
----------------

Every security control discussed in the previous sections must be tested to determine correct operation and impact.
For example, if we inserted a firewall rule to ban connections from an IP address such as 10.10.10.2, then we need to
test that the connections actually fail.

In addition to functional correctness testing, common security testing tools such as `Nessus
<http://www.tenable.com/products/nessus>`_ and `Nmap <http://nmap.org>`_ should be used to perform cyber security
testing.


Conclusion
==========

No system is 100% secure unless it is disconnected from the network and is in a physically secure location.  The
VOLTTRON  team recommends a risk-based cyber security approach that considers each risk, and the impact of an exploit.
Mitigating technologies can then be used to mitigate the most impactful risks first.  VOLTTRON is built with security
in mind from the ground up, but it is only as secure as the operating system that it runs on top of.  This document is
intended to help VOLTTRON users to secure the underlying Linux operating system to further improve the robustness of the
VOLTTRON platform.  Any security questions should be directed to volttron@pnnl.gov.
