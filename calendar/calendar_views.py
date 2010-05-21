# -*- coding: UTF-8 -*-
# Copyright (C) 2006-2008 Hervé Cauwelier <herve@itaapy.com>
# Copyright (C) 2006-2008 Nicolas Deram <nicolas@itaapy.com>
# Copyright (C) 2007-2008 Juan David Ibáñez Palomar <jdavid@itaapy.com>
# Copyright (C) 2007-2008 Sylvain Taverne <sylvain@itaapy.com>
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

# Import from Standard Library
from calendar import monthrange, isleap
from cStringIO import StringIO
from datetime import date, datetime, time, timedelta
from operator import itemgetter

# Import from itools
from itools.datatypes import Date, Integer
from itools.gettext import MSG
from itools.ical import Time
from itools.stl import stl
from itools.uri import encode_query, get_reference
from itools.web import BaseView, STLForm, STLView, get_context, INFO, ERROR
from itools.xapian import AndQuery, PhraseQuery, RangeQuery

# Import from ikaaro
from ikaaro.datatypes import FileDataType
from ikaaro import messages
from grid import get_grid_data


resolution = timedelta.resolution


months = {
    1: MSG(u'January'),
    2: MSG(u'February'),
    3: MSG(u'March'),
    4: MSG(u'April'),
    5: MSG(u'May'),
    6: MSG(u'June'),
    7: MSG(u'July'),
    8: MSG(u'August'),
    9: MSG(u'September'),
    10: MSG(u'October'),
    11: MSG(u'November'),
    12: MSG(u'December')}

days = {
    0: MSG(u'Monday'),
    1: MSG(u'Tuesday'),
    2: MSG(u'Wednesday'),
    3: MSG(u'Thursday'),
    4: MSG(u'Friday'),
    5: MSG(u'Saturday'),
    6: MSG(u'Sunday')}



def build_timetables(start_time, end_time, interval):
    """Build a list of timetables represented as tuples(start, end).
    Interval is given by minutes.
    """
    start =  datetime(2000, 1, 1)
    if start_time:
        start = datetime.combine(start.date(), start_time)
    end =  datetime(2000, 1, 1, 23, 59)
    if end_time:
        end = datetime.combine(start.date(), end_time)

    timetables, tt_start = [], start
    while tt_start < end:
        tt_end = tt_start + timedelta(minutes=interval)
        timetables.append((tt_start.time(), tt_end.time()))
        tt_start = tt_end
    return timetables



def get_current_date(value):
    """Get date as a date object from string value.
    By default, get today's date as a date object.
    """
    if value is None:
        return date.today()
    try:
        return Date.decode(value)
    except ValueError:
        return date.today()



class TimetablesForm(STLForm):

    access = 'is_allowed_to_edit'
    title = MSG(u'Timetables')
    template = '/ui/calendar/edit_timetables.xml'
    styles = ['/ui/calendar/style.css']


    def get_namespace(self, resource, context):
        # Show current timetables only if previously set in metadata
        if resource.has_property('timetables'):
            timetables = resource.get_property('timetables')
            timetables_ns = [
                {'index': index,
                 'startname': '%s_start' % index,
                 'endname': '%s_end' % index,
                 'start': Time.encode(start),
                 'end': Time.encode(end)}
                for index, (start, end) in enumerate(timetables) ]
        else:
            timetables_ns = []

        # Ok
        return {'timetables': timetables_ns}


    action_add_schema = {'new_start': Time, 'new_end': Time}
    def action_add(self, resource, context, form):
        # Check start time is before end time
        start = form['new_start']
        end = form['new_end']
        if start >= end:
            message = ERROR(u'Start time must be earlier than end time.')
            context.message = message
            return

        # Check the given range is not defined yet
        timetables = resource.get_property('timetables')
        if (start, end) in timetables:
            context.message = ERROR(u'The given range is already defined.')
            return

        # Add new range
        timetables = list(timetables)
        timetables.append((start, end))
        timetables.sort()
        resource.set_property('timetables', tuple(timetables))
        # Ok
        context.message = messages.MSG_CHANGES_SAVED


    action_remove_schema = {'ids': Integer(multiple=True)}
    def action_remove(self, resource, context, form):
        ids = form['ids']
        if len(ids) == 0:
            context.message = ERROR(u'Nothing to remove.')
            return

        # New timetables
        timetables = resource.get_property('timetables')
        timetables = [
            timetable for index, timetable in enumerate(timetables)
            if index not in ids ]
        resource.set_property('timetables', tuple(timetables))
        # Ok
        context.message = INFO(u'Timetable(s) removed successfully.')


    def action_update(self, resource, context, form):
        timetables = resource.get_property('timetables')
        if len(timetables) == 0:
            context.message = ERROR(u'Nothing to change.')
            return

        # Update timetable or just set index to next index
        new_timetables = []
        for index in range(len(timetables)):
            try:
                start = context.get_form_value('%s_start' % index, type=Time)
                end = context.get_form_value('%s_end' % index, type=Time)
            except:
                context.message = ERROR(u'Wrong time selection (HH:MM).')
                return

            if start >= end:
                message = ERROR(u'Start time must be earlier than end time.')
                context.message = message
                return

            new_timetables.append((start, end))

        new_timetables.sort()
        resource.set_property('timetables', tuple(new_timetables))
        # Ok
        context.message = messages.MSG_CHANGES_SAVED



