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

# Import from itools
from itools.uri import Path
from itools.web import WebContext
from itools.xapian import OrQuery, PhraseQuery, StartQuery

# Import from ikaaro
from ikaaro.globals import spool, ui
from metadata import Metadata
from registry import get_resource_class


class CMSContext(WebContext):

    def __init__(self, soup_message, path):
        WebContext.__init__(self, soup_message, path)
        self.cache = {}


    def get_template(self, path):
        return ui.get_template(path)


    def send_email(self, to_addr, subject, from_addr=None, text=None,
                   html=None, encoding='utf-8', subject_with_host=True,
                   return_receipt=False):

        # From address
        if from_addr is None and self.user:
            from_addr = user.get_property('email')

        # Subject
        if subject_with_host:
            subject = u'[%s] %s' % (self.uri.authority, subject)

        spool.send_email(to_addr, subject, from_addr=from_addr, text=text,
                        html=html, encoding=encoding,
                        return_receipt=return_receipt)


    #######################################################################
    # Host & Resources
    #######################################################################
    def get_host(self, hostname):
        # Check we have a URI
        if hostname is None:
            return None

        # The site root depends on the host
        catalog = self.mount.database.catalog
        results = catalog.search(vhosts=hostname)
        n = len(results)
        if n == 0:
            return None

        documents = results.get_documents()
        return documents[0].name


    def get_resource(self, path, soft=False):
        if type(path) is Path:
            path = str(path)

        # Get the key
        path = Path(path)
        path.endswith_slash = False
        key = str(path)

        # Cache hit
        resource = self.cache.get(key)
        if resource:
            return resource

        # Load metadata
        target = self.mount.target
        if self.host is None:
            metadata = '%s/database%s.metadata' % (target, key)
        elif key == '/':
            metadata = '%s/database/%s.metadata' % (target, self.host)
        else:
            metadata = '%s/database/%s%s.metadata' % (target, self.host, key)
        database = self.mount.database
        try:
            metadata = database.get_handler(metadata, cls=Metadata)
        except LookupError:
            if soft is False:
                raise
            return None

        # Build resource
        cls = get_resource_class(metadata.format)
        resource = cls(metadata)
        resource.context = self
        resource.path = path
        self.cache[key] = resource
        return resource


    #######################################################################
    # Search
    #######################################################################
    def load_partial_search(self):
        if self.host is None:
            return None

        abspath = '/%s' % self.host
        query = OrQuery(
            PhraseQuery('abspath', abspath),
            StartQuery('abspath', '%s/' % abspath))

        catalog = self.database.catalog
        return catalog.search(query)


    def search(self, query=None, **kw):
        results = self.partial_search
        if results:
            return results.search(query, **kw)

        catalog = self.database.catalog
        return catalog.search(query, **kw)


    #######################################################################
    # Users
    #######################################################################
    def get_user(self, credentials):
        username, password = credentials
        user = self.get_user_by_name(username)
        if user and user.authenticate(password):
            return user
        return None


    def get_user_by_name(self, name):
        return self.get_resource('/users/%s' % name, soft=True)


    def get_user_by_login(self, login):
        """Return the user identified by its unique e-mail or username, or
        return None.
        """
        # Search the user by username (login name)
        results = self.search(username=login)
        n = len(results)
        if n == 0:
            return None
        if n > 1:
            error = 'There are %s users in the database identified as "%s"'
            raise ValueError, error % (n, login)
        # Get the user
        brain = results.get_documents()[0]
        return self.get_user_by_name(brain.name)


    def get_user_title(self, username):
        if username is None:
            return None
        user = self.get_user_by_name(username)
        return user.get_title() if user else None
