Ensure you have installed the `required
packages <DevelopmentPrerequisites>`__ before proceeding. Especially if
you intend to develop in Eclipse, we recommend creating a directory:
~/workspace In this directory:

-  hg clone /volttron/lite volttron-lite
-  cd volttron-lite
-  ./bootstrap

   -  If bootstrap fails before finishing, run: bin/buildout -N

Note: If bootstrap or buildout fails, try "bin/buildout -N" again. Also,
some packages (especially numpy) can be very verbose when they install.
Please wait for the text to finish.

To test that installation worked, star up the platform:

-  bin/volttron-lite -c dev-config.ini

