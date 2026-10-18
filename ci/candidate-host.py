#!/usr/bin/env python3
"""Trusted CI metadata selects one fixed public native Python repository."""
import json
import os
from pathlib import Path
import re

def candidate_requirement(directory):
    path=Path(directory)/'contract.json'
    if not path.is_file():return None
    entry=json.loads(path.read_text())['clients']['python']
    if 'candidate_ref' not in entry:return None
    ref=entry['candidate_ref']
    if entry.get('repository')!='licensebox/python' or not isinstance(ref,str) or not re.fullmatch(r'[0-9a-f]{40}',ref):
        raise ValueError('invalid fixed-repository Python candidate pin')
    return 'licensebox @ git+https://github.com/licensebox/python.git@'+ref

if __name__=='__main__':
    directory=os.environ.get('LICENSEBOX_PROTOCOL_DIR')
    if not directory and os.environ.get('GITHUB_WORKSPACE'):directory=str(Path(os.environ['GITHUB_WORKSPACE'])/'protocol')
    result=candidate_requirement(directory) if directory else None
    if result:print(result)
