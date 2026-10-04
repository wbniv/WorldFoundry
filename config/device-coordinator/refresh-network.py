#!/usr/bin/python3
"""Root-owned address-rule refresh; reads only the protected registry DB."""
import ipaddress
import json
import os
from pathlib import Path
import sqlite3
import subprocess

if os.geteuid()!=0:
    raise SystemExit('Network policy refresh requires root')
config=json.loads(Path('/etc/wf-device-coordinator/devices.json').read_text())
addresses=set()
for device in config['devices']:
    host=device['endpoint'].rsplit(':',1)[0].strip('[]')
    addresses.add(str(ipaddress.ip_address(host)))
    for value in device.get('ipv6_addresses',[]):
        addresses.add(str(ipaddress.ip_address(value)))
db=Path(config['state'])/'coordinator.sqlite3'
if db.exists():
    with sqlite3.connect('file:'+str(db)+'?mode=ro',uri=True) as connection:
        for row in connection.execute('SELECT data FROM devices'):
            device=json.loads(row[0]);host=device['endpoint'].rsplit(':',1)[0].strip('[]')
            addresses.add(str(ipaddress.ip_address(host)))
            for value in device.get('ipv6_addresses',[]):
                addresses.add(str(ipaddress.ip_address(value)))
uids=', '.join(str(int(uid)) for uid in config['allowed_uids'])
v4=', '.join(a for a in sorted(addresses) if ipaddress.ip_address(a).version==4)
v6=', '.join(a for a in sorted(addresses) if ipaddress.ip_address(a).version==6)
# One atomic nft transaction; no broad flush of host rules or unrelated devices.
exists=subprocess.run(['/usr/sbin/nft','list','table','inet','wf_chromecast'],capture_output=True).returncode==0
rules=('delete table inet wf_chromecast\n' if exists else '')+f'''table inet wf_chromecast {{
 set ipv4 {{ type ipv4_addr; elements = {{ {v4} }} }}
 set ipv6 {{ type ipv6_addr; elements = {{ {v6} }} }}
 chain output {{ type filter hook output priority -10; policy accept;
  meta skuid {{ {uids} }} ip daddr @ipv4 reject
  meta skuid {{ {uids} }} ip6 daddr @ipv6 reject
 }}
}}
'''
subprocess.run(['/usr/sbin/nft','-f','-'],input=rules,text=True,check=True)
print('Protected Chromecast addresses:',', '.join(sorted(addresses)))
