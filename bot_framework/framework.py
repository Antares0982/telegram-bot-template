import re
from functools import wraps
from typing import TYPE_CHECKING, Any, Callable, Dict, Optional, Pattern, Type, Union, overload

from telegram import Update
from telegram.ext import CallbackQueryHandler, CommandHandler, MessageHandler, filters

from bot_framework import language
from bot_framework.bot_logging import get_logger
from bot_framework.context_manager import ContextHelper
from bot_framework.error import InvalidQueryException, permission_exceptions, UserPermissionException, InvalidChatTypeException


if TYPE_CHECKING:
    from telegram.ext import BaseHandler

    from bot_framework.context import RichCallbackContext

_LOGGER = get_logger(__name__)


class CallbackBase(object):
    """
    subclass need to implement `kwargs` property
    """
    handler_type: Type["BaseHandler"]

    def __init__(self, func, *args, **kwargs):
        self._instance = None
        self.on_init(*args, **kwargs)
        self._register_and_wrap(func)
        self._pre_executer = None

    def on_init(self, *args, **kwargs):
        raise NotImplementedError

    def _register_and_wrap(self, func):
        wraps(func)(self)

    async def __call__(self, update: Update, context: "RichCallbackContext"):
        # pre execute
        await self.pre_execute(update, context)

        # check blacklist
        # pass
        with ContextHelper(context):
            try:
                if self._instance is not None:
                    return await self.__wrapped__(self._instance, update, context)  # type: ignore
                else:
                    return await self.__wrapped__(update, context)  # type: ignore
            except permission_exceptions() as e:
                try:
                    if isinstance(e, UserPermissionException):
                        from bot_framework.bot_inst import get_bot_instance
                        await get_bot_instance().reply(language.NO_PERMISSION)
                    elif isinstance(e, InvalidChatTypeException):
                        from bot_framework.bot_inst import get_bot_instance
                        await get_bot_instance().reply(language.INVALID_CHAT_TYPE.format(context.chat_type_str()))
                except Exception:
                    _LOGGER.error("%s.__call__", self.__class__.__name__, exc_info=True)
            except InvalidQueryException:
                pass

    def __get__(self, instance, cls):
        if instance is not None:
            self._instance = instance
        return self

    def to_handler(self, **kwds):
        kwds.update(self.kwargs)
        return self.handler_type(callback=self, **kwds)

    async def pre_execute(self, update: Update, context: "RichCallbackContext"):
        if self._pre_executer:
            await self._pre_executer(update, context)

    def __repr__(self) -> str:
        try:
            name = self.__name__  # type: ignore
        except AttributeError:
            name = self.__class__.__name__
        return f"{name}, of type {self.handler_type.__name__}"


class CommandCallback(CallbackBase):
    handler_type = CommandHandler

    def on_init(self, filters, block):
        self.filters = filters
        self.block = block

    @property
    def kwargs(self):
        return {
            "filters": self.filters,
            "block": self.block,
            "command": self.__wrapped__.__name__,
        }


class GeneralCallback(CallbackBase):
    PRE_EXUCUTER_KW = 'pre_executer'

    def on_init(self, handler_type, kwargs):
        self.handler_type = handler_type
        self.kwargs = kwargs
        if self.PRE_EXUCUTER_KW in kwargs:
            self._pre_executer = kwargs[self.PRE_EXUCUTER_KW]
            kwargs.pop(self.PRE_EXUCUTER_KW)


class _CommandCallbackMethodDecor(object):

    """
    Internal decorator for command callback functions.
    """

    def __init__(
        self,
        filters: Optional[filters.BaseFilter] = None,
        block: bool = False
    ):
        self.filters = filters
        self.block = block

    def __call__(self, func):
        return CommandCallback(func, self.filters, self.block)


class GeneralCallbackWrapper(object):
    """
    Internal decorator for command callback functions.
    """

    def __init__(
        self,
        handler_type, **kwargs
    ):
        self.handler_type = handler_type
        self.kwargs = kwargs

    def __call__(self, func):
        return GeneralCallback(func, self.handler_type, self.kwargs)


@overload
def command_callback_wrapper(func: Callable) -> CommandCallback:
    ...


@overload
def command_callback_wrapper(
    block: bool = False,
    filters: Optional[filters.BaseFilter] = None,
) -> CommandCallback:
    ...


def command_callback_wrapper(  # type: ignore
    block: Any = False,
    filters: Optional[filters.BaseFilter] = None,
):
    if callable(block):
        return _CommandCallbackMethodDecor()(block)
    return _CommandCallbackMethodDecor(filters, block)


def general_callback_wrapper(handler_type, block=False, **kwargs):
    if not callable(handler_type):
        raise TypeError("general_callback_wrapper use first argument to identify handler type")
    if 'block' not in kwargs:
        kwargs['block'] = block
    return GeneralCallbackWrapper(handler_type, **kwargs)


async def _btn_pre_executer(update: Update, context: "RichCallbackContext"):
    query = update.callback_query
    assert query is not None and query.data is not None
    await query.answer()


def btn_click_wrapper(
        pattern: Optional[Union[str, Pattern[str], type, Callable[[object], Optional[bool]]]] = None
):
    if isinstance(pattern, str):
        # startswith `pattern`
        pattern = re.compile(f"^{pattern}")
    kwargs: Dict[str, Any] = {}
    kwargs['pattern'] = pattern
    kwargs[GeneralCallback.PRE_EXUCUTER_KW] = _btn_pre_executer
    return general_callback_wrapper(CallbackQueryHandler, **kwargs)


msg_handle_wrapper = general_callback_wrapper(MessageHandler, filters=None)

photo_handle_wrapper = general_callback_wrapper(MessageHandler, filters=filters.PHOTO & (~filters.ChatType.CHANNEL))