class CalendarView(STLView):

    styles = ['/ui/calendar/style.css']
    # default viewed fields on monthly_view
    default_viewed_fields = ('dtstart', 'dtend', 'title', 'status')


    def get_first_day(self):
        """Returns 0 if Sunday is the first day of the week, else 1.
        For now it has to be overridden to return anything else than 1.
        """
        return 1


    def get_with_new_url(self):
        return True


    def get_week_number(self, c_date):
        """datetime.strftime('%U') gives week number, starting week by sunday
           datetime.strftime('%W') gives week number, starting week by monday
           This week number is calculated as "Week 1" begins on the first
           sunday/monday of the year. Its range is [0, 53].

        We adjust week numbers to fit rules which are used by French people.
        XXX Check for other countries.
        """
        if self.get_first_day() == 1:
            format = '%W'
        else:
            format = '%U'
        week_number = int(c_date.strftime(format))
        # Get day of 1st January, if < friday and != monday then number++
        day, kk = monthrange(c_date.year, 1)
        if day in (1, 2, 3):
            week_number = week_number + 1
        return week_number


    def add_selector_ns(self, c_date, method, namespace):
        """Set header used to navigate into time.

        """
        week_number = '%0d' % self.get_week_number(c_date)
        current_week = MSG(u'Week {n}').gettext(n=week_number)
        tmp_date = c_date - timedelta(7)
        previous_week = ";%s?date=%s" % (method, Date.encode(tmp_date))
        tmp_date = c_date + timedelta(7)
        next_week = ";%s?date=%s" % (method, Date.encode(tmp_date))
        # Month
        current_month = months[c_date.month].gettext()
        delta = 31
        if c_date.month != 1:
            kk, delta = monthrange(c_date.year, c_date.month - 1)
        tmp_date = c_date - timedelta(delta)
        previous_month = ";%s?date=%s" % (method, Date.encode(tmp_date))
        kk, delta = monthrange(c_date.year, c_date.month)
        tmp_date = c_date + timedelta(delta)
        next_month = ";%s?date=%s" % (method, Date.encode(tmp_date))
        # Year
        date_before = date(c_date.year, 2, 28)
        date_after = date(c_date.year, 3, 1)
        delta = 365
        if (isleap(c_date.year - 1) and c_date <= date_before) \
          or (isleap(c_date.year) and c_date > date_before):
            delta = 366
        tmp_date = c_date - timedelta(delta)
        previous_year = ";%s?date=%s" % (method, Date.encode(tmp_date))
        delta = 365
        if (isleap(c_date.year) and c_date <= date_before) \
          or (isleap(c_date.year +1) and c_date >= date_after):
            delta = 366
        tmp_date = c_date + timedelta(delta)
        next_year = ";%s?date=%s" % (method, Date.encode(tmp_date))
        # Set value into namespace
        namespace['current_week'] = current_week
        namespace['previous_week'] = previous_week
        namespace['next_week'] = next_week
        namespace['current_month'] = current_month
        namespace['previous_month'] = previous_month
        namespace['next_month'] = next_month
        namespace['current_year'] = c_date.year
        namespace['previous_year'] = previous_year
        namespace['next_year'] = next_year
        # Add today link
        tmp_date = date.today()
        namespace['today'] = ";%s?date=%s" % (method, Date.encode(tmp_date))
        return namespace


    # Get days of week based on get_first_day's result for start
    def days_of_week_ns(self, start, num=None, ndays=7, selected=None):
        """
          start : start date of the week
          num : True if we want to get number of the day too
          ndays : number of days we want
          selected : selected date
        """
        current_date = start
        ns_days = []
        for index in range(ndays):
            ns =  {}
            ns['name'] = days[current_date.weekday()].gettext()
            if num:
                ns['nday'] = current_date.day
            else:
                ns['nday'] = None
            if selected:
                ns['selected'] = (selected == current_date)
            else:
                ns['selected'] = None
            ns_days.append(ns)
            current_date = current_date + timedelta(1)
        return ns_days


    ######################################################################
    # Public API
    ######################################################################
    def get_action_url(self, **kw):
        """Action to call on form submission.
        """
        return None


    def search(self, query=None, **kw):
        if query is None:
            query = [ PhraseQuery(name, value) for name, value in kw.items() ]
        else:
            query = [query]

        # Search only events
        query.append(PhraseQuery('format', 'event'))
        query = AndQuery(*query)

        # Search
        return get_context().root.search(query)


    def search_events_in_range(self, start, end, **kw):
        query = [ PhraseQuery(name, value) for name, value in kw.items() ]
        query = AndQuery(
            RangeQuery('dtstart', None, end),
            RangeQuery('dtend', start, None),
            *query)
        return self.search(query)


    def search_events_in_date(self, date, **kw):
        """Return a list of Component objects of type 'VEVENT' matching the
        given date and sorted if requested.
        """
        dtstart = datetime(date.year, date.month, date.day)
        dtend = dtstart + timedelta(days=1) - resolution
        return self.search_events_in_range(dtstart, dtend, **kw)


    def get_events_to_display(self, start, end):
        events = self.search_events_in_range(start, end)
        return events.get_documents(sort_by='dtstart')


    def events_to_namespace(self, resource, events, day, grid=False,
                            show_conflicts=False):
        """Build namespace for events occuring on current day.
        Update events, removing past ones.

        Events is a list of events where each one follows:
          (resource_name, dtstart, event)
          'event' object must have a methods:
              - get_end
              - get_ns_event.
        """
        ns_events = []
        index = 0
        while index < len(events):
            event = events[index]
            event = resource.get_resource(event.name)
            e_dtstart = event.get_property('dtstart').date()
            e_dtend = event.get_property('dtend').date()
            # Current event occurs on current date
            # event begins during current tt
            starts_on = e_dtstart == day
            # event ends during current tt
            ends_on = e_dtend == day
            # event begins before and ends after
            out_on = (e_dtstart < day and e_dtend > day)

            if starts_on or ends_on or out_on:
                current_resource = resource
                conflicts_list = set()
                if show_conflicts:
                    handler = current_resource.handler
                    conflicts = handler.get_conflicts(e_dtstart, e_dtend)
                    if conflicts:
                        for uids in conflicts:
                            conflicts_list.update(uids)
                ns_event = event.get_ns_event(day,
                                              conflicts_list=conflicts_list,
                                              grid=grid, starts_on=starts_on,
                                              ends_on=ends_on, out_on=out_on)
                ns_event['url'] = current_resource.get_action_url(**ns_event)
                ns_event['cal'] = 0
                if 'resource' in ns_event.keys():
                    ns_event['resource']['color'] = 0
                else:
                    ns_event['resource'] = {'color': 0}
                ns_events.append(ns_event)
                # Current event end on current date
                if e_dtend == day:
                    events.remove(events[index])
                    if events == []:
                        break
                else:
                    index = index + 1
            # Current event occurs only later
            elif e_dtstart > day:
                break
            else:
                index = index + 1
        return ns_events, events



