#!/usr/bin/env python
# -*- coding: UTF-8 -*-
# Copyright (C) 2005-2007 Juan David Ibáñez Palomar <jdavid@itaapy.com>
# Copyright (C) 2006 Hervé Cauwelier <herve@itaapy.com>
# Copyright (C) 2007 Sylvain Taverne <sylvain@itaapy.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

# Import from the Standard Library
from optparse import OptionParser
from sys import exit

# Import from itools
from itools import __version__, vfs
from itools.core import become_daemon, fork

# Import from ikaaro
from ikaaro.database import check_database
from ikaaro.update import is_instance_up_to_date
from ikaaro.server import Server, get_pid, get_fake_context


def start(options, target):
    # Check the server is not running
    pid = get_pid(target)
    if pid is not None:
        print '[%s] The Web Server is already running.' % target
        return 1

    # Check for database consistency
    if check_database(target) is False:
        return 1

    # Set-up the server
    server = Server(target, options.address, options.port)

    # Check instance is up to date
    context = get_fake_context()
    server.init_context(context)
    if not is_instance_up_to_date(server.root):
        print 'The instance is not up-to-date, please type:'
        print
        print '    $ icms-update.py %s' % target
        print
        return 1

    # Listen
    address = server.address or '*'
    port = server.port
    print '[%s] Web Server listens %s:%s' % (target, address, port)

    # GO GO GO
    pid = fork()
    if pid > 0:
        if options.detach:
            become_daemon()

        # Start
        server.start()
        exit(0)

    return 0


if __name__ == '__main__':
    # The command line parser
    usage = ('%prog [OPTIONS] TARGET\n'
             '       %prog TARGET [TARGET]*')
    version = 'itools %s' % __version__
    description = ('Starts a web server that publishes the TARGET ikaaro'
                   ' instance to the world. If several TARGETs are given, one'
                   ' server will be started for each one (in this mode no'
                   ' options are available).')
    parser = OptionParser(usage, version=version, description=description)
    parser.add_option(
        '-a', '--address', help='listen to IP ADDRESS')
    parser.add_option(
        '-d', '--detach', action="store_true", default=False,
        help="Detach from the console.")
    parser.add_option(
        '-p', '--port', type='int', help='listen to PORT number')

    options, args = parser.parse_args()
    n_args = len(args)
    if n_args == 0:
        parser.error('The TARGET argument is missing.')
    elif n_args == 1:
        pass
    elif options.address or options.detach or options.port:
        parser.error('Options are not available when starting several '
                     'servers at once.')

    # Action!
    ret = 0
    for target in args:
        ret += start(options, target)
    exit(ret)
