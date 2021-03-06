#!/usr/bin/python
"""
toggl.py

Copyright (c) 2014 D. Robert Adams. All rights reserved.
Modified for toggl API v8 by Beau Raines
Module-ized by T. Scott Barnes

ASCII art from http://patorjk.com/software/taag/#p=display&c=bash&f=Standard
"""

# This file is divided into three main parts.
#   1. Utility Classes - generic support code
#   2. Toggl Models - Toggl-specific data classes
#   3. Command Line Interface - CLI

#import datetime
#import dateutil.parser
#import iso8601
import json
#import optparse
#import os
#import pytz
#import requests
#import sys
#import time
import urllib

from .utility import Singleton, Config, DateAndTime, Logger, httpexec

TOGGL_URL = "https://www.toggl.com/api/v8"
VERBOSE = False # verbose output?

#############################################################################
#    _                    _   __  __           _      _
#   | |_ ___   __ _  __ _| | |  \/  | ___   __| | ___| |___
#   | __/ _ \ / _` |/ _` | | | |\/| |/ _ \ / _` |/ _ \ / __|
#   | || (_) | (_| | (_| | | | |  | | (_) | (_| |  __/ \__ \
#    \__\___/ \__, |\__, |_| |_|  |_|\___/ \__,_|\___|_|___/
#             |___/ |___/
#############################################################################

#----------------------------------------------------------------------------
# ClientList
#----------------------------------------------------------------------------
class ClientList(object):
    """
    A singleton list of clients. A "client object" is a set of properties
    as documented at
    https://github.com/toggl/toggl_api_docs/blob/master/chapters/clients.md
    """

    __metaclass__ = Singleton

    def __init__(self):
        """
        Fetches the list of clients from toggl.
        """
        result = httpexec("%s/clients" % TOGGL_URL, 'get')
        self.client_list = json.loads(result)

    def __iter__(self):
        """
        Start iterating over the clients.
        """
        self.iter_index = 0
        return self

    def next(self):
        """
        Returns the next client.
        """
        if self.iter_index >= len(self.client_list):
            raise StopIteration
        else:
            self.iter_index += 1
            return self.client_list[self.iter_index-1]

    def __str__(self):
        """
        Formats the list of clients as a string.
        """
        s = ""
        for client in self.client_list:
            s = s + "%s\n" % client['name']
        return s.rstrip() # strip trailing \n

#----------------------------------------------------------------------------
# ProjectList
#----------------------------------------------------------------------------
class ProjectList(object):
    """
    A singleton list of projects. A "project object" is a dictionary as
    documented at
    https://github.com/toggl/toggl_api_docs/blob/master/chapters/projects.md
    """

    __metaclass__ = Singleton

    def __init__(self):
        """
        Fetches the list of projects from toggl.
        """
        result = httpexec("%s/workspaces/%s/projects" % (TOGGL_URL, User().get('default_wid')), 'get')
        self.project_list = json.loads(result)

    def find_by_id(self, pid):
        """
        Returns the project object with the given id, or None.
        """
        for project in self:
            if project['id'] == pid:
                return project
        return None

    def find_by_name(self, name_prefix):
        """
        Returns the project object with the given name (or prefix), or None.
        """
        for project in self:
            if project['name'].startswith(name_prefix):
                return project
        return None

    def __iter__(self):
        """
        Start iterating over the projects.
        """
        self.iter_index = 0
        return self

    def next(self):
        """
        Returns the next project.
        """
        if self.iter_index >= len(self.project_list):
            raise StopIteration
        else:
            self.iter_index += 1
            return self.project_list[self.iter_index-1]

    def __str__(self):
        """Formats the project list as a string."""
        s = ""
        clients = ClientList()
        for project in self:
            client_name = ''
            if 'cid' in project:
               for client in clients:
                   if project['cid'] == client['id']:
                       client_name = " - %s" % client['name']
            s = s + "@%s%s\n" % (project['name'], client_name)
        return s.rstrip() # strip trailing \n

