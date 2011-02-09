#!/usr/bin/python -tt
#coding: utf-8
#    This program is free software; you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation; either version 2 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program; if not, write to the Free Software
#    Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#
# (C) 2011 - Tim Lauridsen <timlau@fedoraproject.org>

import dbus
import dbus.service
import dbus.glib
import gobject
import os
import subprocess
import yum
import yum.Errors as Errors

version = 100 # must be integer
DAEMON_ORG = 'org.baseurl.Yum'
DAEMON_INTERFACE = DAEMON_ORG+'.Interface'

class AccessDeniedError(dbus.DBusException):
    _dbus_error_name = DAEMON_ORG+'.AccessDeniedError'

class CommandFailError(dbus.DBusException):
    _dbus_error_name = DAEMON_ORG+'.CommandFailError'

class YumLockedError(dbus.DBusException):
    _dbus_error_name = DAEMON_ORG+'.YumLockedError'

class YumPreBaseConf:
    """This is the configuration interface for the YumBase configuration.
       So if you want to change if plugins are on/off, or debuglevel/etc.
       you tweak it here, and when yb.conf does it's thing ... it happens. """

    def __init__(self):
        self.fn = '/etc/yum/yum.conf'
        self.root = '/'
        self.init_plugins = True
        self.plugin_types = (yum.plugins.TYPE_CORE,)
        self.optparser = None
        self.debuglevel = None
        self.errorlevel = None
        self.disabled_plugins = None
        self.enabled_plugins = None
        self.syslog_ident = None
        self.syslog_facility = None
        self.syslog_device = '/dev/log'
        self.localpkg_gpgcheck = False

class YumexDaemon(dbus.service.Object):

    def __init__(self, mainloop):
        self.mainloop = mainloop # use to terminate mainloop
        self.authorized_sender = set()
        self._lock = None
        bus_name = dbus.service.BusName(DAEMON_ORG, bus = dbus.SystemBus())
        dbus.service.Object.__init__(self, bus_name, '/')
        self._yumbase = None
        
    @property    
    def yumbase(self):
        if not self._yumbase:
            self._get_yumbase()    
        return self._yumbase
        
    # DBUS Methods

    @dbus.service.method(DAEMON_INTERFACE, 
                                          in_signature='ss', 
                                          out_signature='', 
                                          sender_keyword='sender')
    def run(self, command, env_string, sender=None):
        ''' Run a command with root access '''
        self.check_permission(sender)
        command = command.encode('utf8')
        env_string = env_string.encode('utf8')
        env = self.__get_dict(env_string)
        task = subprocess.Popen(command, shell=True, env=env)
        task.wait()
        if task.returncode:
            raise CommandFailError(command, task.returncode)

    @dbus.service.method(DAEMON_INTERFACE, 
                                          in_signature='', 
                                          out_signature='i') 
    def get_version(self):
        return version

    @dbus.service.method(DAEMON_INTERFACE, 
                                          in_signature='', 
                                          out_signature='',
                                          sender_keyword='sender')
    def exit(self, sender=None):
        ''' Exit the daemon'''
        self.check_permission(sender)
        self.mainloop.quit()

    @dbus.service.method(DAEMON_INTERFACE, 
                                          in_signature='', 
                                          out_signature='b',
                                          sender_keyword='sender')
    def lock(self, sender=None):
        ''' get the lock'''
        self.check_permission(sender)
        if not self._lock:
            try:
                self.yumbase.doLock()
                self._lock = sender
                return True
            except Errors.LockError, e:
                raise YumLockedError(str(e))
        return False

    @dbus.service.method(DAEMON_INTERFACE, 
                                          in_signature='s', 
                                          out_signature='as',
                                          sender_keyword='sender')
    def get_packages(self, narrow, sender=None):
        ''' setup '''
        self.check_permission(sender)
        if self.check_lock(sender):
            yh = self.yumbase.doPackageLists(pkgnarrow=narrow)
            pkgs = [str(po) for po in getattr(yh,narrow)]
            return pkgs
        else:
            return []
            
    @dbus.service.method(DAEMON_INTERFACE, 
                                          in_signature='', 
                                          out_signature='b',
                                          sender_keyword='sender')
    def unlock(self, sender=None):
        ''' release the lock'''
        self.check_permission(sender)
        if self.check_lock(sender):
            self.yumbase.doUnlock()
            self._reset_yumbase()
            self._lock = None
            return True
            

    def check_lock(self, sender):
        if self._lock == sender:
            return True
        else:
            raise YumLockedError('Yum is locked by another application')

    def check_permission(self, sender):
        ''' Check for permission to execute'''
        if sender in self.authorized_sender:
            return
        else:
            self._check_permission(sender)
            self.authorized_sender.add(sender)


    def _check_permission(self, sender):
        if not sender: raise ValueError('sender == None')
        
        obj = dbus.SystemBus().get_object('org.freedesktop.PolicyKit1', '/org/freedesktop/PolicyKit1/Authority')
        obj = dbus.Interface(obj, 'org.freedesktop.PolicyKit1.Authority')
        (granted, _, details) = obj.CheckAuthorization(
                ('system-bus-name', {'name': sender}), DAEMON_ORG, {}, dbus.UInt32(1), '', timeout=600)
        if not granted:
            raise AccessDeniedError('Session is not authorized')

    def __get_dict(self, string):
        return eval(string)
    
    def _get_yumbase(self):
        self._yumbase = yum.YumBase()
        
    def _reset_yumbase(self):
        del self._yumbase

def main():
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    mainloop = gobject.MainLoop()
    YumexDaemon(mainloop)
    mainloop.run()

if __name__ == '__main__':
    main()