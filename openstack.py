#!/usr/bin/env python
import argparse
import json
import os
import subprocess
import sys
import yaml
from collections import namedtuple

# OS = OPENSTACK
OS_DYNAMIC_INVENTORY_TITLE = 'Openstack Dynamic Inventory'
OS_DYNAMIC_INVENTORY_CONFIG_FILENAME = 'openstack.yml'
OS_DYNAMIC_INVENTORY_CACHE = '.openstack_cached.json'
OS_DYNAMIC_INVENTORY_ERR_CODE_INITIALIZE = 1
OS_DYNAMIC_INVENTORY_DEFAULT_GROUP_NAME = 'openstack'

# Openstack Client command
OS_CLIENT_CMD_SERVER_LIST_JSON = 'openstack server list -f json'
OS_CLIENT_CMD_NETWORK_LIST_JSON = 'openstack network list -f json'
OS_CLIENT_CMD_SERVER_INFO_JSON = 'openstack server show {instance_id_or_name} {column_arg} -f json'

# Openstack instance's default ssh config
OS_DEFAULT_SSH_USER = 'root'
OS_DEFAULT_SSH_PORT = 22

# Openstack instance information columns
OS_RESOURCE_KEY_INSTANCE_ID = 'ID'
OS_RESOURCE_KEY_INSTANCE_NAME = 'name'
OS_RESOURCE_KEY_SSH_USER = 'ssh_user'
OS_RESOURCE_KEY_SSH_PORT = 'ssh_port'
OS_RESOURCE_KEY_SSH_KEY_NAME = 'key_name'
OS_RESOURCE_KEY_IMAGE = 'image'
OS_RESOURCE_KEY_IP_ADDRESSES = 'addresses'

# required openstack instance resources
# to generate ansible inventory ssh info
OS_REQUIRED_RESOURCES = (
    OS_RESOURCE_KEY_INSTANCE_NAME,
    OS_RESOURCE_KEY_SSH_KEY_NAME,
    OS_RESOURCE_KEY_IP_ADDRESSES,
    OS_RESOURCE_KEY_IMAGE
)

# dynamic inventory's configuration keys
CONFIG_OS_AUTH_URL = 'os_auth_url'
CONFIG_OS_USER_DOMAIN_NAME = 'os_user_domain_name'
CONFIG_OS_REGION_NAME = 'os_region_name'
CONFIG_OS_USERNAME = 'os_username'
CONFIG_OS_PASSWORD = 'os_password'
CONFIG_OS_TENANT_ID = 'os_tenant_id'
CONFIG_OS_TENANT_NAME = 'os_tenant_name'
CONFIG_SSH_CONFIG_BY_IMAGE_PATTERNS = 'os_image_ssh_config_patterns'
CONFIG_ANSIBLE_KEY_DIRECTORY = 'ansible_key_dir'
CONFIG_GROUPS = 'groups'
CONFIG_GROUPS_PATTERN = 'pattern'
CONFIG_GROUPS_CHILDREN = 'children'

# pairing dict between openstack env variable
# and dynamic inventory configuration
OS_CLIENT_CONFIG_PARING_DICT = {
    'OS_AUTH_URL': CONFIG_OS_AUTH_URL,
    'OS_USER_DOMAIN_NAME': CONFIG_OS_USER_DOMAIN_NAME,
    'OS_REGION_NAME': CONFIG_OS_REGION_NAME,
    'OS_USERNAME': CONFIG_OS_USERNAME,
    'OS_PASSWORD': CONFIG_OS_PASSWORD,
    'OS_TENANT_ID': CONFIG_OS_TENANT_ID,
    'OS_TENANT_NAME': CONFIG_OS_TENANT_NAME
}

# define ansible inventory schema as namedtuple
AnsibleInventoryHost = namedtuple(
    'AnsibleInventoryHost',
    ','.join([
        'ansible_ssh_host',
        'ansible_ssh_user',
        'ansible_ssh_port',
        'ansible_ssh_private_key_file'
    ])
)