#----------------------------------------------------------------------------
# TimeEntry
#----------------------------------------------------------------------------
class TimeEntry(object):
    """
    Represents a single time entry.

    NB: If duration is negative, it represents the amount of elapsed time
    since the epoch. It's not well documented, but toggl expects this duration
    to be in UTC.
    """

    def __init__(self, description=None, start_time=None, stop_time=None, duration=None, project_name=None, data_dict=None):
        """
        Constructor. None of the parameters are required at object creation,
        but the object is validated before data is sent to toggl.
        * description(str) is the optional time entry description.
        * start_time(datetime) is the optional time this entry started.
        * stop_time(datetime) is the optional time this entry ended.
        * duration(int) is the optional duration, in seconds.
        * project_name(str) is the optional name of the project without
          the '@' prefix.
        * data_dict is an optional dictionary created from a JSON-encoded time
          entry from toggl. If this parameter is used to initialize the object,
          its values will supercede any other constructor parameters.
        """

        # All toggl data is stored in the "data" dictionary.
        self.data = {}

        if description is not None:
            self.data['description'] = description

        if start_time is not None:
            self.data['start'] = start_time.isoformat()

        if stop_time is not None:
            self.data['stop'] = stop_time.isoformat()

        if project_name is not None:
            project = ProjectList().find_by_name(project_name)
            if project == None:
                raise RuntimeError("Project '%s' not found." % project_name)
            self.data['pid'] = project['id']

        if duration is not None:
            self.data['duration'] = duration

        # If we have a dictionary of data, use it to initialize this.
        if data_dict is not None:
            self.data = data_dict

        self.data['created_with'] = 'toggl-cli'

    def add(self):
        """
        Adds this time entry as a completed entry.
        """
        self.validate()
        httpexec("%s/time_entries" % TOGGL_URL, "post", self.json())

    def continue_entry(self):
        """
        Continues an existing entry.
        """
        # Was the entry started today or earlier than today?
        start_time = DateAndTime().parse_iso_str( self.get('start') )

        if start_time <= DateAndTime().start_of_today():
            # Entry was from a previous day. Create a new entry from this
            # one, resetting any identifiers or time data.
            new_entry = TimeEntry()
            new_entry.data = self.data.copy()
            new_entry.set('at', None)
            new_entry.set('created_with', 'toggl-cli')
            new_entry.set('duration', None)
            new_entry.set('duronly', False)
            new_entry.set('guid', None)
            new_entry.set('id', None)
            new_entry.set('start', None)
            new_entry.set('stop', None)
            new_entry.set('uid', None)
            new_entry.start()
        else:
            # To continue an entry from today, set duration to
            # 0 - (current_time - duration).
            now = DateAndTime().duration_since_epoch( DateAndTime().now() )
            self.data['duration'] = 0 - (now - int(self.data['duration']))
            self.data['duronly'] = True # ignore start/stop times from now on

            httpexec("%s/time_entries/%s" % (TOGGL_URL, self.data['id']), 'put', data=self.json())

            Logger.debug('Continuing entry %s' % self.json())

    def delete(self):
        """
        Deletes this time entry from the server.
        """
        if not self.has('id'):
            raise Exception("Time entry must have an id to be deleted.")

        url = "%s/time_entries/%s" % (TOGGL_URL, self.get('id'))
        httpexec(url, 'delete')

    def get(self, prop):
        """
        Returns the given toggl time entry property as documented at
        https://github.com/toggl/toggl_api_docs/blob/master/chapters/time_entries.md
        or None, if the property isn't set.
        """
        if prop in self.data:
            return self.data[prop]
        else:
            return None

    def has(self, prop):
        """
        Returns True if this time entry has the given property and it's not
        None, False otherwise.
        """
        return prop in self.data and self.data[prop] is not None

    def json(self):
        """
        Returns a JSON dump of this entire object as toggl payload.
        """
        return '{"time_entry": %s}' % json.dumps(self.data)

    def normalized_duration(self):
        """
        Returns a "normalized" duration. If the native duration is positive,
        it is simply returned. If negative, we return current_time + duration
        (the actual amount of seconds this entry has been running). If no
        duration is set, raises an exception.
        """
        if 'duration' not in self.data:
            raise Exception('Time entry has no "duration" property')
        if self.data['duration'] > 0:
            return int(self.data['duration'])
        else:
            return time.time() + int(self.data['duration'])

    def set(self, prop, value):
        """
        Sets the given toggl time entry property to the given value. If
        value is None, the property is removed from this time entry.
        Properties are documented at
        https://github.com/toggl/toggl_api_docs/blob/master/chapters/time_entries.md
        """
        if value is not None:
            self.data[prop] = value
        elif prop in self.data:
            self.data.pop(prop)

    def start(self):
        """
        Starts this time entry by telling toggl. If this entry doesn't have
        a start time yet, it is set to now. duration is set to
        0-start_time.
        """
        if self.has('start'):
            start_time = DateAndTime().parse_iso_str(self.get('start'))
            self.set('duration', 0-DateAndTime().duration_since_epoch(start_time))

            self.validate()

            httpexec("%s/time_entries" % TOGGL_URL, "post", self.json())
        else:
            # 'start' is ignored by 'time_entries/start' endpoint. We define it
            # to keep consinstency with toggl server
            self.data['start'] = DateAndTime().now().isoformat()

            httpexec("%s/time_entries/start" % TOGGL_URL, "post", self.json())

        Logger.debug('Started time entry: %s' % self.json())

    def stop(self, stop_time=None):
        """
        Stops this entry. Sets the stop time at the datetime given, calculates
        a duration, then updates toggl.
        stop_time(datetime) is an optional datetime when this entry stopped. If
        not given, then stops the time entry now.
        """
        Logger.debug('Stopping entry %s' % self.json())
        self.validate()
        if int(self.data['duration']) >= 0:
            raise Exception("toggl: time entry is not currently running.")
        if 'id' not in self.data:
            raise Exception("toggl: time entry must have an id.")

        if stop_time is None:
            stop_time = DateAndTime().now()
        self.set('stop', stop_time.isoformat())
        self.set('duration', \
            DateAndTime().duration_since_epoch(stop_time) + int(self.get('duration')))

        httpexec("%s/time_entries/%d" % (TOGGL_URL, self.get('id')), 'put', self.json())

    def __str__(self):
        """
        Returns a human-friendly string representation of this time entry.
        """
        if self.data['duration'] > 0:
            is_running = '  '
        else:
            is_running = '* '

        if 'pid' in self.data:
            project_name = " @%s " % ProjectList().find_by_id(self.data['pid'])['name']
        else:
            project_name = " "

        s = "%s%s%s%s" % (is_running, self.data['description'], project_name,
            DateAndTime().elapsed_time(int(self.normalized_duration())) \
        )

        if VERBOSE:
            s += " [%s]" % self.data['id']

        return s

    def validate(self):
        """
        Ensure this time entry contains the minimum information required
        by toggl, as well as passing some basic sanity checks. If not,
        an exception is raised.

        * toggl requires start, duration, and created_with.
        * toggl doesn't require a description, but we do.
        """
        for prop in [ 'start', 'duration', 'description', 'created_with' ]:
            if not self.has(prop):
                Logger.debug(self.json())
                raise Exception("toggl: time entries must have a '%s' property." % prop)
        return True

