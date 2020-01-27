# This is here because ansbile in most imports does this and then
# it uses it throughout the codebase.  It seems that the CLIARGS
# does not effect the PlayBookExecutor that we are using so we
# implement the verbosity here instead of there, though it looks
# like we implment it in the deploy file, we note that it
# does not change
#
# https://stackoverflow.com/questions/34860131/running-an-ansible-playbook-using-python-api-2-0-0-1
# is a reference I used to figure out how to "hack" the verbosity for
# the deploy
# Handle the import of ansible correctly
try:
    from ansible.utils.display import Display

    display = Display(verbosity=1)
except ImportError:
    pass
