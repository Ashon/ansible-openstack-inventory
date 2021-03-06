# Ansible Dynamic Inventory for Openstack
  Simple Ansible Dynamic Inventory for Openstack


## Dependencies
  You need to get openstack cli to use this dynamic inventory.

```
$ sudo pip install python-openstackclient
```


## Usage
  configure openstack.yml (config for dynamic inventory)

``` yml

# file: openstack.yml
---
os_auth_url: http://your.keystone.com/v3    # openstack keystone api url
os_user_domain_name: openstackdomain        # openstack domain name
os_region_name: region                      # openstack region name
os_tenant_id: 187263vf78f2fasoiwur184712    # openstack tenant id
os_tenant_name: openstack_tanant            # openstack tenant name
os_username: openstack_user                 # openstack api user
os_password: user_password                  # openstack api user password

os_image_ssh_config_patterns:               # openstack image default ssh configurations

  # pattern
  ubuntu:
    # openstack image's default ssh configuration
    ssh_user: ubuntu
    ssh_port: 22

  some_your_openstack_image:
    ssh_user: image_user
    ssh_port: 23456

# customized openstack group
groups:

  # ansible group name
  jenkins:

    # instance name patterns
    # dynamic inventory will aggregate instances
    # which is matched with patterns to 'jenkins' group.
    pattern: CI_JENKINS-

  ci-develop:
    pattern: CI-DEVEL-

```

  use dynamic inventory

```
$ ansible -i openstack.py jenkins -m ping
```

## Issues
  - Change `openstack cli` to `novaclient` module.
  - Support group_vars to dynamic inventory's customized groups.
