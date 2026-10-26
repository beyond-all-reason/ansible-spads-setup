# Ansible SPADS setup

This repository contains Ansible playbooks for setting up SPADS servers and optionally resoil-autohost.

## Dependencies

Make sure required collections are installed by running:

```
ansible-galaxy collection install -r requirements.yml
```

If you pull repo and there are changes to that fille, you need to rerun the command to make sure you pick up latest changes.

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

## Examples

**Configure/verify SPADS is configured properly on all servers**
> ansible-playbook play.yaml --ask-vault-pass

**Restart all SPADS services only on US2**
> ansible-playbook restart.yaml --limit us2 --ask-vault-pass

## Available playbooks:
- play.yaml - configure SPADS/verify SPADS is configured properly
- delete.yaml - delete SPADS files and services
- restart.yaml - restart all SPADS services
- start.yaml - start all SPADS services
- stop.yaml - stop all SPADS services
- engineupdate.yaml - runs spads_config_bar_updater.py -c -u (doesn't restart SPADS)
- getreplays.yaml - discover and optionally download replays matching a start window and player list

## Collecting replays

[getreplays.yaml](getreplays.yaml) targets the `prod` inventory group, including
engine-testing hosts. It does not check whether games were passworded. Defaults
select games starting on **25 October 2026 from 01:00 inclusive to 13:00 exclusive
fixed CET (UTC+01:00)**, i.e. `00:00Z <= start < 12:00Z`. This is deliberately not
daylight-saving-aware Central European local time.

Run from a Linux Ansible control node (or WSL) with production SSH and sudo access:

```sh
# Discovery only: saves one manifest per host, downloads no replay files.
ansible-playbook getreplays.yaml -i inventory/prod-inventory --ask-vault-pass \
  -e replay_attendees_file=/absolute/path/to/attendees.txt

# Scan again, download matches, and verify size and SHA-256.
ansible-playbook getreplays.yaml -i inventory/prod-inventory --ask-vault-pass \
  -e replay_attendees_file=/absolute/path/to/attendees.txt \
  -e replay_download=true
```

The default attendee file is `../attendees.txt` relative to this checkout. Provide
one exact player name per line. Matching is case-sensitive and literal, includes
clan tags, and excludes spectators; aliases or renamed accounts are not resolved.
The start script identifies players assigned at game setup, not later joiners.

Optional variables: `replay_start` and `replay_end` (ISO timestamps with explicit
offsets), `replay_root` (remote directory), and `replay_output_dir` (absolute local
directory; default `replays` in this checkout). These defaults can be overridden
using `-e`. Discovery mode is the default, **not** Ansible `--check` mode.

[scanreplays.py](scanreplays.py) uses Python 3.10+ and only the standard library.
It recursively searches the cluster directory, prefilters recognised UTC filename
timestamps, then checks the embedded version-5 replay header and setup script.
Unrecognised filenames are still inspected. Only headers/scripts are decompressed;
matching compressed files are streamed for SHA-256. It does not validate the
entire compressed packet stream or guarantee that a replay is playable.

Manifests contain remote paths, game IDs, UTC start times, matching player names,
sizes, SHA-256 checksums, and per-file errors. They are saved at
`replays/<inventory-host>/manifest.json`. Downloads preserve both host and remote
instance directories beneath `replays/files/`, avoiding filename collisions.
Repeated downloads use Ansible's checksum comparison to skip unchanged files.
The download run rescans current files; it does not reuse an earlier manifest.

Missing roots, malformed candidate replays, traversal errors, and changed files
are reported as failures. Per-file scan errors are persisted before blocking that
host's downloads. Ansible reports unreachable hosts and transfer failures in its
recap: **a failed host means collection is incomplete**, even if others succeed.
Successful downloads are checked against the scan manifest. Fetch with sudo can
buffer matched replays in memory, so account for large files on hosts/control node.
Host cleanup may delete older replays, especially under disk pressure; collect
promptly. This playbook does not pause cleanup or alter SPADS services.

Local scanner tests (no host connections):

```sh
python3 -m unittest discover -s tests -v
```

## Ansible Vault
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

## Recoil autohost

Hosts can additionally run [recoil-autohost](https://github.com/beyond-all-reason/recoil-autohost). It's disabled by default in prod.

To enable it on a host, create bot credentials in teiserver and set in `host_vars/(hostname)/vars.yaml`:

```yaml
recoil_autohost_enabled: true
recoil_autohost_client_id: "<client id>"
recoil_autohost_client_secret: "{{ vault_recoil_autohost_client_secret }}"
```

## Local testing

### Setup

We use Incus for local testing. Make sure you have it installed and initialized following [the official getting started docs](https://linuxcontainers.org/incus/docs/main/tutorial/first_steps/).

To create a new container and initialize it via cloud-init, run the following command:

```
touch .incus-integration-on && \
chmod 0600 test.ssh.key && \
incus launch images:debian/trixie/cloud spads-test1 < test.incus.yml && \
incus exec spads-test1 -- cloud-init status --wait
```

This creates spads instance `TEST1`. You can create any number of them `TEST2`, `TEST3`, etc. by changing the name in the command above.

Then test that it works for ansible:

```
ansible test1 -m shell -a 'uname -a'
```

### Usage

#### Run playbook

Now you can use all the playbooks and roles as usual, just make sure you are targeting the `dev` inventory group or individual `test1` host. For example:

```
ansible-playbook -l dev play.yaml
```

To override the lobby server temporarily from default `localhost` without modifying [dev.yaml](group_vars/dev.yaml) for test1:

```
ansible-playbook -l test1 -e "spads_lobbyHost=10.177.67.244" play.yaml
```

#### Connect to the container

To enter into container shell, run the following command:

```
incus exec spads-test1 -- /bin/bash
```

You can also ssh into it with something like:

```
ssh -i test.ssh.key ansible@$(ansible-inventory --host test1 | jq -r '.ansible_host')
```

#### Register bot with teiserver

You can register the spads lobby account with teiserver using the `register_bot.yaml` playbook:

```
ansible-playbook -l test1 register_bot.yaml
```

After that, you have to give the newly created account "Bot", "Verified" **and "Moderator"** roles manually in the teiserver web interface.

> [!CAUTION]
> If you are creating a new account for the bot because you are repointing SPADS at different instance or because you cleaned up the teiserver database, you **must** drop the `spads/var/ClusterManager/existingAccounts.dat` file because without it SPADS will think the account already exists and won't try to create it again.

#### Monitoring host

To configure sending metrics to local monitoring host set up with [ansible-monitoring](https://github.com/beyond-all-reason/ansible-monitoring) playbook, run:

```
MON_HOST_IP=$(incus list -f csv -c 4 bar-mon-test | grep -E 'eth|enp' | cut -d' ' -f1)
ansible-playbook -l test play.yaml --diff -t monitoring \
  -e "{ configure_monitoring: true, monitoring_write_host_ip: $MON_HOST_IP }"
```

#### Recoil autohost

Autohost is enabled in dev. To connect it to the teiserver test container set up with [ansible-teiserver](https://github.com/beyond-all-reason/ansible-teiserver) playbook, run the `register_autohost.yaml` playbook once. It makes `teiserver.local` resolve to `spads_lobbyHost` (teiserver's OAuth2 token endpoint uses its domain name), and creates the bot with credentials from [dev.yaml](group_vars/dev.yaml) in teiserver over ssh:

```
ansible-playbook -l test1 -e "spads_lobbyHost=10.177.67.244" register_autohost.yaml
```

### Cleanup

To stop and remove the container:

```
incus stop spads-test1 && incus delete spads-test1
```
