#!/usr/bin/env python

"""
This application presents a 'console' prompt to the user asking for read commands
to read the BDT and FDT from a BBMD.
"""

from bacpypes.debugging import bacpypes_debugging, ModuleLogger
from bacpypes.consolecmd import ConsoleCmd
from bacpypes.consolelogging import ArgumentParser

from bacpypes.comm import bind, Client
from bacpypes.core import run, enable_sleeping

from bacpypes.pdu import Address
from bacpypes.bvll import (
    ReadBroadcastDistributionTable,
    ReadBroadcastDistributionTableAck,
    ReadForeignDeviceTable,
    ReadForeignDeviceTableAck,
    WriteBroadcastDistributionTable,
    Result,
)
from bacpypes.bvllservice import AnnexJCodec, UDPMultiplexer

# some debugging
_debug = 0
_log = ModuleLogger(globals())

# globals
this_application = None


@bacpypes_debugging
class ReadWriteBBMDConsoleClient(ConsoleCmd, Client):
    def do_readbdt(self, args):
        """readbdt <addr>"""
        args = args.split()
        if _debug:
            ReadWriteBBMDConsoleClient._debug("do_readbdt %r", args)

        # build a request and send it downstream
        read_bdt = ReadBroadcastDistributionTable(destination=Address(args[0]))
        if _debug:
            ReadWriteBBMDConsoleClient._debug("    - read_bdt: %r", read_bdt)

        self.request(read_bdt)

    def do_readfdt(self, args):
        """readfdt <addr>"""
        args = args.split()
        if _debug:
            ReadWriteBBMDConsoleClient._debug("do_readfdt %r", args)

        # build a request and send it downstream
        read_fdt = ReadForeignDeviceTable(destination=Address(args[0]))
        if _debug:
            ReadWriteBBMDConsoleClient._debug("    - read_fdt: %r", read_fdt)

        self.request(read_fdt)

    def do_writebdt(self, args):
        """writebdt <addr> <entry> ..."""
        args = args.split()
        if _debug:
            ReadWriteBBMDConsoleClient._debug("do_writebdt %r", args)

        # build a list of broadcast distribution table entries which just so
        # happen to be BACpypes IPv4 addresses
        bdt = []
        for addr in args[1:]:
            bdte = Address(addr)
            bdt.append(bdte)

        # build a request and send it downstream
        write_bdt = WriteBroadcastDistributionTable(
            destination=Address(args[0]), bdt=bdt
        )
        if _debug:
            ReadWriteBBMDConsoleClient._debug("    - write_bdt: %r", write_bdt)

        self.request(write_bdt)

    def confirmation(self, pdu):
        """Filter for the acks and errors."""
        if _debug:
            ReadWriteBBMDConsoleClient._debug("confirmation %r", pdu)

        if isinstance(
            pdu, (ReadBroadcastDistributionTableAck, ReadForeignDeviceTableAck, Result)
        ):
            pdu.debug_contents()


def main():
    global this_application

    # parse the command line arguments
    parser = ArgumentParser(description=__doc__)
    parser.add_argument(
        "local_address",
        help="IPv4 address",
    )
    args = parser.parse_args()

    if _debug:
        _log.debug("initialization")
        _log.debug("    - args: %r", args)

    local_address = Address(args.local_address)
    if _debug:
        _log.debug("    - local_address: %r", local_address)

    # make a console
    this_console = ReadWriteBBMDConsoleClient()
    if _debug:
        _log.debug("    - this_console: %r", this_console)

    # create an Annex J codec, bound to the Annex J server
    # of the UDP multiplexer
    annexj = AnnexJCodec()
    mux = UDPMultiplexer(local_address)

    # bind the layers
    bind(this_console, annexj, mux.annexJ)

    # enable sleeping will help with threads
    enable_sleeping()

    _log.debug("running")

    run()

    _log.debug("fini")


if __name__ == "__main__":
    main()
