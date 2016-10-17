#!/usr/bin/python
# -*- coding: utf-8 -*-

import inject
import time

from cloudshell.configuration.cloudshell_cli_binding_keys import CLI_SERVICE, SESSION
from cloudshell.configuration.cloudshell_shell_core_binding_keys import LOGGER
from cloudshell.firewall.operations.state_operations import StateOperations
from cloudshell.shell.core.config_utils import override_attributes_from_config


class CiscoASAStateOperations(StateOperations):
    SESSION_WAIT_TIMEOUT = 600
    DEFAULT_PROMPT = r'[>$#]\s*$'

    def __init__(self, cli_service=None, logger=None):
        StateOperations.__init__(self)
        self._cli_service = cli_service
        self._logger = logger
        overridden_config = override_attributes_from_config(CiscoASAStateOperations)
        self._session_wait_timeout = overridden_config.SESSION_WAIT_TIMEOUT
        self._default_prompt = overridden_config.DEFAULT_PROMPT

    @property
    def logger(self):
        return self._logger or inject.instance(LOGGER)

    @property
    def cli(self):
        return self._cli_service or inject.instance(CLI_SERVICE)

    @property
    def session(self):
        return inject.instance(SESSION)

    def reload(self):
        """ Reload device """

        expected_map = {'[\[\(][Yy]es/[Nn]o[\)\]]|\[confirm\]': lambda session: session.send_line('yes'),
                        '\(y\/n\)|continue': lambda session: session.send_line('y'),
                        'reload': lambda session: session.send_line(''),
                        '[\[\(][Yy]/[Nn][\)\]]': lambda session: session.send_line('y')
                        }
        try:
            self.logger.info("Send 'reload' to device...")
            self.cli.send_command(command='reload', expected_map=expected_map, timeout=3)
        except Exception as e:
            self.logger.info('Session type is \'{}\', closing session...'.format(self.session.session_type))

        if self.session.session_type.lower() != 'console':
            self._wait_for_session_restore(self.session)

    def _wait_for_session_restore(self, session):
        self.logger.debug('Waiting session restore')
        waiting_reboot_time = time.time()
        while True:
            try:
                if time.time() - waiting_reboot_time > self._session_wait_timeout:
                    raise Exception(self.__class__.__name__,
                                    "{0} session didn't close in {1} sec as expected".format(self.session.session_type,
                                                                                             self._session_wait_timeout))
                session.send_line('')
                time.sleep(1)
            except:
                self.logger.debug('Session disconnected')
                break
        reboot_time = time.time()
        while True:
            if time.time() - reboot_time > self._session_wait_timeout:
                self.cli.destroy_threaded_session(session=session)
                raise Exception(self.__class__.__name__,
                                'Failed to reconnect {0} session after {1} sec'.format(self.session.session_type,
                                                                                       self._session_wait_timeout))
            try:
                self.logger.debug('Trying to reconnect ...')
                session.connect(re_string=self._default_prompt)
                self.logger.debug('Session connected')
                break
            except:
                time.sleep(5)
