# -*- coding: UTF-8 -*-
# Copyright (C) 2011 Juan David Ibáñez Palomar <jdavid@itaapy.com>
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
from itools.core import merge_dicts
from itools.datatypes import String
from itools.gettext import MSG
from itools.web import INFO

# Import from ikaaro
from access import RoleAware_BrowseUsers
from autoform import AutoForm, TextWidget
from buttons import BrowseButton, RemoveButton, RenameButton
from config import Configuration
from folder import Folder, Folder_BrowseContent
from messages import MSG_CHANGES_SAVED
from resource_ import DBResource



class Group_BrowseUsers(RoleAware_BrowseUsers):

    schema = {'ids': String(multiple=True)}

    table_columns = [
        ('checkbox', None),
        ('user_id', MSG(u'User ID')),
        ('login_name', MSG(u'Login')),
        ('firstname', MSG(u'First Name')),
        ('lastname', MSG(u'Last Name')),
        ('account_state', MSG(u'State'))]
    table_actions = [
        BrowseButton(access='is_admin', title=MSG(u'Update'))]

    def get_item_value(self, resource, context, item, column):
        if column == 'checkbox':
            members = resource.get_property('members')
            return item.name, (item.name in members)

        proxy = super(Group_BrowseUsers, self)
        return proxy.get_item_value(resource, context, item, column)


    def action(self, resource, context, form):
        members = form['ids']
        resource.set_property('members', members)
        context.message = MSG_CHANGES_SAVED



class Group(DBResource):

    class_id = 'config-group'
    class_version = '20110606'
    class_title = MSG(u'User Group')

    class_schema = merge_dicts(
        DBResource.class_schema,
        members=String(source='metadata', multiple=True))

    # Views
    class_views = ['browse_users', 'edit']
    browse_users = Group_BrowseUsers()



class AddGroup(AutoForm):

    access = 'is_admin'
    title = MSG(u'Add group')

    schema = {'name': String}
    widgets = [TextWidget('name', title=MSG(u'Name'))]


    def action(self, resource, context, form):
        name = form['name']
        resource.make_resource(form['name'], Group)
        message = INFO(u'Group "{name}" added.', name=name)
        return context.come_back(message, goto=';browse_content')


class BrowseGroups(Folder_BrowseContent):

    access = 'is_admin'
    title = MSG(u'Browse groups')

    search_template = None

    table_columns = [
        ('checkbox', None),
        ('abspath', MSG(u'Name')),
        ('title', MSG(u'Title')),
        ('members', MSG(u'Members')),
        ('mtime', MSG(u'Last Modified')),
        ('last_author', MSG(u'Last Author'))]
    table_actions = [RemoveButton, RenameButton]

    def get_item_value(self, resource, context, item, column):
        if column == 'members':
            brain, item_resource = item
            members = item_resource.get_property('members')
            return len(members)

        proxy = super(BrowseGroups, self)
        return proxy.get_item_value(resource, context, item, column)



class ConfigGroups(Folder):

    class_id = 'config-groups'
    class_title = MSG(u'User Groups')
    class_description = MSG(u'Manage user groups.')
    class_icon48 = 'icons/48x48/groups.png'

    # Views
    class_views = ['browse_content', 'add_group', 'edit', 'commit_log']
    browse_content = BrowseGroups()
    add_group = AddGroup()

    # Configuration
    config_name = 'groups'
    config_group = 'access'



Configuration.register_plugin(ConfigGroups)