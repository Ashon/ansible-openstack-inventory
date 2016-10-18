#!/usr/bin/env python

import argparse
import json
import subprocess
import os
import sys
import yaml


# OS = OPENSTACK
OS_DYNAMIC_INVENTORY_TITLE = 'Openstack Dynamic Inventory'
OS_DYNAMIC_INVENTORY_CONFIG_FILENAME = 'openstack.yml'
OS_DYNAMIC_INVENTORY_CACHE = '.openstack_cached.json'

OS_CLIENT_CMD_SERVER_LIST_JSON = 'openstack server list -f json'
OS_CLIENT_CMD_NETWORK_LIST_JSON = 'openstack network list -f json'

OS_DEFAULT_SSH_USER = 'root'
OS_DEFAULT_SSH_PORT = 22

OS_RESOURCE_KEY_INSTANCE_NAME = 'name'
OS_RESOURCE_KEY_SSH_USER = 'ssh_user'
OS_RESOURCE_KEY_SSH_PORT = 'ssh_port'
OS_RESOURCE_KEY_SSH_KEY_NAME = 'key_name'
OS_RESOURCE_KEY_IMAGE = 'image'
OS_RESOURCE_KEY_IP_ADDRESSES = 'addresses'

# pairing dict between openstack env variable
# and dynamic inventory configuration
OS_CLIENT_CONFIG_PARING_DICT = {
    'OS_AUTH_URL': 'os_auth_url',
    'OS_USER_DOMAIN_NAME': 'os_user_domain_name',
    'OS_REGION_NAME': 'os_region_name',
    'OS_USERNAME': 'os_username',
    'OS_PASSWORD': 'os_password',
    'OS_TENANT_ID': 'os_tenant_id',
    'OS_TENANT_NAME': 'os_tenant_name'
}


def set_env_if_not_exists(env_var_name, default_value):
    if not os.environ.get(env_var_name):
        os.environ[env_var_name] = default_value


def initialize(config):

    for key in OS_CLIENT_CONFIG_PARING_DICT.keys():
        set_env_if_not_exists(
            env_var_name=key,
            default_value=config.get(OS_CLIENT_CONFIG_PARING_DICT[key])
        )


def parse_args():
    parser = argparse.ArgumentParser(
        description=OS_DYNAMIC_INVENTORY_TITLE)

    arg_group = parser.add_mutually_exclusive_group(required=True)
    arg_group.add_argument('--list', action='store_true')
    arg_group.add_argument('--save', action='store_true')
    arg_group.add_argument('--host')

    return parser.parse_args()


def get_stdout_from_cmd(cmd):
    return subprocess.check_output(cmd.split(' ')).rstrip()


def query_server_list():
    return json.loads(
        get_stdout_from_cmd(OS_CLIENT_CMD_SERVER_LIST_JSON))


def query_network_list():
    return json.loads(
        get_stdout_from_cmd(OS_CLIENT_CMD_NETWORK_LIST_JSON))


def query_server_info(instance_id_or_name):

    cmd = 'openstack server show {instance_id_or_name} {column_arg} -f json'

    required_resources = (
        OS_RESOURCE_KEY_INSTANCE_NAME,
        OS_RESOURCE_KEY_SSH_KEY_NAME,
        OS_RESOURCE_KEY_IP_ADDRESSES,
        OS_RESOURCE_KEY_IMAGE
    )

    column_arg = ' '.join([
        '-c ' + column for column in required_resources
    ])

    return json.loads(
        get_stdout_from_cmd(cmd.format(
            instance_id_or_name=instance_id_or_name,
            column_arg=column_arg)))


def get_detail_server_list(OS_serverlist):

    # slow...

    return [
        query_server_info(instance['ID'])
        for instance in OS_serverlist
    ]


def get_ip_from_OS_addr(OS_address_str):

    split_table = OS_address_str.split('=')

    # network_name = split_table[0]
    addresses = split_table[1].split(', ')

    return addresses[-1]


def get_ssh_user_from_os_image(patterns, os_image_name):

    ssh_user = OS_DEFAULT_SSH_USER

    for pattern in patterns.keys():

        if os_image_name.find(pattern) > -1:
            ssh_user = patterns[pattern].get(OS_RESOURCE_KEY_SSH_USER)
            break

    return ssh_user


def get_ssh_port_from_os_image(patterns, os_image_name):

    ssh_port = OS_DEFAULT_SSH_PORT

    for pattern in patterns.keys():

        if os_image_name.find(pattern) > -1:
            ssh_port = patterns[pattern].get(OS_RESOURCE_KEY_SSH_PORT)
            break

    return ssh_port


def get_inventory(config):
    image_name_patterns = config.get('os_image_ssh_config_patterns', {})

    server_list = query_server_list()
    detail_server_list = get_detail_server_list(server_list)

    instance_name_list = [
        server[OS_RESOURCE_KEY_INSTANCE_NAME]
        for server in detail_server_list
    ]

    inventory_hostvars = {}
    for instance_name in instance_name_list:

        matched_instance = [
            server for server in detail_server_list
            if server['name'] == instance_name
        ][0]

        inventory_hostvars[instance_name] = {
            'ansible_ssh_host': get_ip_from_OS_addr(
                matched_instance[OS_RESOURCE_KEY_IP_ADDRESSES]),

            'ansible_ssh_user': get_ssh_user_from_os_image(
                patterns=image_name_patterns,
                os_image_name=matched_instance[OS_RESOURCE_KEY_IMAGE]),

            'ansible_ssh_port': get_ssh_port_from_os_image(
                patterns=image_name_patterns,
                os_image_name=matched_instance[OS_RESOURCE_KEY_IMAGE]),

            'ansible_ssh_private_key_file': matched_instance.get(
                OS_RESOURCE_KEY_SSH_KEY_NAME)
        }

    inventory = {
        # openstack dynamic inventory group
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

    try:
        with open(OS_DYNAMIC_INVENTORY_CONFIG_FILENAME, 'r') as configfile:
            try:
                config = yaml.load(configfile)

            except yaml.YAMLError as exception:
                print exception
    except:
        print 'You Should Create \'openstack.yml\' for openstack dynamic inventory'
        print '"cp openstack.yml.example openstack.yml" first.'
        return 1

    initialize(config)

    args = parse_args()

    if args.list:
        try:
            with open(OS_DYNAMIC_INVENTORY_CACHE, 'r') as cached_inventory:
                json.dump(json.loads(cached_inventory.read()), sys.stdout)

        except:
            # when failed to read cached inventory
            json.dump(get_inventory(config), sys.stdout)

    elif args.host:
        json.dump(get_host_from_inventory(config, args.host), sys.stdout)

    elif args.save:
        with open(OS_DYNAMIC_INVENTORY_CACHE, 'w') as cached_inventory:
            cached_inventory.write(json.dumps(get_inventory(config)))
            print 'dynamic inventory is cached as "%s"' % OS_DYNAMIC_INVENTORY_CACHE


if __name__ == '__main__':
    main()
