#!/usr/bin/python
# -*- coding: utf-8 -*-

import inject

from cloudshell.firewall.generic_bootstrap import FirewallGenericBootstrap
from cloudshell.firewall.firewall_resource_driver_interface import FirewallResourceDriverInterface
from cloudshell.shell.core.context_utils import context_from_args
from cloudshell.shell.core.resource_driver_interface import ResourceDriverInterface

import cloudshell.firewall.cisco.asa.cisco_asa_configuration as driver_config

SPLITTER = "-"*60


class CiscoASAResourceDriver(ResourceDriverInterface, FirewallResourceDriverInterface):
    def __init__(self):
        bootstrap = FirewallGenericBootstrap()
        bootstrap.add_config(driver_config)
        bootstrap.initialize()

    @context_from_args
    def initialize(self, context):
        """Initialize method

        :type context: cloudshell.shell.core.context.driver_context.InitCommandContext
        """

        return 'Finished initializing'

    def cleanup(self):
        pass

    @context_from_args
    def ApplyConnectivityChanges(self, context, request):
        pass

    @context_from_args
    def restore(self, context, path, config_type, restore_method):
        """Restore selected file to the provided destination

        :param path: source config file
        :param config_type: running or startup configs
        :param restore_method: append or override methods
        """

        configuration_operations = inject.instance('configuration_operations')
        configuration_operations.logger.info("{splitter}\nRun method 'Restore' with parameters:"
                                             "path = {path},\n"
                                             "config_type = {config_type},\n"
                                             "restore_method = {restore_method}\n"
                                             "{splitter}".format(splitter=SPLITTER,
                                                                 path=path,
                                                                 config_type=config_type,
                                                                 restore_method=restore_method))
        response = configuration_operations.restore_configuration(source_file=path, restore_method=restore_method,
                                                                  config_type=config_type)
        configuration_operations.logger.info('Restore completed')
        configuration_operations.logger.info(response)

    @context_from_args
    def save(self, context, destination_host, source_filename):
        """Save selected file to the provided destination

        :param source_filename: source file, which will be saved
        :param destination_host: destination path where file will be saved
        """

        configuration_operations = inject.instance('configuration_operations')
        configuration_operations.logger.info("{splitter}\nRun method 'Save' with parameters:\n"
                                             "destination_host = {destination_host},\n"
                                             "source_filename = {source_filename}\n"
                                             "{splitter}".format(splitter=SPLITTER,
                                                                 destination_host=destination_host,
                                                                 source_filename=source_filename))
        response = configuration_operations.save_configuration(destination_host, source_filename)
        configuration_operations.logger.info('Save completed')
        return response

    @context_from_args
    def get_inventory(self, context):
        """Return device structure with all standard attributes

        :return: response
        :rtype: string
        """

        autoload_operations = inject.instance("autoload_operations")
        response = autoload_operations.discover()
        autoload_operations.logger.info('Autoload completed')
        return response

    @context_from_args
    def update_firmware(self, context, remote_host, file_path):
        """Upload and updates firmware on the resource

        :param remote_host: path to tftp:// server where firmware file is stored
        :param file_path: firmware file name
        :return: result
        :rtype: string
        """

        firmware_operations = inject.instance("firmware_operations")
        firmware_operations.logger.info("{splitter}\nRun method 'Load Firmware' with parameters:\n"
                                        "remote_host = {remote_host},\n"
                                        "file_path = {file_path}\n"
                                        "{splitter}".format(splitter=SPLITTER,
                                                            remote_host=remote_host,
                                                            file_path=file_path))
        response = firmware_operations.update_firmware(remote_host=remote_host, file_path=file_path)
        firmware_operations.logger.info(response)

    @context_from_args
    def send_custom_command(self, context, command):
        """Send custom command

        :return: result
        :rtype: string
        """

        send_command_operations = inject.instance("send_command_operations")
        send_command_operations.logger.info("{splitter}\nRun method 'Send Custom Command' with parameters:\n"
                                            "command = {command}\n{splitter}".format(splitter=SPLITTER, command=command))
        response = send_command_operations.send_command(command=command)
        return response

    @context_from_args
    def send_custom_config_command(self, context, command):
        """Send custom command in configuration mode

        :return: result
        :rtype: string
        """

        send_command_operations = inject.instance("send_command_operations")
        send_command_operations.logger.info("{splitter}\nRun method 'Send Custom Config Command' with parameters:\n"
                                            "command = {command}\n{splitter}".format(splitter=SPLITTER, command=command))
        result_str = send_command_operations.send_config_command(command=command)
        return result_str

    @context_from_args
    def shutdown(self, context):
        pass
