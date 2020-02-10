.. _Repository-Structure:

Repository Structure
====================

There are several options for using the VOLTTRON code depending on
whether you require the most stable version of the code or want the
latest updates as they happen. In order of decreasing stability and
increasing currency:

For most stable, download the source code for the latest release at:
https://github.com/VOLTTRON/volttron/releases These are purely source
code and are not tied to the git repository. To update them will require
downloading the newest source code and re-installing.

The master branch is now the default branch for VOLTTRON (meaning this
is what you clone if you do not use the “-b” option). This branch will
get the latest stable features as they are pushed. The current major
version is 7.x.

The “develop” branch contains the latest features as they are developed.
Once a feature is considered “finished” it is merged back into develop.
Develop will be merged into master once it is considered stable and
ready for release. This branch can be cloned by those wanting to work
from the latest version of the platform but should not be used in
deployments.

Features are developed on “feature” branches or developers' forks of
the main repository. It is not
recommended to clone these branches except for exploring a new
feature.
