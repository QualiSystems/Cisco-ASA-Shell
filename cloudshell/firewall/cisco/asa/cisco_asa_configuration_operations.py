#!/usr/bin/python
# -*- coding: utf-8 -*-

import inject
import re
import time

from collections import OrderedDict

from cloudshell.configuration.cloudshell_cli_binding_keys import CLI_SERVICE, SESSION
from cloudshell.configuration.cloudshell_shell_core_binding_keys import LOGGER, API
from cloudshell.firewall.networking_utils import validateIP
from cloudshell.firewall.operations.configuration_operations import ConfigurationOperations
from cloudshell.shell.core.config_utils import override_attributes_from_config
from cloudshell.shell.core.context_utils import get_resource_name


def _get_time_stamp():
    return time.strftime("%d%m%y-%H%M%S", time.localtime())


class CiscoASAConfigurationOperations(ConfigurationOperations):
    SESSION_WAIT_TIMEOUT = 600
    DEFAULT_PROMPT = r'[>$#]\s*$'

    def __init__(self, cli_service=None, logger=None, api=None, resource_name=None):
        self._cli_service = cli_service
        self._logger = logger
        self._api = api
        overridden_config = override_attributes_from_config(CiscoASAConfigurationOperations)
        self._session_wait_timeout = overridden_config.SESSION_WAIT_TIMEOUT
        self._default_prompt = overridden_config.DEFAULT_PROMPT
        try:
            self._resource_name = resource_name
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

    @property
    def resource_name(self):
        if self._resource_name is None:
            try:
                self._resource_name = get_resource_name()
            except:
                raise Exception(self.__class__.__name__, 'Failed to get resource name.')
        return self._resource_name

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
            self.cli_service.send_command(command='reload', expected_map=expected_map, timeout=3)
        except Exception as e:
            self.logger.info('Session type is \'{}\', closing session...'.format(self.session.session_type))

        if self.session.session_type.lower() != 'console':
            self._wait_for_session_restore(self.session)

    def _get_resource_attribute(self, resource_full_path, attribute_name):
        """Get resource attribute by provided attribute_name

        :param resource_full_path: resource name or full name
        :param attribute_name: name of the attribute

        :return: attribute value
        """

        try:
            result = self.api.GetAttributeValue(resource_full_path, attribute_name).Value
        except Exception as e:
            raise Exception(e.message)
        return result

    def save(self, folder_path, configuration_type):
        """Backup 'startup-config' or 'running-config' from device to provided file_system [ftp|tftp]
        Also possible to backup config to localhost

        :param folder_path:  tftp/ftp server where file be saved
        :param configuration_type: what file to backup

        :return: status message / exception
        """

        if configuration_type == '':
            configuration_type = 'running-config'
        if '-config' not in configuration_type:
            configuration_type = configuration_type.lower() + '-config'
        if ('startup' not in configuration_type) and ('running' not in configuration_type):
            raise Exception('Cisco ASA', "Source filename must be 'startup' or 'running'!")

        folder_path = self.get_path(folder_path)

        system_name = re.sub('\s+', '_', self.resource_name)
        if len(system_name) > 23:
            system_name = system_name[:23]

        destination_filename = '{0}-{1}-{2}'.format(system_name, configuration_type.replace('-config', ''),
                                                    _get_time_stamp())
        self.logger.info('destination filename is {0}'.format(destination_filename))

        if len(folder_path) <= 0:
            folder_path = self._get_resource_attribute(self.resource_name, 'Backup Location')
            if len(folder_path) <= 0:
                raise Exception('Folder path and Backup Location are empty.')

        if folder_path.endswith('/'):
            destination_file = folder_path + destination_filename
        else:
            destination_file = folder_path + '/' + destination_filename

        is_uploaded = self.copy(destination_file=destination_file, source_file=configuration_type)
        if is_uploaded[0] is True:
            self.logger.info('Save configuration completed.')
            return '{0},'.format(destination_filename)
        else:
            self.logger.info('Save configuration failed with errors: {0}'.format(is_uploaded[1]))
            raise Exception(is_uploaded[1])

    def restore(self, path, configuration_type, restore_method):
        """ Restore configuration on device from remote server

        :param path: Full path to configuration file on remote server
        :param configuration_type: Type of configuration to restore. supports running and startup configuration
        :param restore_method: Type of restore method. Supports append and override. By default is override

        :return Successful message or Exception
        """

        if not restore_method:
            restore_method = "override"

        if not re.search(r'append|override', restore_method.lower()):
            raise Exception('Cisco ASA',
                            "Restore method '{}' is wrong! Use 'Append' or 'Override'".format(restore_method))

        if '-config' not in configuration_type:
            configuration_type = configuration_type.lower() + '-config'

        self.logger.info('Restore device configuration from {}'.format(path))

        match_data = re.search(r'startup-config|running-config', configuration_type)
        if not match_data:
            msg = "Configuration type '{}' is wrong, use 'startup-config' or 'running-config'.".format(configuration_type)
            raise Exception('Cisco ASA', msg)

        destination_filename = match_data.group()

        if path == '':
            raise Exception('Cisco ASA', "Source Path is empty.")

        if destination_filename == "startup-config":
            is_uploaded = self.copy(source_file=path, destination_file=destination_filename)
        elif destination_filename == "running-config" and restore_method.lower() == "override":
            if not self._check_replace_command():
                raise Exception('Overriding running-config is not supported for this device.')

            self.configure_replace(source_filename=path)
            is_uploaded = (True, '')
        elif destination_filename == "running-config" and restore_method.lower() == "append":
            is_uploaded = self.copy(source_file=path, destination_file=destination_filename)
            if is_uploaded[0] and self.session.session_type.lower() != 'console':
                self._wait_for_session_restore(self.session)
        else:
            is_uploaded = self.copy(source_file=path, destination_file=destination_filename)

        if not is_uploaded[0]:
            self.logger.error("Cisco ASA. Restore {0} from {1} failed: {2}".format(configuration_type,
                                                                                   path,
                                                                                   is_uploaded[1]))
            raise Exception('Cisco ASA', is_uploaded[1])

        return 'Restore configuration completed.'

    def _check_replace_command(self):
        """
        Checks whether replace command exist on device or not
        For Cisco ASA devices always return True
        """

        return True
