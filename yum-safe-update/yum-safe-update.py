#!/usr/bin/python 
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Library General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.

'''
This tools take all available updates and check them one at a time
too see if there dependencies can be resolved.
After the check all packages there had no problems will be updated.
'''

import sys
sys.path.insert(0,'/usr/share/yum-cli')
import yum
from utils import YumUtilBase
from yum.constants import *
import logging

class YumSafeUpdate(YumUtilBase):
    
    NAME = 'yum-safe-update'
    VERSION = '1.0.0'
    USAGE = 'yum-safe-update'
    
    def __init__(self):
        YumUtilBase.__init__(self,
                             YumSafeUpdate.NAME,
                             YumSafeUpdate.VERSION,
                             YumSafeUpdate.USAGE)
        self.logger = logging.getLogger("yum.verbose.cli.safe-update")
        self.good_packages = set()
        self.bad_packages=set()
        self.errors_msgs = {}
        self.opts = None
        self.setup()
        self.check_updates()
        if not self.updates:
            self.logger.info('No available updates')
            return
        self.show_result()
        if not self.opts.check_only:
            self.update_good_packages()
        
    def update_good_packages(self):
        '''
        Updated the updates there is marked as good ones.
        '''
        for po in self.updates:
            if po in self.good_packages:
                self.update(po)
        self.doUtilBuildTransaction()
        sys.exit(self.doUtilTransaction())
        
    def show_result(self):
        '''
        Show the result of the depsolve check
        '''
        self.logger.error('SAFE : The following packages can be updated without problems:')
        for po in self.good_packages:
            self.logger.error("SAFE :   --> %s " % str(po))
                    
        if len(self.bad_packages) > 0:
            self.logger.error('SAFE : The following packages has problems:')
            for po in self.bad_packages:
                self.logger.error("SAFE :   --> %s " % str(po))
                msgs = self.errors_msgs[str(po)]
                for msg in msgs:
                    lines = msg.split('\n')
                    for line in lines:
                        self.logger.error("SAFE :   --> %s " % line)
                                   
    def check_updates(self):
        '''
        Check if available updates can be depsolved
        '''
        self.updates = self.doPackageLists('updates').updates
        self.updates.extend(self.doPackageLists('obsoletes').obsoletes)
        # TODO: Add obsoletes too
        i = 0
        for po in self.updates:
            if po not in self.good_packages:
                i +=1
                self.check_package(po)

    def setup(self):
        '''
        Setup the tool
        '''
        self.optparser = self.getOptionParser() 
        self.addCmdOptions()
        try:
            self.opts = self.doUtilConfigSetup()
        except yum.Errors.RepoError, e:
            self.logger.error(str(e))
            sys.exit(50)
                
        # Setup yum (Ts, RPM db, Repo & Sack)
        self.doUtilYumSetup()

    def reset_transaction(self):
        '''
        reset tsInfo for a new run
        '''
        self._tsInfo = None

    def print_transaction(self):
        #transaction set states
        state = { TS_UPDATE     : "update",
                  TS_INSTALL    : "install",
                  TS_TRUEINSTALL: "trueinstall",
                  TS_ERASE      : "erase",
                  TS_OBSOLETED  : "obsoleted",
                  TS_OBSOLETING : "obsoleting",
                  TS_AVAILABLE  : "available",
                  TS_UPDATED    : "updated"}

        self.logger.debug("SAFE :  Current Transaction : %i member(s) " % len(self.tsInfo))
        for txmbr in sorted(self.tsInfo):
            msg = "SAFE :   %-11s : %s " % (state[txmbr.output_state],txmbr.po)
            self.logger.debug( msg)
            for po,rel in sorted(set(txmbr.relatedto)):
                msg = "SAFE :                    %s : %s" % (rel,po)
                self.logger.debug( msg)
        self.logger.debug("SAFE : %s" % (60 * "="))

    def check_package(self,po):
        '''
        Check is a package can be depsolved
        if it depsolves without error the packages and all other packages 
        in the transaction will be marked as good ones.
        
        @param po: package to check
        '''
        self.logger.info('SAFE : Checking : %s' % po)
        self.reset_transaction()
        self.update(po)
        rc, msgs = self.buildTransaction()
        if rc == 2: # Everything is OK
            self.logger.debug("SAFE : %s - OK" % str(po))
            self.logger.debug("SAFE : %s" % (60 * "="))
            for txmbr in self.tsInfo:
                self.good_packages.add(txmbr.po)
        else:
            self.logger.debug("SAFE : %s - FAILED" % str(po))
            self.logger.debug("SAFE : %s" % (60 * "="))
            for msg in msgs:
                lines = msg.split('\n')
                for line in lines:
                    self.logger.error("SAFE :   --> %s " % line)
            self.logger.debug("SAFE : %s" % (60 * "-"))
            self.errors_msgs[str(po)] = msgs
            self.bad_packages.add(po)
        self.print_transaction()
            
    def addCmdOptions(self):
        '''
        Add command line option
        '''
        group = self.getOptionGroup()
        group.add_option("--check-only", default=False, dest="check_only", action="store_true",
          help='Only check if packages can update, dont do the update')
            
        
if __name__ == "__main__":
    app=YumSafeUpdate()