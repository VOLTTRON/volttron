'''
Created on Jun 26, 2014

@author: craig
'''

from volttron.platform.packaging import (create_package,
                                         repackage)

def sign_agent_package(agent_package):
    pass
    

def create_agent_package(agent_descriptor, do_create):
    '''
    '''
    if do_create:
        create_package(agent_descriptor)
    else:
        repackage(agent_descriptor)
        


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(title = 'subcommands',
                                       description = 'valid subcommands',
                                       help = 'additional help', 
                                       dest='subparser_name')
    package_parser = subparsers.add_parser('package',
                                           help="Create agent package (whl) from a directory or installed agent name.")
    
    package_parser.add_argument('agent_directory', 
                                help='Directory for packaging an agent for the first time (requires setup.py file).')
    
    repackage_parser = subparsers.add_parser('repackage',
                                           help="Creates agent package from a currently installed agent.")

    repackage_parser.add_argument('agent_name', 
                                help='The name of a currently installed agent.')
    
    try:
        import volttron.restricted.auth
        sign_parser = subparsers.add_parser('sign')
        sign_parser.add_argument('package',
                                 help='The agent package to sign (whl).')
        
        verify_parser = subparsers.add_parser('verify',
                                              help='The agent package to verify (whl).')
        verify_parser.add_argument('package')
        # TODO add arguments for signing the wheel package here.
    except:
        pass
    
    args = parser.parse_args(['package', '/tmp/wheel'])
    print(args)
    print('subparser_name')
    
    # whl_path will be specified if there is a package or repackage command
    # is specified and it was successful.
    whl_path = None
    
    if args.subparser_name == 'package':
        whl_path = create_agent_package(args.agent_directory, True)
    elif args.subparser_name == 'repackage':
        whl_path = create_agent_package(args.agent_name, False)
    elif args.subparser_name == 'sign':
        result = sign_agent_package(args.package)
            
    if whl_path:
        print("Package created at: {}".format(whl_path))
    