# ansible dynamic inventory json object key
ANSIBLE_INVENTORY_KEY_META = '_meta'
ANSIBLE_INVENTORY_KEY_HOSTS = 'hosts'
ANSIBLE_INVENTORY_KEY_HOSTVARS = 'hostvars'
ANSIBLE_INVENTORY_KEY_CHILDREN = 'children'


def set_env_if_not_exists(env_var_name, default_value):

    ''' Set Environment variable as 'default_value'
        if Environment has no matched with 'env_var_name'. '''

    if not os.environ.get(env_var_name):
        os.environ[env_var_name] = default_value


def initialize(config):
    valid = True
    for key in OS_CLIENT_CONFIG_PARING_DICT.keys():
        try:
            set_env_if_not_exists(
                env_var_name=key,
                default_value=config.get(OS_CLIENT_CONFIG_PARING_DICT[key])
            )
        except AttributeError:
            print 'There is no value "%s" in environment or "%s" in %s' % (
                key, OS_CLIENT_CONFIG_PARING_DICT[key],
                OS_DYNAMIC_INVENTORY_CONFIG_FILENAME)
            valid = False
    return valid


def parse_args():
    parser = argparse.ArgumentParser(
        description=OS_DYNAMIC_INVENTORY_TITLE)
    arg_group = parser.add_mutually_exclusive_group(required=True)
    arg_group.add_argument('--list', action='store_true')
    arg_group.add_argument('--save', action='store_true')
    arg_group.add_argument('--clean', action='store_true')
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
    column_arg = ' '.join([
        '-c ' + column for column in OS_REQUIRED_RESOURCES
    ])
    return json.loads(
        get_stdout_from_cmd(OS_CLIENT_CMD_SERVER_INFO_JSON.format(
            instance_id_or_name=instance_id_or_name,
            column_arg=column_arg)))


def get_detail_server_list(os_serverlist):
    # slow...
    return [
        query_server_info(instance[OS_RESOURCE_KEY_INSTANCE_ID])
        for instance in os_serverlist
    ]


def get_ip_from_instance(os_instance):
    split_table = os_instance[OS_RESOURCE_KEY_IP_ADDRESSES].split('=')

    # network_name = split_table[0]
    addresses = split_table[1].split(', ')

    return addresses


def get_ssh_user_from_instance(patterns, os_instance):

    ssh_user = OS_DEFAULT_SSH_USER

    for pattern in patterns.keys():
        if os_instance[OS_RESOURCE_KEY_IMAGE].find(pattern) > -1:
            ssh_user = patterns[pattern].get(OS_RESOURCE_KEY_SSH_USER)
            break

    return ssh_user


def get_ssh_port_from_instance(patterns, os_instance):

    ssh_port = OS_DEFAULT_SSH_PORT

    for pattern in patterns.keys():
        if os_instance[OS_RESOURCE_KEY_IMAGE].find(pattern) > -1:
            ssh_port = patterns[pattern].get(OS_RESOURCE_KEY_SSH_PORT)
            break

    return ssh_port


def get_ssh_key_path_from_instance(key_directory, os_instance):
    return '%s/%s' % (
        key_directory, os_instance[OS_RESOURCE_KEY_SSH_KEY_NAME])


def get_instance_from_instance_list(instance_name, os_instance_list):
    return [
        os_instance for os_instance in os_instance_list
        if os_instance[OS_RESOURCE_KEY_INSTANCE_NAME] == instance_name
    ][0]


