from cloudshell.networking.cisco.autoload.cisco_generic_snmp_autoload import CiscoGenericSNMPAutoload


class CiscoASASNMPAutoload(CiscoGenericSNMPAutoload):
    IF_ENTITY = "ifName"
    ENTITY_PHYSICAL = "entPhysicalName"