class MonthlyView(CalendarView):

    access = 'is_allowed_to_view'
    title = MSG(u'Monthly View')
    template = '/ui/calendar/monthly_view.xml'
    monthly_template = '/ui/calendar/monthly_template.xml'



    def get_namespace(self, resource, context, ndays=7):
        today_date = date.today()

        # Current date
        c_date = context.get_form_value('date')
        c_date = get_current_date(c_date)
        # Save selected date
        context.set_cookie('selected_date', c_date)

        # Method
        method = context.get_cookie('method')
        if method != 'monthly_view':
            context.set_cookie('method', 'monthly_view')

        ###################################################################
        # Calculate start of previous week
        # 0 = Monday, ..., 6 = Sunday
        weekday = c_date.weekday()
        start = c_date - timedelta(7 + weekday)
        if self.get_first_day() == 0:
            start = start - timedelta(1)
        # Calculate last date to take in account as we display  5*7 = 35 days
        end = start + timedelta(35)

        ###################################################################
        # Get a list of events to display on view
        events = self.get_events_to_display(start, end)
        if isinstance(self.monthly_template, str):
            template = resource.get_resource(self.monthly_template)
        else:
            template = self.monthly_template

        ###################################################################
        namespace = {}
        # Add header to navigate into time
        namespace = self.add_selector_ns(c_date, 'monthly_view', namespace)
        # Get header line with days of the week
        namespace['days_of_week'] = self.days_of_week_ns(start, ndays=ndays)

        namespace['weeks'] = []
        day = start
        # 5 weeks
        for w in range(5):
            ns_week = {'days': [], 'month': u''}
            # 7 days a week
            for d in range(7):
                # day in timetable
                if d < ndays:
                    ns_day = {}
                    ns_day['nday'] = day.day
                    ns_day['selected'] = (day == today_date)
                    ns_day['url'] = resource.get_action_url(day=day)
                    # Insert events
                    ns_events, events = self.events_to_namespace(resource,
                        events, day)
                    ns_day['events'] = stl(template, {'events': ns_events})
                    ns_week['days'].append(ns_day)
                    if day.day == 1:
                        month = months[day.month].gettext()
                        ns_week['month'] = month
                day = day + timedelta(1)
            namespace['weeks'].append(ns_week)

        namespace['add_icon'] = '/ui/icons/16x16/add.png'
        return namespace



