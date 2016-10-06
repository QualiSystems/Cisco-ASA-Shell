#!/usr/bin/python
# -*- coding: utf-8 -*-

import inject
import re
import time

from collections import OrderedDict

from cloudshell.configuration.cloudshell_cli_binding_keys import CLI_SERVICE, SESSION
from cloudshell.configuration.cloudshell_shell_core_binding_keys import LOGGER, API
from cloudshell.firewall.cisco.asa.firmware_data.cisco_asa_firmware_data import CiscoASAFirmwareData
from cloudshell.firewall.networking_utils import validateIP, UrlParser
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
    def session(self):
        return inject.instance(SESSION)

    def copy(self, source_file='', destination_file=''):
        """Copy file from device to tftp or vice versa, as well as copying inside devices filesystem

        :param source_file: source file.
        :param destination_file: destination file.
        :return tuple(True or False, 'Success or Error message')
        """

        host = None
        expected_map = OrderedDict()

        if '://' in source_file:
            source_file_data_list = re.sub(r'/+', '/', source_file).split('/')
            host = source_file_data_list[1]
            expected_map[r'[^/]{}'.format(source_file_data_list[-1])] = lambda session: session.send_line('')
            expected_map[r'[^/]{}'.format(destination_file)] = lambda session: session.send_line('')
        elif '://' in destination_file:
            destination_file_data_list = re.sub(r'/+', '/', destination_file).split('/')
            host = destination_file_data_list[1]
            expected_map[r'{}[^/]'.format(destination_file_data_list[-1])] = lambda session: session.send_line('')
            expected_map[r'{}[^/]'.format(source_file)] = lambda session: session.send_line('')
        elif "flash:" in source_file:
            expected_map[r'{}[^/]'.format(source_file.split(":")[-1])] = lambda session: session.send_line('')
            expected_map[r'{}[^/]'.format(destination_file)] = lambda session: session.send_line('')
        elif "flash:" in destination_file:
            expected_map[r'{}[^/]'.format(source_file)] = lambda session: session.send_line('')
            expected_map[r'{}[^/]'.format(destination_file.split(":")[-1])] = lambda session: session.send_line('')
        else:
            expected_map[r'{}[^/]'.format(source_file)] = lambda session: session.send_line('')
            expected_map[r'{}[^/]'.format(destination_file)] = lambda session: session.send_line('')

        if host and not validateIP(host):
            raise Exception('Cisco ASA', 'Copy method: \'{}\' is not valid remote ip.'.format(host))

        copy_command_str = 'copy /noconfirm {0} {1}'.format(source_file, destination_file)

        if host:
            expected_map[r"{}[^/]".format(host)] = lambda session: session.send_line('')

        expected_map[r'\[confirm\]'] = lambda session: session.send_line('')
        expected_map[r'\(y/n\)'] = lambda session: session.send_line('y')
        expected_map[r'\([Yy]es/[Nn]o\)'] = lambda session: session.send_line('yes')
        expected_map[r'\?'] = lambda session: session.send_line('')
        expected_map[r'bytes'] = lambda session: session.send_line('')

        error_map = OrderedDict()
        error_map[r"Invalid input detected"] = "Invalid input detected"
        error_map[r'FAIL|[Ff]ail|ERROR|[Ee]rror'] = "Copy command failed"

        try:
            self.session.hardware_expect(data_str=copy_command_str,
                                         expect_map=expected_map,
                                         error_map=error_map,
                                         re_string="Previous instance shut down|{}".format(self._default_prompt))
            return True, ""
        except Exception, err:
            if "/noconfirm" in copy_command_str and "Invalid input detected" in err.args[1]:

                self.logger.debug("Copy command doesn't support /noconfirm key."
                                  "Try to run copy command without /noconfirm key")

                copy_command_str = 'copy {0} {1}'.format(source_file, destination_file)
                try:
                    self.session.hardware_expect(data_str=copy_command_str,
                                                 expect_map=expected_map,
                                                 error_map=error_map,
                                                 re_string="Previous instance shut down|{}".format(self._default_prompt))
                    return True, ""
                except Exception, err:
                    return False, err.args
            else:
                return False, err.args

    def _wait_for_session_restore(self, session):
        self.logger.debug('Waiting session restore')
        waiting_reboot_time = time.time()
        while True:
            try:
                if time.time() - waiting_reboot_time > self._session_wait_timeout:
                    raise Exception(self.__class__.__name__,
                                    "Session doesn't closed in {} sec as expected".format(self._session_wait_timeout))
                session.send_line('')
                time.sleep(1)
            except:
                self.logger.debug('Session disconnected')
                break
        reboot_time = time.time()
        while True:
            if time.time() - reboot_time > self._session_wait_timeout:
                self.cli_service.destroy_threaded_session(session=session)
                raise Exception(self.__class__.__name__,
                                'Session cannot connect after {} sec.'.format(self._session_wait_timeout))
            try:
                self.logger.debug('Reconnect retry')
                session.connect(re_string=self._default_prompt)
                self.logger.debug('Session connected')
                break
            except:
                time.sleep(5)

    def reload(self):
        """ Reload device """

        expected_map = {'[\[\(][Yy]es/[Nn]o[\)\]]|\[confirm\]': lambda session: session.send_line('yes'),
                        '\(y\/n\)|continue': lambda session: session.send_line('y'),
                        'reload': lambda session: session.send_line(''),
                        '[\[\(][Yy]/[Nn][\)\]]': lambda session: session.send_line('y')
                        }
        try:
            self.logger.info("Send 'reload' to device...")
            self.cli_service.send_command(command='reload', expected_map=expected_map, timeout=3)
        except Exception as e:
            self.logger.info('Session type is \'{}\', closing session...'.format(self.session.session_type))

        if self.session.session_type.lower() != 'console':
            self._wait_for_session_restore(self.session)

    def load_firmware(self, path, vrf_management_name=None):
        """Update firmware version on device by loading provided image, performs following steps:
            1. Copy bin file from remote tftp server.
            2. Clear in run config boot system section.
            3. Set downloaded bin file as boot file and then reboot device.
            4. Check if firmware was successfully installed.
        :param path: full path to firmware file on ftp/tftp location
        :param vrf_management_name: VRF Name
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

        is_downloaded = self.copy(source_file=path, destination_file='flash:/{}'.format(file_name))

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

        self.reload()
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
