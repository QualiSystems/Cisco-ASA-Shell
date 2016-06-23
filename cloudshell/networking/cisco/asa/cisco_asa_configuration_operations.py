from cloudshell.networking.cisco.cisco_configuration_operations import CiscoConfigurationOperations
from cloudshell.networking.cisco.firmware_data.cisco_firmware_data import CiscoFirmwareData


class CiscoASAConfigurationOperations(CiscoConfigurationOperations):
    """   """
    def __init__(self):
        CiscoConfigurationOperations.__init__(self)

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

        firmware_obj = CiscoFirmwareData(file_path)
        if firmware_obj.get_name() is None:
            raise Exception('Cisco ASA', "Invalid firmware name!\n \
                                Firmware file must have: title, extension.\n \
                                Example: isr4400-universalk9.03.10.00.S.153-3.S-ext.SPA.bin\n\n \
                                Current path: " + file_path)

            # if not validateIP(remote_host):
            #     raise Exception('Cisco ASA', "Not valid remote host IP address!")
        free_memory_size = self._get_free_memory_size('boot flash')

        # if size_of_firmware > free_memory_size:
        #    raise Exception('Cisco ISR 4K', "Not enough memory for firmware!")

        is_downloaded = self.copy(source_file=remote_host,
                                  destination_file='flash:/' + file_path, timeout=600, retries=2)

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
        is_reloaded = self.reload()
        output_version = self.cli.send_command(command='show version | include image file')

        is_firmware_installed = output_version.find(firmware_full_name)
        if is_firmware_installed != -1:
            return 'Finished updating firmware!'
        else:
            raise Exception('Cisco ASA', 'Firmware update was unsuccessful!')

    def _check_replace_command(self):
        """
        Checks whether replace command exist on device or not
        For Cisco ASA devices always return True
        """
        return True

    def configure_replace(self, source_filename, timeout=600, vrf=None):
        """Replace config on target device with specified one

        :param source_filename: full path to the file which will replace current running-config
        :param timeout: period of time code will wait for replace to finish
        :param vrf:
        """
        backup = "flash:backup-rc"
        config = "running-config"

        if not source_filename:
            raise Exception('Cisco ASA', "Configure replace method doesn't have source filename!")

        self._logger.warning("Cisco ASA", "Restore method doesn't implemented yet")

        # try:
        #     self.logger.debug("Cisco ASA", "Start backup running-config")
        #     is_backuped = self.copy(source_file=config, destination_file=backup, vrf=vrf)
        #     if not is_backuped[0]:
        #         raise Exception("Check if flash has enough free space")
        #     self.logger.debug("Cisco ASA", "Backup running-config successfully")
        # except Exception, err:
        #     raise Exception("Cisco ASA", "Could not backup running-config: {0}" .format(err))
        #
        # # Clear all running configuration
        # self.cli.send_config_command(command="clear configure all")
        #
        # try:
        #     self.logger.debug("Cisco ASA", "Start reload running-config from {0}" .format(source_filename))
        #     is_uploaded = self.copy(source_file=source_filename, destination_file=config, vrf=vrf)
        #     if not is_uploaded[0]:
        #         raise Exception(is_uploaded[1])
        #     self.logger.debug("Cisco ASA", "Reloading running-config successfully")
        # except Exception, err:
        #     self.logger.error("Cisco ASA", "Restore running-config from backup")
        #     is_restored = self.copy(source_file=backup, destination_file=config, vrf=vrf)
        #     # TODO think about handling restore configuration from backup result
        #     raise Exception("Cisco ASA", "Could reload running-config: {0}".format(err))
