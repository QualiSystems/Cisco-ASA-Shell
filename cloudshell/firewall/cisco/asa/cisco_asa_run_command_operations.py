#!/usr/bin/python
# -*- coding: utf-8 -*-

import inject

from cloudshell.configuration.cloudshell_cli_binding_keys import CLI_SERVICE
from cloudshell.configuration.cloudshell_shell_core_binding_keys import LOGGER, API
from cloudshell.firewall.operations.interfaces.run_command_interface import RunCommandInterface
from cloudshell.shell.core.context_utils import get_resource_name


class CiscoASARunCommandOperations(RunCommandInterface):
    def __init__(self, resource_name=None, cli_service=None, logger=None, api=None):
        """Create CiscoHandlerBase

        :param cli: CliService object
        :param logger: QsLogger object
        :param snmp: QualiSnmp object
        :param api: CloudShell Api object
        :param resource_name: resource name
        :return:
        """

        self._cli_service = cli_service
        self._logger = logger
        self._api = api
        try:
            self.resource_name = resource_name or get_resource_name()
        except Exception:
            raise Exception('CiscoHandlerBase', 'Failed to get resource_name.')

    @property
    def logger(self):
        return self._logger or inject.instance(LOGGER)

    @property
    def cli_service(self):
        return self._cli_service or inject.instance(CLI_SERVICE)

    @property
    def api(self):
        return self._api or inject.instance(API)

    def run_custom_command(self, command, expected_str=None, expected_map=None, timeout=None, retries=None,
                           is_need_default_prompt=True, session=None):
        """Send command using cli service

        :param command: command to send
        :param expected_str: optional, custom expected string, if you expect something different from default prompts
        :param expected_map: optional, custom expected map, if you expect some actions in progress of the command
        :param timeout: optional, custom timeout
        :param retries: optional, custom retry count, if you need more than 5 retries
        :param is_need_default_prompt: default
        :param session:

        :return: session returned output
        :rtype: string
        """

        if session:
            response = self.cli_service.send_command(command=command, expected_str=expected_str,
                                                     expected_map=expected_map, timeout=timeout, retries=retries,
                                                     is_need_default_prompt=is_need_default_prompt, session=session)
        else:
            response = self.cli_service.send_command(command=command, expected_str=expected_str,
                                                     expected_map=expected_map, timeout=timeout, retries=retries,
                                                     is_need_default_prompt=is_need_default_prompt)
        return response

    def run_custom_config_command(self, command, expected_str=None, expected_map=None, timeout=None, retries=None,
                                  is_need_default_prompt=True):
        """Send list of config commands to the session

        :param command: list of commands to send
        :param expected_str: optional, custom expected string, if you expect something different from default prompts
        :param expected_map: optional, custom expected map, if you expect some actions in progress of the command
        :param timeout: optional, custom timeout
        :param retries: optional, custom retry count, if you need more than 5 retries
        :param is_need_default_prompt: default

        :return session returned output
        :rtype: string
        """

        return self.cli_service.send_config_command(command, expected_str, expected_map, timeout, retries,
                                                    is_need_default_prompt)
