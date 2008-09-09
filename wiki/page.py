# -*- coding: UTF-8 -*-
# Copyright (C) 2007 Sylvain Taverne <sylvain@itaapy.com>
# Copyright (C) 2007-2008 Henry Obein <henry@itaapy.com>
# Copyright (C) 2007-2008 Hervé Cauwelier <herve@itaapy.com>
# Copyright (C) 2007-2008 Juan David Ibáñez Palomar <jdavid@itaapy.com>
# Copyright (C) 2008 Gautier Hayoun <gautier.hayoun@itaapy.com>
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

# Import from docutils
from docutils.core import publish_doctree
from docutils.readers import get_reader_class
from docutils import nodes

# Import from itools
from itools.gettext import MSG
from itools.handlers import checkid
from itools.uri import get_reference

# Import from ikaaro
from ikaaro.text import Text
from ikaaro.registry import register_object_class
from ikaaro.resource_views import DBResourceNewInstance
from page_views import WikiPageView, WikiPageToPDF, WikiPageEdit, WikiPageHelp



StandaloneReader = get_reader_class('standalone')


class WikiPage(Text):

    class_id = 'WikiPage'
    class_version = '20071217'
    class_title = MSG(u"Wiki Page")
    class_description = MSG(u"Wiki contents")
    class_icon16 = 'wiki/WikiPage16.png'
    class_icon48 = 'wiki/WikiPage48.png'
    class_views = ['view', 'to_pdf', 'edit', 'externaledit', 'upload',
                   'backlinks', 'edit_metadata_form', 'state_form', 'help']

    overrides = {
        # Security
        'file_insertion_enabled': 0,
        'raw_enabled': 0,
        # Encodings
        'input_encoding': 'utf-8',
        'output_encoding': 'utf-8',
    }


    new_instance = DBResourceNewInstance


    #######################################################################
    # API
    #######################################################################
    def resolve_link(self, title):
        parent = self.parent

        # Try regular object name or path
        try:
            return parent.get_resource(title)
        except (LookupError, UnicodeEncodeError):
            # Convert wiki name to object name
            name = checkid(title)
            if name is None:
                return None
            try:
                return parent.get_resource(name)
            except LookupError:
                return None


    def get_document(self):
        parent = self.parent

        # Override dandling links handling
        class WikiReader(StandaloneReader):
            supported = ('wiki',)

            def wiki_reference_resolver(target):
                title = target['name']
                object = self.resolve_link(title)
                if object is None:
                    # Not Found
                    target['wiki_name'] = False
                else:
                    # Found
                    target['wiki_name'] = str(self.get_pathto(object))

                return True

            wiki_reference_resolver.priority = 851
            unknown_reference_resolvers = [wiki_reference_resolver]

        # Publish!
        reader = WikiReader(parser_name='restructuredtext')
        document = publish_doctree(self.handler.to_str(), reader=reader,
                                   settings_overrides=self.overrides)

        # Assume internal paths are relative to the container
        for node in document.traverse(condition=nodes.reference):
            refuri = node.get('refuri')
            # Skip wiki or fragment link
            if node.get('wiki_name') or not refuri:
                continue
            reference = get_reference(refuri.encode('utf_8'))
            # Skip external
            if reference.scheme or reference.authority:
                continue
            # Note: absolute paths will be rewritten as relative paths
            try:
                object = parent.get_resource(reference.path)
                node['refuri'] = str(self.get_pathto(object))
            except LookupError:
                pass

        # Assume image paths are relative to the container
        for node in document.traverse(condition=nodes.image):
            uri  = node['uri'].encode('utf_8')
            reference = get_reference(uri)
            # Skip external
            if reference.scheme or reference.authority:
                continue
            try:
                object = parent.get_resource(reference.path)
                node['uri'] = str(self.get_pathto(object))
            except LookupError:
                pass

        return document


    def get_links(self):
        base = self.get_abspath()

        links = []
        document = self.get_document()
        for node in document.traverse(condition=nodes.reference):
            refname = node.get('wiki_name')
            if refname is False:
                # Wiki link not found
                title = node['name']
                path = checkid(title) or title
                path = base.resolve(path)
            elif refname:
                # Wiki link found, "refname" is the path
                path = base.resolve2(refname)
            else:
                # Regular link, include internal ones
                refuri = node.get('refuri')
                if refuri is None:
                    continue
                reference = get_reference(refuri.encode('utf_8'))
                # Skip external
                if reference.scheme or reference.authority:
                    continue
                path = base.resolve2(reference.path)
            path = str(path)
            links.append(path)

        for node in document.traverse(condition=nodes.image):
            uri = node['uri'].encode('utf_8')
            reference = get_reference(uri)
            # Skip external image
            if reference.scheme or reference.authority:
                continue
            path = base.resolve2(reference.path)
            path = str(path)
            links.append(path)

        return links


    #######################################################################
    # User Interface
    #######################################################################
    view = WikiPageView()
    to_pdf = WikiPageToPDF()
    edit = WikiPageEdit()
    help = WikiPageHelp()


    def get_context_menus(self):
        return self.parent.get_context_menus()



###########################################################################
# Register
###########################################################################
register_object_class(WikiPage)
