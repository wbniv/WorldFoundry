#!/usr/bin/env python3
"""Extract explicitly bound enum fields from an existing compiled OAD.

OAD owns labels/ranges/defaults; bindings select fields and mailbox destinations.
The resulting compact JSON is proposed runtime bridge input, not a shipped API.
"""
import argparse
import json
from pathlib import Path
import struct

HEADER=80
ENTRY=1491

def cstr(b):
    return b.split(b'\0',1)[0].decode('utf-8')

def settings_from_oad(oad,bindings):
    data=Path(oad).read_bytes()
    if len(data)<HEADER or len(data[HEADER:])%ENTRY:
        raise ValueError('Malformed OAD length')
    if data[:4]!=b' DAO':raise ValueError('Invalid OAD magic')
    declared={}
    for start in range(HEADER,len(data),ENTRY):
        e=data[start:start+ENTRY];kind=e[0];name=cstr(e[1:65])
        low,high,default=struct.unpack_from('<iii',e,65)
        labels=cstr(e[79:591]);show=e[591]
        if kind==4 and show==4:
            if name in declared:raise ValueError('Duplicate OAD field')
            choices=labels.split('|')
            if high-low+1!=len(choices) or not low<=default<=high or any(not s for s in choices):
                raise ValueError('Enum labels/range/default mismatch')
            declared[name]=dict(name=name,type='enum',min=low,max=high,default=default,choices=choices)
    if bindings.get('version')!=1:raise ValueError('Unsupported bindings version')
    fields=[];used=set()
    for binding in bindings['fields']:
        name=binding['field'];mailbox=binding['mailbox']
        if name not in declared:raise ValueError('Binding references undeclared enum: '+name)
        if isinstance(mailbox,bool) or not isinstance(mailbox,int) or not 2<=mailbox<=3999:
            raise ValueError('Invalid settings mailbox')
        if mailbox in used:raise ValueError('Duplicate settings mailbox')
        used.add(mailbox);fields.append(dict(declared[name],mailbox=mailbox))
    return dict(version=1,title=bindings['title'],fields=fields)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--oad',type=Path,required=True)
    p.add_argument('--bindings',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();data=settings_from_oad(a.oad,json.loads(a.bindings.read_text()))
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(data,indent=2)+'\n');print(a.out)
