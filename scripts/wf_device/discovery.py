"""Legacy Cast rediscovery matches a registered UDN, never the first model match."""
import ipaddress
import urllib.request
import xml.etree.ElementTree as ET


def candidates(address,span=24):
    ip=ipaddress.IPv4Address(address)
    prefix=str(ip).rsplit('.',1)[0];last=int(str(ip).rsplit('.',1)[1])
    yield str(ip)
    for n in range(last+1,min(255,last+span+1)):yield prefix+'.'+str(n)
    for n in range(last-1,max(0,last-span-1),-1):yield prefix+'.'+str(n)


def cast_udn(host):
    # Discovery performs read-only HTTP requests from the service identity.
    with urllib.request.urlopen('http://'+host+':8008/ssdp/device-desc.xml',timeout=.35) as response:
        data=response.read(65536)
    root=ET.fromstring(data)
    return next((e.text.removeprefix('uuid:') for e in root.iter() if e.tag.rsplit('}',1)[-1]=='UDN' and e.text),None)


def rediscover(address,expected_udn,fetch=cast_udn,guard=lambda:None):
    for host in candidates(address):
        guard()
        try:
            if fetch(host)==expected_udn:return host
        except (OSError,ValueError,ET.ParseError):pass
    raise RuntimeError('Registered Cast identity not found near last address; supply a verified new discovery hint')