def get_inventory(config):
    image_name_patterns = config.get(CONFIG_SSH_CONFIG_BY_IMAGE_PATTERNS, {})
    ssh_key_directory = config.get(CONFIG_ANSIBLE_KEY_DIRECTORY, '.')

    os_instance_list = get_detail_server_list(query_server_list())

    instance_name_list = [
        os_instance[OS_RESOURCE_KEY_INSTANCE_NAME]
        for os_instance in os_instance_list
    ]

    inventory_hostvars = {}

    for instance_name in instance_name_list:

        matched_instance = get_instance_from_instance_list(
            instance_name, os_instance_list)

        instance_ips = get_ip_from_instance(matched_instance)
        ifaces = instance_ips[:-1]
        ssh_host = instance_ips[-1]

        inventory_hostvars[instance_name] = AnsibleInventoryHost(
            ansible_ssh_host=ssh_host,
            ansible_ssh_port=get_ssh_port_from_instance(
                patterns=image_name_patterns,
                os_instance=matched_instance),
            ansible_ssh_user=get_ssh_user_from_instance(
                patterns=image_name_patterns,
                os_instance=matched_instance),
            ansible_ssh_private_key_file=get_ssh_key_path_from_instance(
                key_directory=ssh_key_directory,
                os_instance=matched_instance)
        )._asdict()

        for i in range(0, len(ifaces)):
            inventory_hostvars[instance_name]['iface_%s' % str(i)] = ifaces[i]

    ansible_inventory = {
        # set 'openstack' as

        default openstack instance group
        # in dynamic inventory
        OS_DYNAMIC_INVENTORY_

        DEFAULT_GROUP_NAME: {
            ANSIBLE_INVENTORY_KEY_HOSTS: instance_name_list,
        },
        ANSIBLE_INVENTORY_KEY_META: {
            ANSIBLE_INVENTORY_KEY_HOSTVARS: inventory_hostvars
        }
    }

    groups = config.get(CONFIG_GROUPS, {})

    for group in groups.keys():
        inventory_group = {}
        instance_name_pattern = groups[group].get(CONFIG_GROUPS_PATTERN)
        children = groups[group].get(CONFIG_GROUPS_CHILDREN)
        # register openstack instances as group hosts
        if instance_name_pattern:
            inventory_group[ANSIBLE_INVENTORY_KEY_HOSTS] = [
                instance_name for instance_name in instance_name_list
                if instance_name.find(instance_name_pattern) > -1
            ]
        # register child groups
        if children:
            inventory_group[ANSIBLE_INVENTORY_KEY_CHILDREN] = children
        ansible_inventory[group] = inventory_group

    return ansible_inventory


def get_host_from_inventory(config, hostname):

    ansible_inventory = get_inventory(config)

    return ansible_inventory[
        ANSIBLE_INVENTORY_KEY_META][
        ANSIBLE_INVENTORY_KEY_HOSTVARS][
        hostname
    ]


def main():

    try:
        with open(OS_DYNAMIC_INVENTORY_CONFIG_FILENAME, 'r') as configfile:
            try:
                config = yaml.load(configfile)

            except yaml.YAMLError as exception:
                print exception

    except:
        print \
            'You Should Create \'{config}\' for openstack dynamic inventory\n' \
            '"cp {config}.example {config}" first.'.format(
                config=OS_DYNAMIC_INVENTORY_CONFIG_FILENAME)

        return OS_DYNAMIC_INVENTORY_ERR_CODE_INITIALIZE

    args = parse_args()

    if not initialize(config):
        return OS_DYNAMIC_INVENTORY_ERR_CODE_INITIALIZE

    if args.list:
        try:
            with open(OS_DYNAMIC_INVENTORY_CACHE, 'r') as cached_inventory:
                json.dump(json.loads(cached_inventory.read()), sys.stdout)

        except:
            # when failed to read cached inventory
            # generate inventory using openstack client
            json.dump(get_inventory(config), sys.stdout)

    elif args.host:
        json.dump(get_host_from_inventory(config, args.host), sys.stdout)

    elif args.save:
        with open(OS_DYNAMIC_INVENTORY_CACHE, 'w') as cached_inventory:
            cached_inventory.write(json.dumps(get_inventory(config)))
            print 'dynamic inventory is cached as "%s"' % OS_DYNAMIC_INVENTORY_CACHE

    elif args.clean:
        try:
            os.remove(OS_DYNAMIC_INVENTORY_CACHE)
            print 'cleanup cached inventory "%s"' % OS_DYNAMIC_INVENTORY_CACHE

        except OSError as e:
            print e

    return 0

if __name__ == '__main__':
    main()
