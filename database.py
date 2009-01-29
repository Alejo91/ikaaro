# -*- coding: UTF-8 -*-
# Copyright (C) 2009 Juan David Ibáñez Palomar <jdavid@itaapy.com>
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
from os import devnull
from subprocess import call

# Import from itools
from itools.handlers import ReadOnlyDatabase as BaseReadOnlyDatabase
from itools.handlers import SafeDatabase
from itools import vfs
from itools.web import get_context
from itools.xapian import Catalog, make_catalog

# Import from ikaaro
from folder import Folder
from registry import get_register_fields



class ReadOnlyDatabase(BaseReadOnlyDatabase):

    def __init__(self, target):
        BaseReadOnlyDatabase.__init__(self)

        # Git archive
        self.path = '%s/database' % target

        # The catalog
        self.catalog = Catalog('%s/catalog' % target, get_register_fields(),
                               read_only=True)



class Database(SafeDatabase):
    """Adds a Git archive to the itools database.
    """

    def __init__(self, target):
        SafeDatabase.__init__(self, '%s/database.commit' % target)

        # Git archive
        self.path = '%s/database' % target
        self.new_files = []

        # The catalog
        self.catalog = Catalog('%s/catalog' % target, get_register_fields())

        # Events
        self.resources_added = {}
        self.resources_changed = {}
        self.resources_removed = set()


    #######################################################################
    # Events API
    #######################################################################
    def remove_resource(self, resource):
        resources_removed = self.resources_removed
        resources_added = self.resources_added

        if isinstance(resource, Folder):
            for x in resource.traverse_resources():
                path = str(x.get_canonical_path())
                if path in resources_added:
                    del resources_added[path]
                resources_removed.add(path)
        else:
            path = str(resource.get_canonical_path())
            if path in resources_added:
                del resources_added[path]
            resources_removed.add(path)


    def add_resource(self, resource):
        resources_added = self.resources_added

        # Catalog
        if isinstance(resource, Folder):
            for x in resource.traverse_resources():
                path = str(x.get_canonical_path())
                resources_added[path] = x
        else:
            path = str(resource.get_canonical_path())
            resources_added[path] = resource


    def change_resource(self, resource):
        path = str(resource.get_canonical_path())
        self.resources_changed[path] = resource


    #######################################################################
    # Transactions API
    #######################################################################
    def before_commit(self):
        catalog = self.catalog
        new_files = self.new_files

        # Removed
        for path in self.resources_removed:
            catalog.unindex_document(path)
        self.resources_removed.clear()

        # Added
        resources_added = self.resources_added
        for path in resources_added:
            resource = resources_added[path]
            # Git
            new_files.extend(resource.get_files_to_archive())
            # Catalog
            catalog.index_document(resource)
        resources_added.clear()

        # Changed
        resources_changed = self.resources_changed
        for path in resources_changed:
            resource = resources_changed[path]
            # Git
            new_files.extend(resource.get_files_to_archive())
            # Catalog
            catalog.unindex_document(path)
            catalog.index_document(resource)
        resources_changed.clear()


    def save_changes(self):
        SafeDatabase.save_changes(self)

        # Git
        new_files = [ x for x in self.new_files if vfs.exists(x) ]
        if new_files:
            command = ['git', 'add'] + new_files
            call(command, cwd=self.path)
        if self.new_files:
            self.new_files = []

        # Commit author & message
        author = 'nobody <>'
        message = 'no comment'
        context = get_context()
        if context is not None:
            # Author
            user = context.user
            if user is not None:
                author = '%s <%s>' % (user.name, user.get_property('email'))
            # Message
            try:
                message = getattr(context, 'git_message')
            except AttributeError:
                pass
            else:
                message = message.encode('utf-8')

        # Commit
        command = [
            'git', 'commit', '-a', '--author=%s' % author, '-m', message]
        with open(devnull) as null:
            call(command, cwd=self.path, stdout=null)

        # Catalog
        self.catalog.save_changes()


    def abort_changes(self):
        SafeDatabase.abort_changes(self)

        # Git
        self.new_files = []
        command = ['git', 'reset', '--']
        call(command, cwd=self.path)

        # Catalog
        self.catalog.abort_changes()

        # Clear events
        self.resources_removed.clear()
        self.resources_added.clear()
        self.resources_changed.clear()



def make_database(target):
    # Init git
    path = '%s/database' % target
    command = ['git', 'init']
    with open(devnull) as null:
        call(command, cwd=path, stdout=null)

    # The catalog
    make_catalog('%s/catalog' % target, get_register_fields())

    # Ok
    return Database(target)


def get_database(path, read_only=False):
    if read_only is True:
        return ReadOnlyDatabase(path)

    return Database(path)
