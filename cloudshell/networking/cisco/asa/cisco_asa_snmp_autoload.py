from cloudshell.networking.cisco.autoload.cisco_generic_snmp_autoload import CiscoGenericSNMPAutoload


class CiscoASASNMPAutoload(CiscoGenericSNMPAutoload):
    def __init__(self):
        CiscoGenericSNMPAutoload.__init__(self)
        self.if_entity = "Name"
