#!/usr/bin/python
# -*- coding: utf-8 -*-

import inject
import re
import time

from cloudshell.configuration.cloudshell_cli_binding_keys import CLI_SERVICE
from cloudshell.configuration.cloudshell_shell_core_binding_keys import LOGGER, API
from cloudshell.firewall.cisco.asa.cisco_asa_state_operations import CiscoASAStateOperations
from cloudshell.firewall.cisco.asa.cisco_asa_configuration_operations import CiscoASAConfigurationOperations
from cloudshell.firewall.cisco.asa.firmware_data.cisco_asa_firmware_data import CiscoASAFirmwareData
from cloudshell.firewall.networking_utils import UrlParser
from cloudshell.firewall.operations.interfaces.firmware_operations_interface import FirmwareOperationsInterface
from cloudshell.shell.core.config_utils import override_attributes_from_config
from cloudshell.shell.core.context_utils import get_resource_name


def _get_time_stamp():
    return time.strftime("%d%m%y-%H%M%S", time.localtime())


class CiscoASAFirmwareOperations(FirmwareOperationsInterface):
    SESSION_WAIT_TIMEOUT = 600
    DEFAULT_PROMPT = r'[>$#]\s*$'

    def __init__(self, cli_service=None, logger=None, api=None, resource_name=None):
        self._cli_service = cli_service
        self._logger = logger
        self._api = api
        overridden_config = override_attributes_from_config(CiscoASAFirmwareOperations)
        self._session_wait_timeout = overridden_config.SESSION_WAIT_TIMEOUT
        self._default_prompt = overridden_config.DEFAULT_PROMPT
        try:
            self.resource_name = resource_name or get_resource_name()
        except Exception:
            raise Exception('CiscoASAHandlerBase', 'ResourceName is empty or None')

    @property
    def logger(self):
        return self._logger or inject.instance(LOGGER)

    @property
    def cli_service(self):
        return self._cli_service or inject.instance(CLI_SERVICE)

    @property
    def api(self):
        return self._api or inject.instance(API)

    @property
    def state_operations(self):
        return CiscoASAStateOperations()

    @property
    def configuration_operations(self):
        return CiscoASAConfigurationOperations()

    def load_firmware(self, path):
        """Update firmware version on device by loading provided image, performs following steps:
            1. Copy bin file from remote tftp server.
            2. Clear in run config boot system section.
            3. Set downloaded bin file as boot file and then reboot device.
            4. Check if firmware was successfully installed.

        :param path: full path to firmware file on ftp/tftp location

        :return: status / exception
        """

        url = UrlParser.parse_url(path)
        required_keys = [UrlParser.FILENAME, UrlParser.HOSTNAME, UrlParser.SCHEME]

        if not url or not all(key in url for key in required_keys):
            raise Exception('Cisco ASA', 'Path is wrong or empty')

        file_name = url[UrlParser.FILENAME]
        firmware_obj = CiscoASAFirmwareData(path)

        if firmware_obj.get_name() is None:
            raise Exception('Cisco ASA', "Invalid firmware name!\n \
                                Firmware file must have: title, extension.\n \
                                Example: isr4400-universalk9.03.10.00.S.153-3.S-ext.SPA.bin\n\n \
                                Current path: {}".format(file_name))

        is_downloaded = self.configuration_operations.copy(source_file=path, destination_file='flash:/{}'.format(file_name))

        if not is_downloaded[0]:
            raise Exception('Cisco ASA', "Failed to download firmware from {}!\n {}".format(path, is_downloaded[1]))

        self.cli_service.send_command(command='configure terminal', expected_str='(config)#')
        self._remove_old_boot_system_config()
        output = self.cli_service.send_command('do show run | include boot')

        is_boot_firmware = False
        firmware_full_name = firmware_obj.get_name() + '.' + firmware_obj.get_extension()

        retries = 5
        while (not is_boot_firmware) and (retries > 0):
            self.cli_service.send_command(command='boot system flash flash:' + firmware_full_name,
                                          expected_str='(config)#')
            self.cli_service.send_command(command='config-reg 0x2102', expected_str='(config)#')

            output = self.cli_service.send_command('do show run | include boot')

            retries -= 1
            is_boot_firmware = output.find(firmware_full_name) != -1

        if not is_boot_firmware:
            raise Exception('Cisco ASA', "Can't add firmware '" + firmware_full_name + "' for boot!")

        self.cli_service.send_command(command='exit')
        output = self.cli_service.send_command(command='copy run start',
                                               expected_map={'\?': lambda session: session.send_line('')})

        self.state_operations.reload()
        output_version = self.cli_service.send_command(command='show version | include image file')

        is_firmware_installed = output_version.find(firmware_full_name)
        if is_firmware_installed != -1:
            return 'Update firmware completed successfully!'
        else:
            raise Exception('Cisco ASA', 'Update firmware failed!')

    def _get_resource_attribute(self, resource_full_path, attribute_name):
        """Get resource attribute by provided attribute_name

        :param resource_full_path: resource name or full name
        :param attribute_name: name of the attribute
        :return: attribute value
        :rtype: string
        """

        try:
            result = self.api.GetAttributeValue(resource_full_path, attribute_name).Value
        except Exception as e:
            raise Exception(e.message)
        return result

    def _remove_old_boot_system_config(self):
        """Clear boot system parameters in current configuration
        """

        data = self.cli_service.send_command('do show run | include boot')
        start_marker_str = 'boot-start-marker'
        index_begin = data.find(start_marker_str)
        index_end = data.find('boot-end-marker')

        if index_begin == -1 or index_end == -1:
            return

        data = data[index_begin + len(start_marker_str):index_end]
        data_list = data.split('\n')

        for line in data_list:
            if line.find('boot system') != -1:
                self.cli_service.send_command(command='no ' + line, expected_str='(config)#')

    def _get_free_memory_size(self, partition):
        """Get available memory size on provided partition

        :param partition: file system
        :return: size of free memory in bytes
        """

        cmd = 'dir {0}:'.format(partition)
        output = self.cli_service.send_command(command=cmd, retries=100)

        find_str = 'bytes total ('
        position = output.find(find_str)
        if position != -1:
            size_str = output[(position + len(find_str)):]

            size_match = re.match(r'[0-9]*', size_str)
            if size_match:
                return int(size_match.group())
            else:
                return -1
        else:
            return -1
