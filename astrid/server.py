import logging
from logging.handlers import SysLogHandler
import os
import time
from service import find_syslog, Service

#from astrid.io import IOManager

class AstridServer(Service):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.logger.addHandler(SysLogHandler(address=find_syslog(), facility=SysLogHandler.LOG_DAEMON))
        self.logger.setLevel(logging.INFO)
        #self.io = IOManager()
        working_directory = os.getcwd()

    def run(self):
        while not self.got_sigterm():
            self.logger.info('doing stuff')
            time.sleep(1)

        self.logger.info('Stopping')
