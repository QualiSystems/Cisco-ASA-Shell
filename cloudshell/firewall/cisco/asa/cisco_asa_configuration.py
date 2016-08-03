#!/usr/bin/python
# -*- coding: utf-8 -*-

import re
from cloudshell.firewall.cisco.asa.autoload.cisco_asa_snmp_autoload import CiscoASASNMPAutoload
from cloudshell.firewall.cisco.asa.cisco_asa_configuration_operations import CiscoASAConfigurationOperations
from cloudshell.firewall.cisco.asa.cisco_asa_send_command_operations import CiscoASASendCommandOperations
from cloudshell.shell.core.context_utils import get_decrypted_password_by_attribute_name_wrapper


DEFAULT_PROMPT = r'[>#]\s*$'
ENABLE_PROMPT = r'#\s*$'
CONFIG_MODE_PROMPT = r'\(config.*\)#\s*$'


def send_default_actions(session):
    """Send default commands to configure/clear session outputs

    :return:
    """
    out = ''
    out += enter_enable_mode(session=session)
    out += session.hardware_expect('terminal pager 0', ENABLE_PROMPT)
    out += session.hardware_expect(ENTER_CONFIG_MODE_PROMPT_COMMAND, CONFIG_MODE_PROMPT)
    out += session.hardware_expect('no logging console', CONFIG_MODE_PROMPT)
    out += session.hardware_expect('exit', DEFAULT_PROMPT + '|' + ENABLE_PROMPT)
    return out

ENTER_CONFIG_MODE_PROMPT_COMMAND = 'configure terminal'
EXIT_CONFIG_MODE_PROMPT_COMMAND = 'exit'
DEFAULT_ACTIONS = send_default_actions
SUPPORTED_OS = ["A(daptive)? ?S(ecurity)? ?A(ppliance)?"]


def enter_enable_mode(session):
    session.hardware_expect('enable', re_string=DEFAULT_PROMPT + '|' + ENABLE_PROMPT,
                            expect_map={'[Pp]assword': lambda session: session.send_line(
                                get_decrypted_password_by_attribute_name_wrapper('Enable Password')())})
    result = session.hardware_expect('', re_string=DEFAULT_PROMPT + '|' + ENABLE_PROMPT)
    if not re.search(ENABLE_PROMPT, result):
        raise Exception('enter_enable_mode', 'Enable password is incorrect')

    return result

CONFIGURATION_OPERATIONS_CLASS = CiscoASAConfigurationOperations
FIRMWARE_OPERATIONS_CLASS = CiscoASAConfigurationOperations
AUTOLOAD_OPERATIONS_CLASS = CiscoASASNMPAutoload
SEND_COMMAND_OPERATIONS_CLASS = CiscoASASendCommandOperations
