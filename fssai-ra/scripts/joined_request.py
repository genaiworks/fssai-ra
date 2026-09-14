#!/usr/bin/env python3
"""One JSON request against a synthetic store; token is supplied out of band."""
import argparse
import json
import os
import sys

from fssaira.joined_workflow import Workflow

parser = argparse.ArgumentParser()
parser.add_argument('--database', required=True)
args = parser.parse_args()
world = Workflow(args.database)
print(json.dumps(world.dispatch(os.environ.get('FSSAI_DEMO_TOKEN', ''), sys.stdin.read())))
world.close()
