# Ansible SPADS setup

This repository contains Ansible playbooks for setting up SPADS servers.

## On each client (SPADS server)
Install python3.
> sudo apt install python3

## On the Ansible server
1. Install Ansible and sshpass.
   > sudo apt install ansible sshpass
2. SSH to each client once and accept their key to add them to the known hosts.
3. Checkout this repo and then run any following Ansible command from the checked out folder.
4. Configure the variable files
   - groups_vars/all.yaml - contains the variables that will be applied to every spads server
   - groups_vars/prod/vars.yaml - variables for every prod server. Anything set here will override groups_vars/all.yaml
   - groups_vars/(region).yaml - variables specific to a region (AU, EU, US).
   - host_vars/(hostname).yaml - contains the variables specific to the host. Anything set here will override all other
6. Run Ansible. The typical syntax for running Ansible with some files encrypted with Ansible Vault is:
   > ansible-playbook (playbookfile) -i (inventoryfile) --ask-vault-pass

   If no files are encrypted --ask-vault-pass can be removed.

   Run can be limited to a specific host with --limit (hostname) \
   Note: use the hostname set in the inventory file
   > ansible-playbook (playbookfile) -i (inventoryfile) --limit (hostname)

# Examples

**Configure/verify SPADS is configured properly on all servers**
> ansible-playbook play.yaml --ask-vault-pass

**Restart all SPADS services only on US2**
> ansible-playbook restart.yaml --limit us2 --ask-vault-pass

# Available playbooks:
- play.yaml - configure SPADS/verify SPADS is configured properly
- delete.yaml - delete SPADS files and services
- restart.yaml - restart all SPADS services
- start.yaml - start all SPADS services
- stop.yaml - stop all SPADS services
- engineupdate.yaml - runs spads_config_bar_updater.py -c -u (doesn't restart SPADS)

# Ansible Vault
Ansible Vault provides a way to encrypt sensitive information used by Ansible. It'll prompt for the password when running a command.

**View encrypted file**
> ansible-vault view file1.yaml file2.yaml file3.yaml

**Encrypt an existing file**
> ansible-vault encrypt file1.yaml file2.yaml file3.yaml

**Edit an encrypted file**
> ansible-vault edit file.yaml

**Decrypt a file**
> ansible-vault decrypt file1.yaml file2.yaml file3.yaml

**Change the encrpytion key of a file**
> ansible-vault rekey file1.yaml file2.yaml file3.yaml

# Local testing

## Setup

We use LXD for local testing. Make sure you have it installed and initialized [following the docs](https://documentation.ubuntu.com/lxd/en/latest/). For example for Debian, it's as simple as `sudo apt install lxd && sudo lxd init`.

To create a new container and initialize it via cloud-init, run the following command:

```
touch .lxd-integration-on && \
sudo lxc launch images:debian/bookworm/cloud spads-test1 < test.lxc.yml && \
sudo lxc exec spads-test1 -- cloud-init status --wait
```

This creates spads instance `TEST1`. You can create any number of them `TEST2`, `TEST3`, etc. by changing the name in the command above.

Then test that it works for ansible:

```
ansible test1 -m shell -a 'uname -a'
```

## Usage

### Run playbook

Now you can use all the playbooks and roles as usual, just make sure you are targeting the `dev` inventory group or individual `test1` host. For example:

```
ansible-playbook -l dev play.yaml
```

To override the lobby server temporarily from default `localhost` without modifying [dev.yaml](group_vars/dev.yaml) for test1:

```
ansible-playbook -l test1 -e "spads_lobbyHost=10.177.67.244" play.yaml
```

### Connect to the container

To enter into container shell, run the following command:

```
sudo lxc exec spads-test1 -- /bin/bash
```

You can also ssh into it with something like:

```
ssh -i test.ssh.key ansible@$(ansible-inventory --host test1 | jq -r '.ansible_host')
```

### Register bot with teiserver

You can register the spads lobby account with teiserver using the `register_bot.yaml` playbook:

```
ansible-playbook -l test1 register_bot.yaml
```

After that, you have to give the newly created account "Bot", "Verified" **and "Moderator"** roles manually in the teiserver web interface.

## Cleanup

To stop and remove the container:

```
sudo lxc stop spads-test1 && sudo lxc delete spads-test1
```
