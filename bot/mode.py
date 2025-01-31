import logging
from functools import wraps
from typing import Callable, List

from telegram import Update
from telegram.ext import Updater, CommandHandler, CallbackContext, run_async, Dispatcher
from telegram.ext.dispatcher import DEFAULT_GROUP

from filters import admin_filter

logger = logging.getLogger(__name__)

ON, OFF = True, False


class Mode:
    _dp: Dispatcher
    _mode_handlers: List[CommandHandler] = []

    def __init__(self, mode_name: str, default: bool = True, pin_info_msg: bool = False) -> None:
        self.name = mode_name
        self.default = default
        self.chat_data_key = self._gen_chat_data_key(mode_name)
        self.pin_info_msg = pin_info_msg

        self.handlers_gr = DEFAULT_GROUP

    @staticmethod
    def _gen_chat_data_key(mode_name: str) -> str:
        return f"is_{mode_name}_on".lower()

    def _get_mode_state(self, context: CallbackContext):
        if self.chat_data_key not in context.chat_data:
            context.chat_data[self.chat_data_key] = self.default

        return context.chat_data[self.chat_data_key]

    def _set_mode(self, state: bool, context: CallbackContext):
        context.chat_data[self.chat_data_key] = state
        logger.info(f"new state: {state}")
        if state is ON:
            self._add_mode_handlers()
        elif state is OFF:
            self._remove_mode_handlers()
        else:
            raise ValueError(f"wrong mode state. expect [True, False], got: {state}")

    def _add_on_off_handlers(self):
        self._dp.add_handler(CommandHandler(f"{self.name}_on", self._mode_on, filters=admin_filter), self.handlers_gr)
        self._dp.add_handler(CommandHandler(f"{self.name}_off", self._mode_off, filters=admin_filter), self.handlers_gr)
        self._dp.add_handler(CommandHandler(f"{self.name}", self._mode_status), self.handlers_gr)

    def _remove_mode_handlers(self):
        for h in self._mode_handlers:
            self._dp.remove_handler(h, self.handlers_gr)

    def _add_mode_handlers(self):
        for h in self._mode_handlers:
            self._dp.add_handler(h, self.handlers_gr)

    @run_async
    def _mode_on(self, update: Update, context: CallbackContext):
        logger.info(f"{self.name} switch to ON")
        mode = self._get_mode_state(context)
        if mode is OFF:
            msg = context.bot.send_message(update.effective_chat.id, f"{self.name} is ON")
            if self.pin_info_msg is True:
                context.bot.pin_chat_message(
                    update.effective_chat.id,
                    msg.message_id,
                    disable_notification=True
                )
            self._set_mode(ON, context)

    @run_async
    def _mode_off(self, update: Update, context: CallbackContext):
        logger.info(f"{self.name} switch to OFF")
        mode = self._get_mode_state(context)
        if mode is ON:
            self._set_mode(OFF, context)
            context.bot.send_message(update.effective_chat.id, f"{self.name} is OFF")
            if self.pin_info_msg is True:
                context.bot.unpin_chat_message(update.effective_chat.id)

    @run_async
    def _mode_status(self, update: Update, context: CallbackContext):
        status = "ON" if self._get_mode_state(context) is ON else "OFF"
        msg = f"{self.name} status is {status}"
        logger.info(msg)
        context.bot.send_message(update.effective_chat.id, msg)

    def add(self, func) -> Callable:
        @wraps(func)
        def wrapper(upd: Updater, handlers_group: int):
            self._dp = upd.dispatcher
            self.handlers_gr = handlers_group

            logger.info(f"adding users handlers...")
            func(upd, self.handlers_gr)

            self._mode_handlers = upd.dispatcher.handlers[self.handlers_gr].copy()
            logger.info(f"registered {len(self._mode_handlers)} {self.name} handlers")

            self._add_on_off_handlers()

            if self.default is False:
                self._remove_mode_handlers()

        return wrapper


__all__ = ["Mode"]
