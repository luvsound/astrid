import logging
from logging.handlers import SysLogHandler
from service import find_syslog
import warnings

#warnings.simplefilter('always')
#logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger('astrid')
if not logger.handlers:
    logger.addHandler(SysLogHandler(address=find_syslog(), facility=SysLogHandler.LOG_DAEMON))
logger.setLevel(logging.INFO)