class WeeklyView(CalendarView):

    access = 'is_allowed_to_view'
    title = MSG(u'Weekly View')
    template = '/ui/calendar/weekly_view.xml'


    def get_weekly_templates(self):
        """Get weekly templates to display events with timetables, and full
        day events.
        """
        return None, None


    # Get timetables as a list of string containing time start of each one
    def get_timetables_grid_ns(self, resource, start_date):
        """Build namespace to give as grid to gridlayout factory.
        """
        ns_timetables = []
        for start, end in resource.get_timetables():
            for value in (start, end):
                value = Time.encode(value)
                if value not in ns_timetables:
                    ns_timetables.append(value)
        return ns_timetables


    def get_grid_events(self, resource, start_date, ndays=7, headers=None,
                        step=timedelta(1)):
        """Build namespace to give as data to gridlayout factory.
        """
        # Get events by day
        ns_days = []
        current_date = start_date

        if headers is None:
            headers = [None] * ndays

        # For each found calendar (or self), get events
        events = []
        # Get a list of events to display on view
        end = start_date + timedelta(days=ndays)
        events = self.get_events_to_display(start_date, end)
        for header in headers:
            ns_day = {}
            # Add header if given
            ns_day['header'] = header
            # Insert events
            ns_events, events = self.events_to_namespace(resource, events,
                                current_date, grid=True)
            ns_day['events'] = ns_events
            ns_days.append(ns_day)
            current_date = current_date + step

        return ns_days


    def get_namespace(self, resource, context, ndays=7):
        # Current date
        c_date = context.get_form_value('date')
        if not c_date:
            c_date = context.get_cookie('selected_date')
        c_date = get_current_date(c_date)
        # Save selected date
        context.set_cookie('selected_date', c_date)

        # Method
        method = context.get_cookie('method')
        if method != 'weekly_view':
            context.set_cookie('method', 'weekly_view')

        # Calculate start of current week: 0 = Monday, ..., 6 = Sunday
        weekday = c_date.weekday()
        start = c_date - timedelta(weekday)
        if self.get_first_day() == 0:
            start = start - timedelta(1)

        # Add header to navigate into time
        namespace = self.add_selector_ns(c_date, 'weekly_view', {})

        # Get icon to appear to add a new event
        add_icon = '/ui/icons/16x16/add.png'
        namespace['add_icon'] = add_icon

        # Get header line with days of the week
        days_of_week_ns = self.days_of_week_ns(start, True, ndays, c_date)
        ns_headers = []
        for day in days_of_week_ns:
            ns_header = '%s %s' % (day['name'], day['nday'])
            # Tip: Use 'selected' for css class to highlight selected date
            ns_headers.append(ns_header)
        # Calculate timetables and events occurring for current week
        timetables = self.get_timetables_grid_ns(resource, start)

        events = self.get_grid_events(resource, start, headers=ns_headers)

        # Fill data with grid (timetables) and data (events for each day)
        templates = self.get_weekly_templates()
        with_new_url = self.get_with_new_url()
        timetable = get_grid_data(events, timetables, start, templates,
                                  with_new_url, add_icon)
        namespace['timetable_data'] = timetable

        return namespace



