#!/usr/bin/python
# -*- coding: utf-8 -*-
from cloudshell.shell.core.context import ResourceCommandContext, ResourceContextDetails, ReservationContextDetails
from cloudshell.firewall.cisco.asa.cisco_asa_resource_driver import CiscoASAResourceDriver
import re


def create_context():
    context = ResourceCommandContext()
    context.resource = ResourceContextDetails()
    context.resource.name = 'Cisco ASA'
    context.reservation = ReservationContextDetails()
    context.reservation.reservation_id = 'test_id'
    context.resource.attributes = {}
    context.resource.attributes['User'] = 'alex'
    context.resource.attributes['Password'] = 'C1sco123'
    context.resource.attributes['Enable Password'] = 'C1sco123'
    context.resource.address = '172.29.168.36'
    # context.resource.address = '172.17.2.101:5000'
    context.resource.attributes['SNMP Version'] = '2'
    context.resource.attributes['SNMP Read Community'] = 'public'
    context.resource.attributes['CLI Connection Type'] = 'Telnet'
    return context

if __name__ == '__main__':
    context = create_context()
    driver = CiscoASAResourceDriver()
    # driver = CiscoIOSResourceDriver()
    print driver.get_inventory(context)
    # print driver.send_custom_command(context, "sh ver")
