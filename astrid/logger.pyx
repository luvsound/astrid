import logging
from logging.handlers import SysLogHandler, RotatingFileHandler
import os
import warnings
from pprint import pformat

LOG_FORMAT_STRING = '[%(asctime)s] %(levelname)-8s %(threadName)s %(message)s'

class PrettyPrintAdapter(logging.LoggerAdapter):
    def process(self, msg, kwargs):
        return pformat(msg), kwargs

class ColorFormatter(logging.Formatter):
    def format(self, record):
        NORMAL = "\x1b[38;21m"
        WARNING = "\x1b[33;21m"
        ERROR = "\x1b[31;1m"
        CRITICAL = "\x1b[31;1m"
        RESET = "\x1b[0m"

        if record.levelno in (logging.DEBUG, logging.INFO):
            formatter = logging.Formatter(NORMAL + LOG_FORMAT_STRING + RESET)

        elif record.levelno == logging.WARNING:
            formatter = logging.Formatter(WARNING + LOG_FORMAT_STRING + RESET)

        elif record.levelno == logging.ERROR:
            formatter = logging.Formatter(ERROR + LOG_FORMAT_STRING + RESET)

        elif record.levelno in (logging.CRITICAL, logging.EXCEPTION):
            formatter = logging.Formatter(CRITICAL + LOG_FORMAT_STRING + RESET)

        return formatter.format(record)
    
logger = logging.getLogger('astrid')

if not logger.handlers:
    _syslog = SysLogHandler(address='/dev/log', facility=SysLogHandler.LOG_DAEMON)
    _syslog.setFormatter(ColorFormatter())
    logger.addHandler(_syslog)

    _logfile = RotatingFileHandler('astrid.log', mode='a', maxBytes=2**20, backupCount=4)
    _logfile.setFormatter(logging.Formatter(LOG_FORMAT_STRING))
    logger.addHandler(_logfile)

    _streamHandler = logging.StreamHandler()
    _streamHandler.setFormatter(ColorFormatter())
    logger.addHandler(_streamHandler)

    logger.setLevel(logging.DEBUG)
    warnings.simplefilter('always')

    #logger.setLevel(logging.INFO)

logger = PrettyPrintAdapter(logger, {})