class DailyView(CalendarView):

    access = 'is_allowed_to_view'
    title = MSG(u'Daily View')
    template = '/ui/calendar/daily_view.xml'
    query_schema = {
        'date': Date}


    # Start 07:00, End 21:00, Interval 30min
    class_cal_range = (time(7,0), time(21,0), 30)
    class_cal_fields = ('title', 'DTSTART', 'DTEND')


    def get_cal_range(self):
        return self.class_cal_range


    # Get namespace for a resource's lines into daily_view
    def get_ns_calendar(self, calendar, c_date, timetables,
                        method='daily_view', show_conflicts=False):
        cal_fields = self.class_cal_fields
        calendar_name = str(calendar.name)
        args = {'date': Date.encode(c_date), 'method': method}

        # Get a dict for each event, compute colspan
        handler = calendar.handler
        events_by_index = {}
        for event in self.search_events_in_date(c_date).get_documents():
            event = calendar.get_resource(event.name)
            event_start = event.get_property('dtstart')
            event_end = event.get_property('dtend')
            # Compute start and end indexes
            tt_start = 0
            tt_end = len(timetables) - 1
            for tt_index, (start, end) in enumerate(timetables):
                start = datetime.combine(c_date, start)
                end = datetime.combine(c_date, end)
                if start <= event_start:
                    tt_start = tt_index
                if end >= event_end:
                    tt_end = tt_index
                    break
            uid = getattr(event, 'id', getattr(event, 'uid', None))
            events_by_index.setdefault(tt_start, [])
            events_by_index[tt_start].append({
                'title': event.get_property('title'),
                'tt_start': tt_start,
                'tt_end': tt_end,
                'resource_id': calendar_name,
                'event_id': str(uid),
                'colspan': tt_end - tt_start + 1})

        # Organize events in rows
        # If a row index is busy, start a new row
        rows = []
        for index in range(len(timetables)):
            events = events_by_index.get(index)
            if events is None:
                continue
            # Sort events by tt_end to reduce fragmentation
            # Longer events go on lines of their own
            events.sort(key=itemgetter('tt_end'))
            for row_index, event in enumerate(events):
                if not rows or len(rows) <= row_index:
                    rows.append({'events': []})
                current_events = rows[row_index]['events']
                if (current_events
                        and current_events[-1]['tt_end'] >= index):
                    # Overlapping, move on a line of its own
                    rows.append({'events': [event]})
                else:
                    # Enough free space, extend
                    current_events.append(event)

        # Get the list of conflicting events if activated
        if show_conflicts:
            conflicts_list = set()
            conflicts = handler.get_conflicts(c_date)
            if conflicts:
                for uids in conflicts:
                    uids = ['%s/%s' % (calendar_name, uid) for uid in uids]
                    conflicts_list.update(uids)

        # Organize columns
        rows_namespace = []
        for row in rows:
            row_namespace = {}
            columns_namespace = []
            events = row['events']
            event = events.pop(0)
            colspan = 0
            for tt_index, (start, end) in enumerate(timetables):
                if colspan > 0:
                    colspan = colspan - 1
                    continue
                tmp_args = args.copy()
                tmp_args['start_time'] = Time.encode(start)
                tmp_args['end_time'] = Time.encode(end)
                # Init column
                column =  {'class': None,
                           'colspan': 1,
                           'rowspan': 1,
                           'evt_url': None}
                # Add event
                if event and tt_index == event['tt_start']:
                    resource_id = event['resource_id']
                    event_id = event['event_id']
                    tmp_args = args.copy()
                    tmp_args['resource'] = resource_id
                    tmp_args['id'] = event_id
                    go_url = ';edit_event?%s' % encode_query(tmp_args)
                    if show_conflicts and uid in conflicts_list:
                        css_class = 'cal_conflict'
                    else:
                        css_class = 'cal_busy'
                    column['class'] = css_class
                    column['colspan'] = event['colspan']
                    column['evt_url'] = go_url
                    column['title'] = event['title']
                    # Set colspan
                    colspan = event['colspan'] - 1
                    # Delete added event
                    event = None
                    if events != []:
                        event = events.pop(0)
                # Fields in template but not shown
                for field in cal_fields:
                    if field not in column:
                        column[field] = None
                columns_namespace.append(column)
                row_namespace['columns'] = columns_namespace
            rows_namespace.append(row_namespace)

        # Header columns (one line with header and empty cases with only
        # '+' for daily_view)
        url = ';new_resource?type=event&%s' % encode_query(args)
        url = get_reference(url).replace(resource=calendar_name)
        header_columns = [
            url.replace(start_time=Time.encode(x), end_time=Time.encode(y))
            for x, y in timetables ]

        # Return namespace
        return {
            'name': calendar.get_title(),
            'rows': rows_namespace,
            'header_columns': header_columns,
            'url': ';monthly_view?%s' % encode_query(args),
            'rowspan': len(rows) + 1,
        }


    def get_namespace(self, resource, context):
        method = context.get_cookie('method')
        if method != 'daily_view':
            context.set_cookie('method', 'daily_view')

        # Current date
        c_date = context.query['date']
        if c_date is None:
            c_date = date.today()

        # Add a header line with start time of each timetable
        start, end, interval = self.get_cal_range()
        timetables = build_timetables(start, end, interval)

        # Table heading and footer with the time ranges
        delta = timedelta(minutes=45)
        tt_start, tt_end = timetables[0]
        last_start = datetime.combine(c_date, tt_start)
        ns_timetables = [last_start.strftime('%H:%M')]
        # Add next ones if delta time > delta minutes
        for tt_start, tt_end in timetables[1:]:
            tt_start = datetime.combine(c_date, tt_start)
            if (tt_start - last_start) > delta:
                ns_timetables.append(tt_start.strftime('%H:%M'))
                last_start = tt_start
            else:
                ns_timetables.append(None)

        # Ok
        ns_calendars = [self.get_ns_calendar(resource, c_date, timetables)]
        return {
            'date': Date.encode(c_date),
            'firstday': self.get_first_day(),
            'header_timetables': ns_timetables,
            'calendars': ns_calendars}



class Calendar_Import(STLForm):

    access = 'is_allowed_to_edit'
    title = MSG(u'Import')
    template = '/ui/calendar/upload.xml'
    schema = {
        'file': FileDataType(mandatory=True)}


    def action(self, resource, context, form):
        file = form['file']
        filename, mimetype, body = file

        # Check wether the handler is able to deal with the uploaded file
        handler = resource.handler
        if mimetype != 'text/calendar':
            message = messages.MSG_UNEXPECTED_MIMETYPE(mimetype=mimetype)
            context.message = message
            return

        # Replace
        try:
            handler.load_state_from_ical_file(StringIO(body))
        except:
            message = ERROR(u'Failed to load the file, may contain errors.')
            context.message = message
        else:
            context.database.change_resource(resource)
            context.message = INFO(u'Version uploaded')



class Calendar_Export(BaseView):

    access = 'is_allowed_to_view'

    def GET(self, resource, context):
        context.set_content_type('text/calendar')
        context.set_content_disposition('inline', '%s.ics' % resource.name)
        return resource.to_ical()
