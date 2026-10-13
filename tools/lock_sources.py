#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Refresh provenance from local pinned clones, including uninitialized gitlinks."""
import hashlib, json, pathlib, subprocess
root = pathlib.Path(__file__).resolve().parent.parent
pins = {'darling':('60ba801decee7a00782f74f6be4c8ffb013f79ff','GPL-3.0; mixed submodules'), 'darling-metal':('ae20248dc144beab899e38752f5a530f28a0ea56','MPL-2.0'), 'indium':('8423a7d2f053167030d2bc4a227f96243c740667','0BSD')}
def git(path,*args):
    return subprocess.check_output(['git','-C',str(path),*args],text=True).strip()
def entry(path,url,revision,license):
    if git(path,'rev-parse','HEAD') != revision:
        raise RuntimeError('revision mismatch: '+str(path))
    links=[]
    for line in git(path,'ls-tree','-r','HEAD').splitlines():
        meta,name=line.split('\t',1)
        mode,kind,sha=meta.split()
        if mode=='160000':
            child=path/name
            item={'path':name,'revision':sha,'initialized':(child/'.git').exists()}
            if item['initialized']:
                item['source']=entry(child,git(child,'remote','get-url','origin'),sha,'audit-required')
            links.append(item)
    return {'url':url,'revision':revision,'license':license,'gitlinks':links}
sources=[entry(root/'.work/upstream'/name,'https://github.com/darlinghq/'+name+'.git',sha,lic) for name,(sha,lic) in pins.items()]
header=root/'third_party/json/nlohmann/json.hpp'
manifest={'schema_version':1,'sources':sources,'json':{'version':'3.11.3','license':'MIT','sha256':hashlib.sha256(header.read_bytes()).hexdigest(),'url':'https://raw.githubusercontent.com/nlohmann/json/v3.11.3/single_include/nlohmann/json.hpp'}}
(root/'third_party/sources.lock.json').write_text(json.dumps(manifest,indent=2)+'\n')