#----------------------------------------------------------------------------
# TimeEntryList
#----------------------------------------------------------------------------
class TimeEntryList(object):
    """
    A singleton list of recent TimeEntry objects.
    """

    __metaclass__ = Singleton

    def __init__(self):
        """
        Fetches time entry data from toggl.
        """
        self.reload()

    def __iter__(self):
        """
        Start iterating over the time entries.
        """
        self.iter_index = 0
        return self

    def find_by_description(self, description):
        """
        Searches the list of entries for the one matching the given
        description, or return None. If more than one entry exists
        with a matching description, the most recent one is
        returned.
        """
        for entry in reversed(self.time_entries):
            if entry.get('description') == description:
                return entry
        return None

    def next(self):
        """
        Returns the next time entry object.
        """
        if self.iter_index >= len(self.time_entries):
            raise StopIteration
        else:
            self.iter_index += 1
            return self.time_entries[self.iter_index-1]

    def now(self):
        """
        Returns the current time entry object or None.
        """
        for entry in self:
            if int(entry.get('duration')) < 0:
                return entry
        return None

    def reload(self):
        """
        Force reloading time entry data from the server. Returns self for
        method chaining.
        """
        # Fetch time entries from 00:00:00 yesterday to 23:59:59 today.
        url = "%s/time_entries?start_date=%s&end_date=%s" % \
            (TOGGL_URL, urllib.quote(DateAndTime().start_of_yesterday().isoformat('T')), \
            urllib.quote(DateAndTime().last_minute_today().isoformat('T')))
        Logger.debug(url)
        entries = json.loads( httpexec(url, 'get') )

        # Build a list of entries.
        self.time_entries = []
        for entry in entries:
            te = TimeEntry(data_dict=entry)
            Logger.debug(te.json())
            Logger.debug('---')
            self.time_entries.append(te)

        # Sort the list by start time.
        sorted(self.time_entries, key=lambda entry: entry.data['start'])
        return self

    def __str__(self):
        """
        Returns a human-friendly list of recent time entries.
        """
        # Sort the time entries into buckets based on "Month Day" of the entry.
        days = { }
        for entry in self.time_entries:
            start_time = DateAndTime().parse_iso_str(entry.get('start')).strftime("%Y-%m-%d")
            if start_time not in days:
                days[start_time] = []
                days[start_time].append(entry)

        # For each day, print the entries, and sum the times.
        s = ""
        for date in sorted(days.keys()):
            s += date + "\n"
            duration = 0
            for entry in days[date]:
                s += str(entry) + "\n"
                duration += entry.normalized_duration()
                s += "  (%s)\n" % DateAndTime().elapsed_time(int(duration))

        return s.rstrip() # strip trailing \n

#----------------------------------------------------------------------------
# User
#----------------------------------------------------------------------------
class User(object):
    """
    Singleton toggl user data.
    """

    __metaclass__ = Singleton

    def __init__(self):
        """
        Fetches user data from toggl.
        """
        result = httpexec("%s/me" % TOGGL_URL, 'get')
        result_dict = json.loads(result)

        # Results come back in two parts. 'since' is how long the user has
        # had their toggl account. 'data' is a dictionary of all the other
        # user data.
        self.data = result_dict['data']
        self.data['since'] = result_dict['since']

    def get(self, prop):
        """
        Return the given toggl user property. User properties are
        documented at https://github.com/toggl/toggl_api_docs/blob/master/chapters/users.md
        """
        return self.data[prop]
