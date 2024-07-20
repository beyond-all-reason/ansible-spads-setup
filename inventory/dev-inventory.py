#!/usr/bin/env python3

# This script generates Ansible dev inventory from Incus containers named spads-testN

import grp
import json
import os
import os.path
import re
import shutil
import subprocess

def get_container_ip(container):
    for interface, info in container['state']['network'].items():
        if re.match(r'^eth\d+|enp\d+s\d+$', interface) is None:
            continue
        for addr in info['addresses']:
            if addr['family'] == 'inet':
                return addr['address']
    return None

def get_hosts():
    if not os.path.isfile('.incus-integration-on'):
        return {}
    if shutil.which('incus') is None:
        return {}

    containers = json.loads(subprocess.check_output(
        ['incus', 'list', '--format=json', 'status=running', 'spads-test']))

    hosts = {}
    for container in containers:
        m = re.match(r'^spads-test(\d+)$', container['name'])
        if m is None:
            continue
        if ip := get_container_ip(container):
            hosts['test' + m.group(1)] = ip

    return hosts

def main():
    hosts = get_hosts()
    hostvars = {}
    for host, ip in hosts.items():
        hostvars[host] = {
            "ansible_host": ip,
            "ansible_user": "ansible",
            "ansible_ssh_private_key_file": "test.ssh.key"
        }
    print(json.dumps({
        "_meta": {
            "hostvars": hostvars,
        },
        "all": {
            "children": [
                "dev"
            ]
        },
        "dev": {
            "hosts": list(hosts.keys())
        }
    }))

if __name__ == '__main__':
    main()
