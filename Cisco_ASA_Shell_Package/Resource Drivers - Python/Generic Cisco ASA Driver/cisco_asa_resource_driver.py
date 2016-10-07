#!/usr/bin/python
# -*- coding: utf-8 -*-


from cloudshell.firewall.cisco.asa.autoload.cisco_asa_snmp_autoload import CiscoASASNMPAutoload as Autoload
from cloudshell.firewall.cisco.asa.cisco_asa_run_command_operations import CiscoASARunCommandOperations as RunCommandOperations
from cloudshell.firewall.cisco.asa.cisco_asa_state_operations import CiscoASAStateOperations as StateOperations
from cloudshell.firewall.cisco.asa.cisco_asa_firmware_operations import CiscoASAFirmwareOperations as FirmwareOperations
from cloudshell.firewall.cisco.asa.cisco_asa_configuration_operations import CiscoASAConfigurationOperations as ConfigurationOperations

from cloudshell.firewall.generic_bootstrap import FirewallGenericBootstrap as Bootstrap
from cloudshell.firewall.firewall_resource_driver_interface import FirewallResourceDriverInterface
from cloudshell.shell.core.resource_driver_interface import ResourceDriverInterface

import cloudshell.firewall.cisco.asa.cisco_asa_configuration as driver_config

from cloudshell.shell.core.context_utils import ContextFromArgsMeta

SPLITTER = "-"*60


class CiscoASAResourceDriver(ResourceDriverInterface, FirewallResourceDriverInterface):
    __metaclass__ = ContextFromArgsMeta

    def __init__(self, config=None, autoload=None, run_command_operations=None, firmware_operations=None):
        super(CiscoASAResourceDriver, self).__init__()
        self.run_command_operations = run_command_operations
        self.firmware_operations = firmware_operations
        self.autoload = autoload
        bootstrap = Bootstrap()
        bootstrap.add_config(driver_config)
        if config:
            bootstrap.add_config(config)
        bootstrap.initialize()

    @property
    def _firmware_operations(self):
        return self.firmware_operations or FirmwareOperations()

    @property
    def _autoload(self):
        return self.autoload or Autoload()

    @property
    def _run_command_operations(self):
        return self.run_command_operations or RunCommandOperations()

    @property
    def _configuration_operations(self):
        return ConfigurationOperations()

    @property
    def _state_operations(self):
        return StateOperations()

    def initialize(self, context):
        pass

    def cleanup(self):
        pass

    def ApplyConnectivityChanges(self, context, request):
        pass

    def get_inventory(self, context):
        """ Get device structure with all standard attributes

        :return: AutoLoadDetails object
        """

        return self._autoload.discover()

    def run_custom_command(self, context, custom_command):
        """ Send custom command

        :param custom_command: command
        :return: command execution output
        """

        self._run_command_operations.logger.info("{splitter}\nRun method 'Send Custom Command' with parameters:\n"
                                                 "command = {command}\n{splitter}".format(splitter=SPLITTER,
                                                                                           command=custom_command))
        return self._run_command_operations.run_custom_command(custom_command)

    def run_custom_config_command(self, context, custom_command):
        """ Send custom command in configuration mode

        :param custom_command: command
        :return: command execution output
        """

        self._run_command_operations.logger.info("{splitter}\nRun method 'Send Custom Config Command' with parameters:"
                                                 "\ncommand = {command}\n{splitter}".format(splitter=SPLITTER,
                                                                                            command=custom_command))
        return self._run_command_operations.run_custom_config_command(custom_command)

    def send_custom_command(self, context, custom_command):
        """ Send custom command

        :param custom_command: command
        :return: command execution output
        """

        self._run_command_operations.logger.info("{splitter}\nRun method 'Send Custom Command' with parameters:\n"
                                                 "command = {command}\n{splitter}".format(splitter=SPLITTER,
                                                                                          command=custom_command))
        return self._run_command_operations.run_custom_command(custom_command)

    def send_custom_config_command(self, context, custom_command):
        """ Send custom command in configuration mode

        :param custom_command: command
        :return: command execution output
        """

        self._run_command_operations.logger.info("{splitter}\nRun method 'Send Custom Config Command' with parameters:"
                                                 "\ncommand = {command}\n{splitter}".format(splitter=SPLITTER,
                                                                                            command=custom_command))
        return self._run_command_operations.run_custom_config_command(custom_command)

    def load_firmware(self, context, path):
        """Upload and updates firmware on the resource

        :param path: full path to firmware file, i.e.tftp://10.10.10.1/firmware.bin
        :return: result
        """

        self._firmware_operations.logger.info("{splitter}\nRun method 'Load Firmware' with parameters:\n"
                                              "path = {path}\n"
                                              "{splitter}".format(splitter=SPLITTER,
                                                                  path=path))
        return self._firmware_operations.load_firmware(path)

    def save(self, context, folder_path, configuration_type="running"):
        """Save selected file to the provided destination

        :param configuration_type: source file, which will be saved
        :param folder_path: destination path where file will be saved
        :return saved configuration file name
        """

        if not configuration_type:
            configuration_type = "running"
        self._configuration_operations.logger.info("{splitter}\nRun method 'Save' with parameters:\n"
                                                   "configuration_type = {configuration_type},\n"
                                                   "folder_path = {folder_path},\n"
                                                   "{splitter}".format(splitter=SPLITTER,
                                                                       folder_path=folder_path,
                                                                       configuration_type=configuration_type))
        return self._configuration_operations.save(folder_path=folder_path, configuration_type=configuration_type)

    def restore(self, context, path, configuration_type="running", restore_method="override"):
        """ Restore selected file to the provided destination

        :param path: source config file
        :param configuration_type: running or startup configs
        :param restore_method: append or override methods
        """

        if not configuration_type:
            configuration_type = 'running'

        if not restore_method:
            restore_method = 'override'

        self._configuration_operations.logger.info("{splitter}\nRun method 'Restore' with parameters:"
                                                   "path = {path},\n"
                                                   "config_type = {config_type},\n"
                                                   "restore_method = {restore_method}\n"
                                                   "{splitter}".format(splitter=SPLITTER,
                                                                       path=path,
                                                                       config_type=configuration_type,
                                                                       restore_method=restore_method))
        return self._configuration_operations.restore(path, configuration_type, restore_method)

    def orchestration_save(self, context, mode='shallow', custom_params=None):

        if not mode:
            mode = 'shallow'

        self._configuration_operations.logger.info("{splitter}\nOrchestration save started".format(splitter=SPLITTER))

        response = self._configuration_operations.orchestration_save(mode=mode, custom_params=custom_params)
        self._configuration_operations.logger.info("Orchestration save completed\n{splitter}".format(splitter=SPLITTER))
        return response

    def orchestration_restore(self, context, saved_artifact_info, custom_params=None):
        self._configuration_operations.logger.info("{splitter}\nOrchestration restore started".format(splitter=SPLITTER))
        self._configuration_operations.orchestration_restore(saved_artifact_info=saved_artifact_info,
                                                             custom_params=custom_params)

        self._configuration_operations.logger.info("Orchestration restore completed\n{splitter}".format(splitter=SPLITTER))

    def health_check(self, context):
        """ Performs device health check """

        return self._state_operations.health_check()

    def shutdown(self, context):
        """ Shutdown device """

        pass
