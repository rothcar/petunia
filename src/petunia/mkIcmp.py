"""mkIcmp.py

Iteratively generate the allowed ICMP fields.

The full list is at
https://www.iana.org/assignments/icmp-parameters/icmp-parameters.xhtml
but here we enumerate the ones that iptables supports.

See also
/usr/include/linux/uapi/linux/icmp.h

This script assumes we can nuke the FORWARD table.
"""

import subprocess
import sys
import re

import logging

ALIAS_RE = re.compile("^([a-z-]+) [(](.*)[)]$")

logging.basicConfig()
logger = logging.getLogger("icmp")
logger.setLevel(logging.DEBUG)

logger.info("getting supported ICMP types and sub-types")
buf = subprocess.check_output(('iptables', '-p', 'icmp', '-h',),
                              universal_newlines=True)
p = buf.find("Valid ICMP Types:\n")
buf = buf[p+18:]

def extractType(type_):
    """Get an ICMP type value from IPTABLES"""

    cmd = ('iptables', '-F', 'FORWARD',)
    subprocess.check_call(cmd)

    cmd = ('iptables', '-A', 'FORWARD',
           '-p', 'icmp', '--icmp-type', type_,)
    subprocess.check_call(cmd)

    cmd = ('iptables', '-nL', 'FORWARD',)
    buf = subprocess.check_output(cmd,
                                  universal_newlines=True)
    p = buf.find('icmptype ')
    q = buf.find("\n", p)
    code = buf[p+9:q]
    return int(code, 10)

def extractCode(code_):
    """Get an ICMP type and code value from IPTABLES"""

    cmd = ('iptables', '-F', 'FORWARD',)
    subprocess.check_call(cmd)

    cmd = ('iptables', '-A', 'FORWARD',
           '-p', 'icmp', '--icmp-type', code_,)
    subprocess.check_call(cmd)

    cmd = ('iptables', '-nL', 'FORWARD',)
    buf = subprocess.check_output(cmd,
                                  universal_newlines=True)

    p = buf.find('icmptype ')
    q = buf.find(" ", p+9)
    type_ = int(buf[p+9:q], 10)

    p = buf.find("code ", q)
    q = buf.find("\n", p)
    code = int(buf[p+5:q], 10)

    return type_, code

typeByName = {}
nameByType = {}
codeTypeByName = {}

curTypeName = curTypeVal = None
for line in buf.strip().splitlines(False):
    if not line.startswith(' '):
        m = ALIAS_RE.match(line)
        if m is not None:
            curTypeName = m.group(1)
            alias = m.group(2)
            logger.info("found type %s (alias %s)", curTypeName, alias)
        else:
            curTypeName = line
            alias = None
            logger.info("found type %s", curTypeName)
        n = extractType(curTypeName)
        logger.info("found code %d for %s", n, curTypeName)
        typeByName[curTypeName] = n
        if alias is not None:
            typeByName[alias] = n
        curTypeVal = n
    else:
        if curTypeName is None:
            raise ValueError("found code %s for missing type", line)
        codeName = line.lstrip()
        logger.info("found code %s for type %s", codeName, curTypeName)
        t, codeVal = extractCode(codeName)
        if t != curTypeVal:
            raise ValueError("invalid type %d for %s (expected %d)"
                             % (t, codeName, curTypeName,))
        logger.info("found type %d, code %d for %s", t, codeVal, codeName)
        codeTypeByName[codeName] = (t, codeVal,)

logger.info("generating Python output")

sys.stdout.write("# icmp.py\n")
sys.stdout.write("# generated by %s\n" % sys.argv[0])
sys.stdout.write("ICMP_TYPE = {}\n")
sys.stdout.write("ICMP_TYPE_CODE = {}\n")

types = []
for typeName, typeVal in typeByName.items():
    types.append((typeVal, typeName,))
types.sort()

codes = []
for codeName, rec in codeTypeByName.items():
    typeVal, codeVal = rec
    codes.append((typeVal, codeVal, codeName,))
codes.sort()

while types and codes:
    if types[0][0] <= codes[0][0]:
        typeVal, typeName = types.pop(0)
        sys.stdout.write("ICMP_TYPE[\"%s\"] = %d\n" % (typeName, typeVal,))
    else:
        typeVal, codeVal, codeName = codes.pop(0)
        sys.stdout.write("ICMP_TYPE_CODE[\"%s\"] = (%d, %d,)\n"
                         % (codeName, typeVal, codeVal,))

for typeVal, typeName in types:
    sys.stdout.write("ICMP_TYPE[\"%s\"] = %d\n" % (typeName, typeVal,))

for typeVal, codeVal, codeName in codes:
    sys.stdout.write("ICMP_TYPE_CODE[\"%s\"] = (%d, %d,)\n"
                     % (codeName, typeVal, codeVal,))

sys.exit(0)
