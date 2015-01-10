#!/usr/bin/python
"""
toggl.py

Copyright (c) 2014 D. Robert Adams. All rights reserved.
Modified for toggl API v8 by Beau Raines
Module-ized by T. Scott Barnes

ASCII art from http://patorjk.com/software/taag/#p=display&c=bash&f=Standard
"""

import datetime
import optparse
import os
import sys

from pytoggl.utility import Singleton, Config, DateAndTime, Logger
from pytoggl.toggl import ClientList, ProjectList, TimeEntry, TimeEntryList, User

VERBOSE = False # verbose output?
Parser = None   # OptionParser initialized by main()

#############################################################################
#     ____                                          _   _     _
#    / ___|___  _ __ ___  _ __ ___   __ _ _ __   __| | | |   (_)_ __   ___
#   | |   / _ \| '_ ` _ \| '_ ` _ \ / _` | '_ \ / _` | | |   | | '_ \ / _ \
#   | |__| (_) | | | | | | | | | | | (_| | | | | (_| | | |___| | | | |  __/
#    \____\___/|_| |_| |_|_| |_| |_|\__,_|_| |_|\__,_| |_____|_|_| |_|\___|
#
#############################################################################

#----------------------------------------------------------------------------
# CLI
#----------------------------------------------------------------------------
class CLI(object):
    """
    Singleton class to process command-line actions.
    """
    __metaclass__ = Singleton

    def __init__(self):
        """
        Initializes the command-line parser and handles the command-line
        options.
        """

        # Override the option parser epilog formatting rule.
        # See http://stackoverflow.com/questions/1857346/python-optparse-how-to-include-additional-info-in-usage-output
        optparse.OptionParser.format_epilog = lambda self, formatter: self.epilog

        self.parser = optparse.OptionParser(usage="Usage: %prog [OPTIONS] [ACTION]", \
            epilog="\nActions:\n"
            "  add DESCR [@PROJECT] START_DATETIME ('d'DURATION | END_DATETIME)\n\tcreates a completed time entry\n"
            "  clients\n\tlists all clients\n"
            "  continue DESCR\n\trestarts the given entry\n"
            "  ls\n\tlist recent time entries\n"
            "  now\n\tprint what you're working on now\n"
            "  projects\n\tlists all projects\n"
            "  rm ID\n\tdelete a time entry by id\n"
            "  start DESCR [@PROJECT] [DATETIME]\n\tstarts a new entry\n"
            "  stop [DATETIME]\n\tstops the current entry\n"
            "  www\n\tvisits toggl.com\n"
            "\n"
            "  DURATION = [[Hours:]Minutes:]Seconds\n")
        self.parser.add_option("-q", "--quiet",
                              action="store_true", dest="quiet", default=False,
                              help="don't print anything")
        self.parser.add_option("-v", "--verbose",
                              action="store_true", dest="verbose", default=False,
                              help="print additional info")
        self.parser.add_option("-d", "--debug",
                              action="store_true", dest="debug", default=False,
                              help="print debugging output")

        # self.args stores the remaining command line args.
        (options, self.args) = self.parser.parse_args()

        # Process command-line options.
        Logger.level = Logger.INFO
        if options.quiet:
            Logger.level = Logger.NONE
        if options.debug:
            Logger.level = Logger.DEBUG
        if options.verbose:
            global VERBOSE
            VERBOSE = True

    def _add_time_entry(self, args):
        """
        Creates a completed time entry.
        args should be: DESCR [@PROJECT] START_DATE_TIME
            'd'DURATION | STOP_DATE_TIME
        """
        # Process the args.
        description = self._get_str_arg(args)

        project_name = self._get_project_arg(args, optional=True)
        if project_name is not None:
            project = ProjectList().find_by_name(project_name)
            if project == None:
                raise RuntimeError("Project '%s' not found." % project_name)

        start_time = self._get_datetime_arg(args, optional=False)
        duration = self._get_duration_arg(args, optional=True)
        if duration is None:
            stop_time = self._get_datetime_arg(args, optional=False)
            duration = (stop_time - start_time).total_seconds()
        else:
            stop_time = None

        # Create a time entry.
        entry = TimeEntry(
            description=description,
            start_time=start_time,
            stop_time=stop_time,
            duration=duration,
            project_name=project_name
        )

        Logger.debug(entry.json())
        entry.add()
        Logger.info('%s added' % description)

    def act(self):
        """
        Performs the actions described by the list of arguments in self.args.
        """
        if len(self.args) == 0 or self.args[0] == "ls":
            Logger.info(TimeEntryList())
        elif self.args[0] == "add":
            self._add_time_entry(self.args[1:])
        elif self.args[0] == "clients":
            print ClientList()
        elif self.args[0] == "continue":
            self._continue_entry(self.args[1:])
        elif self.args[0] == "now":
            self._list_current_time_entry()
        elif self.args[0] == "projects":
            print ProjectList()
        elif self.args[0] == "rm":
            self._delete_time_entry(self.args[1:])
        elif self.args[0] == "start":
            self._start_time_entry(self.args[1:])
        elif self.args[0] == "stop":
            self._stop_time_entry(self.args[1:])
        elif self.args[0] == "www":
            os.system(VISIT_WWW_COMMAND)
        else:
            self.print_help()

    def _continue_entry(self, args):
        """
        Continues a time entry. args[0] should be the description of the entry
        to restart. If a description appears multiple times in your history,
        then we restart the newest one.
        """
        if len(args) == 0:
            CLI().print_help()
        entry = TimeEntryList().find_by_description(args[0])
        if entry:
            entry.continue_entry()
            Logger.info("%s continued at %s" % (entry.get('description'),
                DateAndTime().format_time(datetime.datetime.now())))
        else:
            Logger.info("Did not find '%s' in list of entries." % args[0] )

    def _delete_time_entry(self, args):
        """
        Removes a time entry from toggl.
        args must be [ID] where ID is the unique identifier for the time
        entry to be deleted.
        """
        if len(args) == 0:
            CLI().print_help()

        entry_id = args[0]

        for entry in TimeEntryList():
            if entry.get('id') == int(entry_id):
                entry.delete()
                Logger.info("Deleting entry " + entry_id)

    def _get_datetime_arg(self, args, optional=False):
        """
        Returns args[0] as a localized datetime object, or None.
        """
        if len(args) == 0:
            if optional:
                return None
            else:
                self.print_help()
        else:
            return DateAndTime().parse_local_datetime_str(args.pop(0))

    def _get_duration_arg(self, args, optional=False):
        """
        Returns args[0] (e.g. 'dHH:MM:SS') as an integer number of
        seconds, or None.
        """
        if len(args) == 0:
            if optional:
                return None
            else:
                self.print_help()
        elif args[0][0] != 'd':
            if optional:
                return None
            else:
                self.print_help()
        else:
            return DateAndTime().duration_str_to_seconds( args.pop(0)[1:] )

    def _get_project_arg(self, args, optional=False):
        """
        If the first entry in args is a project name (e.g., '@project')
        then return the name of the project, or None.
        """
        if len(args) == 0:
            if optional:
                return None
            else:
                self.print_help()
        elif args[0][0] != '@':
            if optional:
                return None
            else:
                self.print_help()
        else:
            return args.pop(0)[1:]

    def _get_str_arg(self, args, optional=False):
        """
        Returns the first entry in args as a string, or None.
        """
        if len(args) == 0:
            if optional:
                return None
            else:
                self.print_help()
        else:
            return args.pop(0)

    def _list_current_time_entry(self):
        """
        Shows what the user is currently working on.
        """
        entry = TimeEntryList().now()

        if entry != None:
            Logger.info(str(entry))
        else:
            Logger.info("You're not working on anything right now.")

    def print_help(self):
        """Prints the usage message and exits."""
        self.parser.print_help()
        sys.exit(1)

    def _start_time_entry(self, args):
        """
        Starts a new time entry.
        args should be: DESCR [@PROJECT] [DATETIME]
        """
        description = self._get_str_arg(args, optional=False)
        project_name = self._get_project_arg(args, optional=True)
        start_time = self._get_datetime_arg(args, optional=True)

        # Create the time entry.
        entry = TimeEntry(
            description=description,
            start_time=start_time,
            project_name=project_name
        )
        entry.start()
        Logger.debug(entry.json())
        friendly_time = DateAndTime().format_time(DateAndTime().parse_iso_str(entry.get('start')))
        Logger.info('%s started at %s' % (description, friendly_time))

    def _stop_time_entry(self, args):
        """
        Stops the current time entry.
        args contains an optional end time.
        """

        entry = TimeEntryList().now()
        if entry != None:
            if len(args) > 0:
                entry.stop(DateAndTime().parse_local_datetime_str(args[0]))
            else:
                entry.stop()

            Logger.debug(entry.json())
            friendly_time = DateAndTime().format_time(DateAndTime().parse_iso_str(entry.get('stop')))
            Logger.info('%s stopped at %s' % (entry.get('description'), friendly_time))
        else:
            Logger.info("You're not working on anything right now.")

if __name__ == "__main__":
    CLI().act()
    sys.exit(0)
