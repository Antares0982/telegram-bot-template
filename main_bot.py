#!/usr/bin/python3 -O
# region import
import logging
from typing import List

from telegram.ext import CallbackContext

from basebot import baseBot
from example1 import exampleBot1
from example2 import exampleBot2
from utils import *

# endregion


class mainBot(exampleBot1, exampleBot2):  # 继承的功能类,handle时从左到右优先级逐次降低
    def __init__(self) -> None:
        print("subclasses init")
        for cls in self.__class__.__bases__:
            cls.__init__(self)
        print("all subclasses init finished")

    @commandCallbackMethod
    def exec(self, update: Update, context: CallbackContext) -> None:
        if not isfromme(update):
            self.errorInfo("没有权限")
            return

        if len(context.args) == 0:
            self.errorInfo("没有接收到命令诶")
            return
        try:
            needReturn = False
            txt = update.message.text
            if context.args[0] == "r":
                needReturn = True
                command = txt[txt.find("r ") + 2 :]
            else:
                command = " ".join(context.args)

            if not command:
                raise ValueError

            if not needReturn:
                try:
                    exec(command)
                except Exception as e:
                    self.reply(text="执行失败……")
                    raise e
                self.reply(text="执行成功～")
            else:
                try:
                    exec("t=" + command)
                    ans = locals()["t"]
                except Exception as e:
                    self.reply(text="执行失败……")
                    raise e
                self.reply(text=f"执行成功，返回值：{ans}")
        except (TypeError, ValueError):
            self.reply(text="唔……似乎参数不对呢")
        except Exception as e:
            raise e

    def textHandler(self, update: Update, context: CallbackContext) -> bool:
        fakeself = self.renewStatus(update)
        fakeself.debuginfo(f"Text message come in, chat: {fakeself.lastchat}")

        if update.message is None:
            return True

        if update.message.migrate_from_chat_id is not None:
            fakeself.chatmigrate(
                update.message.migrate_from_chat_id, getchatid(update), fakeself
            )
            return True

        with self.lock:
            if any(x in self.blacklist for x in (fakeself.lastuser, fakeself.lastchat)):
                return fakeself.errorInfo("你在黑名单中，无法使用任何功能")

        for cls in self.__class__.__bases__:
            status: handleStatus = cls.textHandler(fakeself, update, context)
            if status.blocked():
                return status.normal

        return False

    def buttonHandler(self, update: Update, context: CallbackContext) -> bool:
        fakeself = self.renewStatus(update)
        fakeself.debuginfo(f"Button pressed, chat: {fakeself.lastchat}")
        update.callback_query.answer()

        if any(x in self.blacklist for x in (fakeself.lastuser, fakeself.lastchat)):
            return fakeself.queryError(update.callback_query)

        for cls in self.__class__.__bases__:
            status: handleStatus = cls.buttonHandler(fakeself, update, context)
            if status.blocked():
                return status.normal

        return fakeself.queryError(update.callback_query)

    def photoHandler(self, update: Update, context: CallbackContext) -> bool:
        fakeself = self.renewStatus(update)
        fakeself.debuginfo(f"Photo message come in, chat: {fakeself.lastchat}")

        if fakeself.lastchat in self.blacklist:
            return self.errorInfo("你在黑名单中，无法使用任何功能")

        for cls in self.__class__.__bases__:
            status: handleStatus = cls.photoHandler(fakeself, update, context)
            if status.blocked():
                return status.normal

        return False

    def channelHandler(self, update: Update, context: CallbackContext) -> bool:
        fakeself = self.renewStatus(update)
        if fakeself.lastchat in fakeself.blacklist:
            return False

        if update.channel_post is not None:
            for cls in self.__class__.__bases__:
                status: handleStatus = cls.channelHandler(fakeself, update, context)
                if status.blocked():
                    return status.normal

        elif update.edited_channel_post is not None:
            for cls in self.__class__.__bases__:
                status: handleStatus = cls.editedChannelHandler(
                    fakeself, update, context
                )
                if status.blocked():
                    return status.normal

        return False

    @classmethod
    def chatmigrate(cls, oldchat: int, newchat: int, instance: "mainBot"):
        errs: List[Exception] = []
        try:
            baseBot.chatmigrate(oldchat, newchat, instance)
        except Exception as e:
            errs.append(e)

        for kls in cls.__bases__:
            try:
                kls.chatmigrate(oldchat, newchat, instance)
            except Exception as e:
                errs.append(e)

        if len(errs) != 0:
            if len(errs) > 1:
                errstr = "\n".join(str(x) for x in errs)
                raise RuntimeError(f"聊天迁移时抛出多于一个错误：{errstr}")
            raise errs[0]

    def beforestop(self):
        for cls in self.__class__.__bases__:
            cls.beforestop(self)


def main():
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=logging.INFO,
    )
    global mainbot
    mainbot = mainBot()
    mainbot.start()


if __name__ == "__main__":
    main()
