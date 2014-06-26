'''
Created on Jun 26, 2014

This module defines the entry point for the developer module. 

@author: craig
'''
import sys, argparse

# option decorator
def option(*args, **kwds):
    def _decorator(func):
        _option = (args, kwds)
        if hasattr(func, 'options'):
            func.options.append(_option)
        else:
            func.options = [_option]
        return func
    return _decorator

# arg decorator
arg = option

# combines option decorators
def option_group(*options):
    def _decorator(func):
        for option in options:
            func = option(func)
        return func
    return _decorator


class MetaCommander(type):
    def __new__(cls, classname, bases, classdict):
        subcmds = {}
        for name, func in classdict.items():
            if name.startswith('do_'):
                name = name[3:]
                subcmd = {
                    'name': name,
                    'func': func,
                    'options': []
                }
                if hasattr(func, 'options'):
                    subcmd['options'] = func.options
                subcmds[name] = subcmd
        classdict['_argparse_subcmds'] = subcmds
        return type.__new__(cls, classname, bases, classdict)



class Commander(object):
    __metaclass__ = MetaCommander
    name = 'app'
    description = 'a description'
    version = '0.0'
    epilog = ''
    default_args = []
    
    def cmdline(self):
        parser = argparse.ArgumentParser(
            # prog = self.name,
            formatter_class = argparse.RawDescriptionHelpFormatter,
            description=self.__doc__,
            epilog = self.epilog,
        )

        parser.add_argument('-v', '--version', action='version',
                            version = '%(prog)s '+ self.version)

        subparsers = parser.add_subparsers(
            title='subcommands',
            description='valid subcommands',
            help='additional help',
        )
        
        for name in sorted(self._argparse_subcmds.keys()):
            subcmd = self._argparse_subcmds[name]            
            subparser = subparsers.add_parser(subcmd['name'],
                                     help=subcmd['func'].__doc__)
            for args, kwds in subcmd['options']:
                subparser.add_argument(*args, **kwds)
            subparser.set_defaults(func=subcmd['func'])

        if len(sys.argv) <= 1:
            options = parser.parse_args(self.default_args)
        else:
            options = parser.parse_args()
        options.func(self, options)
    


def main():
    # only for options which are repeated across different funcs
    common_options = option_group(
        option('--log', '-l', action='store_true', help='log is on')
    )
    
    class Application(Commander):
        'Command line tool to package or sign (optional) the agent '
        name = 'volttron-dev'
        version = '0.1'
        default_args = ['--help']
        
        @option('--log', '-l', action='store_true', help='log is on')
        @arg('agent', help="agent directory or name of currently installed agent.")
        def do_package(self, options):
            "Packages agent and create a whl file"
            print options

        @option('-f', '--force', action='store_true',
                        help='force through installation')
        @common_options
        def do_sign(self, options):
            "Signs an agent's package (whl file)"
            print options
             
    app = Application()
    app.cmdline()

if __name__ == '__main__':
    main()

## This function takes the 'extra' attribute from global namespace and re-parses it to create separate namespaces for all other chained commands.
# def parse_extra (parser, namespace):
#   namespaces = []
#   extra = namespace.extra
#   while extra:
#     n = parser.parse_args(extra)
#     extra = n.extra
#     namespaces.append(n)
# 
#   return namespaces
# 
# 
# if __name__ == '__main__':
#     parser = argparse.ArgumentParser()
#     
#     parser.add_argument("command")
# 
#     parser.add_argument("--package_dir", nargs=1)
#     parser.add_argument("--sign", nargs=1)
#     
#     parser.print_help()
#     print(parser.parse_args('package --package_dir junk'.split()))
#     
#     
    #parser.add_argument('agent')
    
#     subparsers = parser.add_subparsers(help='command package', dest='package')
#     
#     parser_a = subparsers.add_parser('package', help="command_a help")
#     
#     # nargs="*" for 0 or more commands.
#     parser.add_argument('package', nargs="*", help = 'Other commands')
#     parser.add_argument('agent_name', nargs="*", help = 'Other commands')
#     
#     
#     namespace = parser.parse_args()
#     
#     extra_namespaces = parse_extra(parser.extra, namespace)