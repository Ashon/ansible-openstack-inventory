#!/usr/bin/env python

import argparse
import json
import subprocess
import os
import sys
import yaml


def initialize(config):

    os.environ['OS_AUTH_URL'] = config.get('os_auth_url')
    os.environ['OS_USER_DOMAIN_NAME'] = config.get('os_user_domain_name')
    os.environ['OS_REGION_NAME'] = config.get('os_region_name')

    os.environ['OS_USERNAME'] = config.get('os_username')
    os.environ['OS_PASSWORD'] = config.get('os_password')

    os.environ['OS_TENANT_ID'] = config.get('os_tenant_id')
    os.environ['OS_TENANT_NAME'] = config.get('os_tenant_name')


def parse_args():
    parser = argparse.ArgumentParser(description='Openstack Dynamic Inventory')

    arg_group = parser.add_mutually_exclusive_group(required=True)
    arg_group.add_argument('--list', action='store_true')
    arg_group.add_argument('--host')

    return parser.parse_args()


def get_stdout_from_cmd(cmd):
    return subprocess.check_output(cmd.split(' ')).rstrip()


def query_server_list():
    return json.loads(
        get_stdout_from_cmd('openstack server list -f json'))


def query_network_list():
    return json.loads(
        get_stdout_from_cmd('openstack network list -f json'))


def query_server_info(instance_id_or_name):

    cmd = 'openstack server show {instance_id_or_name} {column_arg} -f json'

    columns = [
        'name',
        'key_name',
        'addresses',
        'image'
    ]

    column_arg = ' '.join([
        '-c ' + column for column in columns
    ])

    return json.loads(
        get_stdout_from_cmd(cmd.format(
            instance_id_or_name=instance_id_or_name,
            column_arg=column_arg)))


def get_detail_server_list(openstack_serverlist):

    # slow...

    return [
        query_server_info(instance['ID']) for instance in openstack_serverlist
    ]


def get_ip_from_openstack_addr(openstack_address_str):

    split_table = openstack_address_str.split('=')

    # network_name = split_table[0]
    addresses = split_table[1].split(', ')

    return addresses[-1]


def get_ssh_user_from_os_image(patterns, os_image_name):

    ssh_user = 'root'

    for pattern in patterns.keys():

        if os_image_name.find(pattern) > -1:
            ssh_user = patterns[pattern].get('ssh_user')
            break

    return ssh_user


def get_ssh_port_from_os_image(patterns, os_image_name):

    # default ssh port
    ssh_port = 22

    for pattern in patterns.keys():

        if os_image_name.find(pattern) > -1:
            ssh_port = patterns[pattern].get('ssh_port')
            break

    return ssh_port


def get_inventory(config):
    image_name_patterns = config.get('os_image_ssh_config_patterns', {})

    server_list = query_server_list()
    detail_server_list = get_detail_server_list(server_list)

    instance_name_list = [server['name'] for server in detail_server_list]

    inventory_hostvars = {}
    for instance_name in instance_name_list:

        matched_instance = [
            server for server in detail_server_list
            if server['name'] == instance_name
        ][0]

        inventory_hostvars[instance_name] = {
            'ansible_ssh_host': get_ip_from_openstack_addr(matched_instance['addresses']),
            'ansible_ssh_user': get_ssh_user_from_os_image(image_name_patterns, matched_instance['image']),
            'ansible_ssh_port': get_ssh_port_from_os_image(image_name_patterns, matched_instance['image']),
            'ansible_ssh_private_key_file': matched_instance['key_name']
        }

    inventory = {
        'openstack': {
            'hosts': instance_name_list,
        },
        '_meta': {
            'hostvars': inventory_hostvars
        }
    }

    group_patterns = config.get('group_patterns')

    for group in group_patterns.keys():

        find_instance_names = [
            instance_name for instance_name in instance_name_list
            if instance_name.find(group_patterns[group].get('pattern')) > -1
        ]

        inventory[group] = {
            'hosts': find_instance_names
        }

    return inventory


def get_host_from_inventory(config, hostname):
    inventory = get_inventory(config)
    return inventory['_meta']['hostvars'][hostname]


def main():

    with open('openstack.yml', 'r') as configfile:
        try:
            config = yaml.load(configfile)

        except yaml.YAMLError as exception:
            print exception

    initialize(config)

    args = parse_args()

    if args.list:
        json.dump(get_inventory(config), sys.stdout)

    elif args.host:
        json.dump(get_host_from_inventory(config, args.host), sys.stdout)


if __name__ == '__main__':
    main()
