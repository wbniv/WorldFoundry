"""Compatibility adapters; device work always goes through one typed job."""
import argparse
import json
from pathlib import Path
from .client import Client

ROOT=Path(__file__).resolve().parents[2]


def device_id(client,selector):
    devices=client.call('devices')
    matches=[d['id'] for d in devices if selector in {d['id'],d['serial'],d.get('endpoint'),d.get('endpoint','').rsplit(':',1)[0]}
             or (selector and d['serial'] in selector)]
    if not selector:
        if len(devices)==1:return devices[0]['id']
        raise ValueError('Multiple Chromecasts registered: specify --serial or DEVICE')
    if len(matches)!=1:
        raise ValueError('Selector does not identify one registered Chromecast')
    return matches[0]


def profile(argv=None,jellyfish=False):
    ap=argparse.ArgumentParser(description='Compatibility alias for task chromecast:profile; no direct ADB')
    ap.add_argument('--serial',default='');ap.add_argument('--apk',required=True);ap.add_argument('--out',required=True)
    ap.add_argument('--runs',type=int,default=1 if jellyfish else 3)
    ap.add_argument('--menu-index',type=int,default=3 if jellyfish else None)
    ap.add_argument('--warmup',type=float,default=15 if jellyfish else 30)
    ap.add_argument('--scenario',choices=['all','swarm','plants'],default='swarm' if jellyfish else 'all')
    ap.add_argument('--resume',action='store_true')
    a=ap.parse_args(argv);c=Client();devices=c.call('devices')
    from .workflows import SCENES
    if a.menu_index is not None and not 0<=a.menu_index<len(SCENES):ap.error('Menu index out of range')
    # Resume never reuses old device ownership or silently skips measurements; submit a new immutable job.
    req={'workflow':'profile','device':device_id(c,a.serial),'app':'aquarium','apk':a.apk,
         'runs':a.runs,'warmup':a.warmup,'trace':a.scenario}
    if a.menu_index is not None:req['scene']=SCENES[a.menu_index]
    job=c.submit(req);print('Replacement: task chromecast:profile; job '+job['id'],flush=True)
    result=c.watch(job['id']);c.evidence(job['id'],a.out);return result


def selector_check(argv=None):
    ap=argparse.ArgumentParser(description='Manifest-driven selector check through coordinator')
    ap.add_argument('--serial',required=True);ap.add_argument('--apk',required=True);ap.add_argument('--out',required=True)
    a=ap.parse_args(argv);c=Client()
    job=c.submit({'workflow':'check','device':device_id(c,a.serial),'app':'aquarium','apk':a.apk,'validator':'menu-back'})
    result=c.watch(job['id']);c.evidence(job['id'],a.out);return result


def planted(argv=None):
    ap=argparse.ArgumentParser(description='One owned variant benchmark plus restoration')
    ap.add_argument('--variants-dir',type=Path,required=True);ap.add_argument('--restore-apk',required=True);ap.add_argument('--out',required=True)
    ap.add_argument('--variants',nargs='+',default=['baseline','density','detailed']);ap.add_argument('--cpu-variants',nargs='+',default=['baseline','density','detailed'])
    ap.add_argument('--runs',type=int,default=3);ap.add_argument('--serial',default='')
    a=ap.parse_args(argv);c=Client()
    variants=[{'label':label,'apk':str(a.variants_dir/(label+'.apk'))} for label in a.variants]
    variants += [{'label':label+'-cpu','apk':str(a.variants_dir/(label+'-cpu.apk')),'runs':1,'warmup':30} for label in a.cpu_variants]
    req={'workflow':'variant-benchmark','device':device_id(c,a.serial),'app':'aquarium','scene':'planted-tank',
         'apk':a.restore_apk,'restore_apk':a.restore_apk,'variants':variants,'trace':'plants','warmup':30,'runs':a.runs}
    job=c.submit(req);result=c.watch(job['id']);c.evidence(job['id'],a.out);return result


def android(argv=None):
    ap=argparse.ArgumentParser(description='Registered Chromecast compatibility route')
    ap.add_argument('--serial',required=True);ap.add_argument('--app',required=True);ap.add_argument('--apk',required=True)
    ap.add_argument('--seconds',type=float,default=20);ap.add_argument('--poke',type=int,default=0);ap.add_argument('--resume',type=int,default=0)
    a=ap.parse_args(argv);c=Client()
    req={'workflow':'check','device':device_id(c,a.serial),'app':a.app,'apk':a.apk,'duration':a.seconds}
    if a.poke or a.resume:req['validator']='poke-resume'
    job=c.submit(req);return c.watch(job['id'])
