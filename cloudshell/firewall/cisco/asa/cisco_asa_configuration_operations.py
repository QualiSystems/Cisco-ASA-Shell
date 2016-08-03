#!/usr/bin/python
# -*- coding: utf-8 -*-

import inject
import re
import time

from collections import OrderedDict

from cloudshell.configuration.cloudshell_cli_binding_keys import CLI_SERVICE, SESSION
from cloudshell.configuration.cloudshell_shell_core_binding_keys import LOGGER, API
from cloudshell.firewall.networking_utils import validateIP
from cloudshell.firewall.cisco.asa.firmware_data.cisco_asa_firmware_data import CiscoASAFirmwareData
from cloudshell.firewall.operations.interfaces.configuration_operations_interface import \
    ConfigurationOperationsInterface
from cloudshell.firewall.operations.interfaces.firmware_operations_interface import FirmwareOperationsInterface
from cloudshell.shell.core.config_utils import override_attributes_from_config
from cloudshell.shell.core.context_utils import get_resource_name, get_attribute_by_name


def _get_time_stamp():
    return time.strftime("%d%m%y-%H%M%S", time.localtime())


class CiscoASAConfigurationOperations(ConfigurationOperationsInterface, FirmwareOperationsInterface):
    SESSION_WAIT_TIMEOUT = 600
    DEFAULT_PROMPT = r'[>$#]\s*$'

    def __init__(self, cli=None, logger=None, api=None, resource_name=None):
        self._cli = cli
        self._logger = logger
        self._api = api
        overridden_config = override_attributes_from_config(CiscoASAConfigurationOperations)
        self._session_wait_timeout = overridden_config.SESSION_WAIT_TIMEOUT
        self._default_prompt = overridden_config.DEFAULT_PROMPT
        try:
            self.resource_name = resource_name or get_resource_name()
        except Exception:
            raise Exception('CiscoASAHandlerBase', 'ResourceName is empty or None')

    @property
    def logger(self):
        if self._logger:
            logger = self._logger
        else:
            logger = inject.instance(LOGGER)
        return logger

    @property
    def api(self):
        if self._api:
            api = self._api
        else:
            api = inject.instance(API)
        return api

    @property
    def cli(self):
        if self._cli is None:
            self._cli = inject.instance(CLI_SERVICE)
        return self._cli

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
                self.cli.destroy_threaded_session(session=session)
                raise Exception(self.__class__.__name__,
                                'Session cannot connect after {} sec.'.format(self._session_wait_timeout))
            try:
                self.logger.debug('Reconnect retry')
                session.connect(re_string=self._default_prompt)
                self.logger.debug('Session connected')
                break
            except:
                time.sleep(5)

    def configure_replace(self, source_filename):
        """Replace config on target device with specified one

        :param source_filename: full path to the file which will replace current running-config
        """

        backup = "flash:backup-sc"
        config_name = "startup-config"

        if not source_filename:
            raise Exception('Cisco ASA', "Configure replace method doesn't have source filename!")

        self.logger.debug("Start backup process for '{0}' config".format(config_name))
        backup_done = self.copy(source_file=config_name, destination_file=backup)
        if not backup_done[0]:
            raise Exception("Cisco ASA", "Failed to backup {0} config. Check if flash has enough free space"
                            .format(config_name))
        self.logger.debug("Backup completed successfully")

        self.logger.debug("Start reloading {0} from {1}".format(config_name, source_filename))
        is_uploaded = self.copy(source_file=source_filename, destination_file=config_name)
        if not is_uploaded[0]:
            self.logger.debug("Failed to reload {0}: {1}".format(config_name, is_uploaded[1]))
            self.logger.debug("Restore startup-configuration from backup")
            self.copy(source_file=backup, destination_file=config_name)
            raise Exception(is_uploaded[1])
        self.logger.debug("Reloading startup-config successfully")
        self.reload()

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

    def update_firmware(self, remote_host, file_path, size_of_firmware=200000000):
        """Update firmware version on device by loading provided image, performs following steps:

            1. Copy bin file from remote tftp server.
            2. Clear in run config boot system section.
            3. Set downloaded bin file as boot file and then reboot device.
            4. Check if firmware was successfully installed.

        :param remote_host: host with firmware
        :param file_path: relative path on remote host
        :param size_of_firmware: size in bytes
        :return: status / exception
        """

        firmware_obj = CiscoASAFirmwareData(file_path)
        if firmware_obj.get_name() is None:
            raise Exception('Cisco ASA', "Invalid firmware name!\n \
                                Firmware file must have: title, extension.\n \
                                Example: isr4400-universalk9.03.10.00.S.153-3.S-ext.SPA.bin\n\n \
                                Current path: " + file_path)

        free_memory_size = self._get_free_memory_size('boot flash')

        is_downloaded = self.copy(source_file=remote_host, destination_file='flash:/' + file_path)

        if not is_downloaded[0]:
            raise Exception('Cisco ASA', "Failed to download firmware from " + remote_host +
                            file_path + "!\n" + is_downloaded[1])

        self.cli.send_command(command='configure terminal', expected_str='(config)#')
        self._remove_old_boot_system_config()
        output = self.cli.send_command('do show run | include boot')

        is_boot_firmware = False
        firmware_full_name = firmware_obj.get_name() + '.' + firmware_obj.get_extension()

        retries = 5
        while (not is_boot_firmware) and (retries > 0):
            self.cli.send_command(command='boot system flash:' + firmware_full_name, expected_str='(config)#')
            self.cli.send_command(command='config-reg 0x2102', expected_str='(config)#')

            output = self.cli.send_command('do show run | include boot')

            retries -= 1
            is_boot_firmware = output.find(firmware_full_name) != -1

        if not is_boot_firmware:
            raise Exception('Cisco ASA', "Can't add firmware '" + firmware_full_name + "' dor boot!")

        self.cli.send_command(command='exit')
        output = self.cli.send_command(command='copy run start',
                                       expected_map={'\?': lambda session: session.send_line('')})
        self.reload()
        output_version = self.cli.send_command(command='show version | include image file')

        is_firmware_installed = output_version.find(firmware_full_name)
        if is_firmware_installed != -1:
            return 'Finished updating firmware!'
        else:
            raise Exception('Cisco ASA', 'Firmware update was unsuccessful!')

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

    def save_configuration(self, destination_host, source_filename):
        """Backup 'startup-config' or 'running-config' from device to provided file_system [ftp|tftp]
        Also possible to backup config to localhost
        :param destination_host:  tftp/ftp server where file be saved
        :param source_filename: what file to backup
        :return: status message / exception
        """

        if source_filename == '':
            source_filename = 'running-config'
        if '-config' not in source_filename:
            source_filename = source_filename.lower() + '-config'
        if ('startup' not in source_filename) and ('running' not in source_filename):
            raise Exception('Cisco ASA', "Source filename must be 'startup' or 'running'!")

        if not destination_host:
            destination_host = get_attribute_by_name('Backup Location')
            if not destination_host:
                raise Exception('Cisco ASA', "Backup location or path can not be empty")

        system_name = re.sub('\s+', '_', self.resource_name)
        if len(system_name) > 23:
            system_name = system_name[:23]

        destination_filename = '{0}-{1}-{2}'.format(system_name, source_filename.replace('-config', ''),
                                                    _get_time_stamp())
        self.logger.info('destination filename is {0}'.format(destination_filename))

        if len(destination_host) <= 0:
            destination_host = self._get_resource_attribute(self.resource_name, 'Backup Location')
            if len(destination_host) <= 0:
                raise Exception('Folder path and Backup Location are empty.')

        if destination_host.endswith('/'):
            destination_file = destination_host + destination_filename
        else:
            destination_file = destination_host + '/' + destination_filename

        is_uploaded = self.copy(destination_file=destination_file, source_file=source_filename)
        if is_uploaded[0] is True:
            self.logger.info('Save configuration completed.')
            return '{0},'.format(destination_filename)
        else:
            self.logger.info('Save configuration failed with errors: {0}'.format(is_uploaded[1]))
            raise Exception(is_uploaded[1])

    def restore_configuration(self, source_file, config_type, restore_method='override'):
        """Restore configuration on device from provided configuration file
        Restore configuration from local file system or ftp/tftp server into 'running-config' or 'startup-config'.

        :param source_file: relative path to the file on the remote host tftp://server/sourcefile
        :param restore_method: override current config or not
        :return:
        """

        if not re.search(r'append|override', restore_method.lower()):
            raise Exception('Cisco ASA',
                            "Restore method '{}' is wrong! Use 'Append' or 'Override'".format(restore_method))

        if '-config' not in config_type:
            config_type = config_type.lower() + '-config'

        self.logger.info('Restore device configuration from {}'.format(source_file))

        match_data = re.search(r'startup-config|running-config', config_type)
        if not match_data:
            msg = "Configuration type '{}' is wrong, use 'startup-config' or 'running-config'.".format(config_type)
            raise Exception('Cisco ASA', msg)

        destination_filename = match_data.group()

        if source_file == '':
            raise Exception('Cisco ASA', "Source Path is empty.")

        if destination_filename == "startup-config":
            is_uploaded = self.copy(source_file=source_file, destination_file=destination_filename)
        elif destination_filename == "running-config" and restore_method.lower() == "override":
            if not self._check_replace_command():
                raise Exception('Overriding running-config is not supported for this device.')

            self.configure_replace(source_filename=source_file)
            is_uploaded = (True, '')
        elif destination_filename == "running-config" and restore_method.lower() == "append":
            is_uploaded = self.copy(source_file=source_file, destination_file=destination_filename)
            if is_uploaded[0] and self.session.session_type.lower() != 'console':
                self._wait_for_session_restore(self.session)
        else:
            is_uploaded = self.copy(source_file=source_file, destination_file=destination_filename)

        if not is_uploaded[0]:
            self.logger.error("Cisco ASA. Restore {0} from {1} failed: {2}".format(config_type,
                                                                                   source_file,
                                                                                   is_uploaded[1]))
            raise Exception('Cisco ASA', is_uploaded[1])

        return 'Restore configuration completed.'

    def _check_replace_command(self):
        """
        Checks whether replace command exist on device or not
        For Cisco ASA devices always return True
        """

        return True

    def _remove_old_boot_system_config(self):
        """Clear boot system parameters in current configuration
        """

        data = self.cli.send_command('do show run | include boot')
        start_marker_str = 'boot-start-marker'
        index_begin = data.find(start_marker_str)
        index_end = data.find('boot-end-marker')

        if index_begin == -1 or index_end == -1:
            return

        data = data[index_begin + len(start_marker_str):index_end]
        data_list = data.split('\n')

        for line in data_list:
            if line.find('boot system') != -1:
                self.cli.send_command(command='no ' + line, expected_str='(config)#')

    def _get_free_memory_size(self, partition):
        """Get available memory size on provided partition

        :param partition: file system
        :return: size of free memory in bytes
        """

        cmd = 'dir {0}:'.format(partition)
        output = self.cli.send_command(command=cmd, retries=100)

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
