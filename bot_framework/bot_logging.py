import logging
import threading
from logging import Handler, getLevelName
from types import GenericAlias
from typing import Optional, cast


try:
    from rabbitmq_interface import PikaMessageQueue

    PIKA_SUPPORTED = True
except ImportError:
    PIKA_SUPPORTED = False

__logger_top_name = "antares_bot"
__logger_inited = False
__root_logger = None


if PIKA_SUPPORTED:
    _pika_msg_queue = PikaMessageQueue()

    class PikaHandler(Handler):
        def emit(self, record):
            try:
                msg = self.format(record)
                _pika_msg_queue.push("logging." + record.name, msg)
            except RecursionError:  # See issue 36272
                raise
            except Exception:
                self.handleError(record)

        def __repr__(self):
            level = getLevelName(self.level)
            name = self.name
            #  bpo-36015: name can be an int
            name = str(name)
            if name:
                name += ' '
            return '<%s %s(%s)>' % (self.__class__.__name__, name, level)

        __class_getitem__ = classmethod(GenericAlias)  # type: ignore


def log_start(logger_top_name: Optional[str] = None) -> logging.Logger:
    global __logger_inited, __root_logger
    if __logger_inited:
        return cast(logging.Logger, __root_logger)
    __logger_inited = True
    if logger_top_name is not None:
        global __logger_top_name
        __logger_top_name = logger_top_name

    __root_logger = logging.getLogger(__logger_top_name)
    if PIKA_SUPPORTED:
        threading.Thread(target=_pika_msg_queue.run, name="logger_thread").start()
        handler = PikaHandler()
        __root_logger.addHandler(handler)
        # add handler to telegram internal logger
        tg_logger = logging.getLogger("telegram")
        tg_logger.addHandler(handler)
        apscheduler_logger = logging.getLogger("apscheduler")
        apscheduler_logger.addHandler(handler)
    return __root_logger


def get_logger(module_name: str):
    strip_prefix = "modules."
    if module_name.startswith(strip_prefix):
        module_name = module_name[len(strip_prefix):]
    if not __logger_inited:
        raise RuntimeError("logger not inited")
    name = __logger_top_name + "." + module_name
    logger = logging.getLogger(name)
    return logger


def get_root_logger():
    if not __logger_inited:
        raise RuntimeError("logger not inited")
    return __root_logger


def stop_logger():
    if PIKA_SUPPORTED:
        _pika_msg_queue.stop()
