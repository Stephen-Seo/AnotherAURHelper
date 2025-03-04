# Setting up AnotherAURHelper with LXC

It is recommended to use AnotherAURHelper with a container as a safety net due
to the fact that `makechrootpkg` directly sources/parses PKGBUILDs.

The following assumes you already have LXC installed. If not, [follow the
ArchWiki](https://wiki.archlinux.org/title/Linux_Containers#Setup) until you
can get an arbitrary container up and running.

!!! note
    The following code blocks will have different prefixes. `> ` is used to
    specify commands run on an ArchLinux installation, and `$ ` is used to
    specify commands run inside of the LXC container.

## Privileged Containers

AnotherAURHelper requires to be run in a privileged container because it uses
a chroot. If your LXC is already configured for unprivileged containers, you can
create a privileged container by commenting out the config for an unprivileged
container and creating a container, and uncommenting after the container has
been created to allow future containers to be created as unprivileged.

<div class="codehilite"><pre><code># /etc/lxc/default.conf
<span class="c">#lxc.idmap = u 0 100000 65536
#lxc.idmap = g 0 100000 65536</span></code></pre></div>

## LXC Container Setup

Create the container like the following on your host system.

<div class="codehilite"><pre><code><span class="cmd">> sudo lxc-create -n aur_helper -t download</span>
Downloading the image index

---
DIST             RELEASE     ARCH   VARIANT  BUILD
---
...
archlinux        current     amd64  default  20250303_05:33
archlinux        current     arm64  default  20250303_05:49
...
---

Distribution:
<span class="cmd">> archlinux</span>
Release:
<span class="cmd">> current</span>
Architecture:
<span class="cmd">> amd64</span>

The cached copy has expired, re-downloading...
Downloading the image index
Downloading the rootfs
Downloading the metadata
The image cache is now ready
Unpacking the rootfs

---
You just created an Archlinux  x86_64 (20250303_05:33) container.
</code></pre></div>

Start the container.

<div class="codehilite"><pre><code><span class="cmd">> sudo lxc-start -n aur_helper -s lxc.apparmor.allow_nesting=1 -s lxc.apparmor.profile=generated</span></code></pre></div>

Attach to a shell inside the container.

<div class="codehilite"><pre><code><span class="cmd">> sudo lxc-attach -n aur_helper</span></code></pre></div>

### Getting Required Packages

Update your [mirror-list](https://wiki.archlinux.org/title/Mirrors) in the
container and update.

<div class="codehilite"><pre><code><span class="lxc">$ pacman -Syu</span></code></pre></div>

`base-devel`, `devtools`, `python-toml`, and `ccache` is required.

<div class="codehilite"><pre><code><span class="lxc">$ pacman -S base-devel devtools python-toml ccache</span></code></pre></div>

You may need to grab an editor like `vim`, `emacs`, or `nano`.

<div class="codehilite"><pre><code><span class="lxc">$ pacman -S vim emacs nano</span></code></pre></div>

If your filesystem is using `btrfs`, you will need to install `btrfs-progs`.

<div class="codehilite"><pre><code><span class="lxc">$ pacman -S btrfs-progs</span></code></pre></div>

### Setting up SSH for the Container

This is pretty straightforward, but for those unfamiliar with ssh, heres a quick
setup guide.

First, install `openssh`.

<div class="codehilite"><pre><code><span class="lxc">$ pacman -S openssh</span></code></pre></div>

Enable and start sshd.

<div class="codehilite"><pre><code><span class="lxc">$ systemctl enable --now sshd</span></code></pre></div>

After setting up the user in the following section, you can use ssh to log in to
the user.

You can fetch the local ip address of the running container with the following.

<div class="codehilite"><pre><code><span class="cmd">> sudo lxc-ls -f</span>
NAME       STATE   AUTOSTART GROUPS IPV4    IPV6    UNPRIVILEGED
aur_helper RUNNING 0         -      omitted omitted false</code></pre></div>

Just use the local ip address in the IPV4 column and you can ssh into your user
like so.

<div class="codehilite"><pre><code><span class="cmd">> ssh build@10.0.3.1</span></code></pre></div>

### Creating the build user

A `build` user is to be created with `sudo` privileges that will be used to run
the builds.

First, create the user.

<div class="codehilite"><pre><code><span class="lxc">$ useradd -m -s /usr/bin/bash build</span></code></pre></div>

Then add sudo privileges for the `build` user.

<div class="codehilite"><pre><code><span class="lxc">$ EDITOR=nano visudo</span></code></pre></div>

Add the following line for sudo privileges for `build`.

<div class="codehilite"><pre><code><span class="txt">build ALL=(ALL:ALL) NOPASSWD: ALL</span></code></pre></div>

If you prefer to have `build` use a password for sudo privielges, then use the
following instead.

<div class="codehilite"><pre><code><span class="txt">build ALL=(ALL:ALL) ALL</span></code></pre></div>

And set `build`'s password.

<div class="codehilite"><pre><code><span class="lxc">$ passwd build</span></code></pre></div>

Open a shell as `build` to check if it works.

<div class="codehilite"><pre><code><span class="lxc">$ su - build
$ sudo ls -a</span></code></pre></div>

At this point you should be able to ssh into `build`.

## Creating the CHROOT

!!! note
    Continue the following steps as the `build` user, not as `root`.

Use `/usr/bin/mkarchroot` to create a CHROOT at `/home/build/chroot/root`.

<div class="codehilite"><pre><code><span class="lxc">$ mkdir /home/build/chroot
$ mkarchroot /home/build/chroot/root base base-devel cmake ninja</span></code></pre></div>

!!! warning
    Do NOT preinstall `ccache` or `sccache` in the CHROOT as it will be handled
    by AnotherAURHelper.

!!! note
    From now on, you must refer to the CHROOT as `/home/build/chroot` when
    handling it in AnotherAURHelper, even if the actual chroot is inside of
    `/home/build/chroot/root`.

!!! note
    The default LXC ArchLinux container has `/etc/locale.conf` set to `C.UTF-8`.
    You may have to change [locale settings as in the installation guide on the
    ArchWiki](https://wiki.archlinux.org/title/Installation_guide#Localization).

!!! note
    You are able to run commands in the CHROOT:  
    <div class="codehilite"><pre><code><span class="lxc">$ arch-nspawn /home/build/chroot/root pacman -S cmake</span></code></pre></div>  
    You may do this to also set proper locale information in the CHROOT.

## Set up GnuPG for Signature Verifcation and Package Signing

### Checking GnuPG

Create a directory at a location of your choosing, ideally inside of
`/home/build/`.

<div class="codehilite"><pre><code><span class="lxc">$ mkdir /home/build/checking_gpg
$ chmod 700 /home/build/checking_gpg
$ GNUPGHOME=/home/build/checking_gpg gpg -k</span></code></pre></div>

Whenever a build fails due to missing gpg public keys, the key can be added to
this directory. Usually there should be a key file inside of the AUR pkg's
directory, but otherwise the fingerprint can be used to fetch it directly.

<div class="codehilite"><pre><code><span class="c"># Load key from file</span>
<span class="lxc">$ GNUPGHOME=/home/build/checking_gpg gpg --import < the_pub_key_file.pub</span>
<span class="c"># Fetch key via fingerprint from a keyserver</span>
<span class="lxc">$ GNUPGHOME=/home/build/checking_gpg gpg --recv-keys A_DEV_KEYS_FINGERPRINT</span></code></pre></div>

### Signing GnuPG

A GnuPG public/private key pair will need to be generated. Only keys with
signature creation is necessary, so generate accordingly. Like the previous
GnuPG directory, this can be placed in `/home/build/`.

!!! note
    If you encounter errors, try using `--pinentry-mode loopback` as a flag to
    pass to gpg. Otherwise, run the shell inside of a `tmux` session. This may
    occur if you are accessing the `build` user through an attached shell
    instead of `ssh`.

Also, be prepared to set up a password for this key.

!!! warning
    Write the password down somewhere so you don't forget it! If you ever lose
    this password, you will need to revoke the old key, re-generate a new key,
    delete all package signatures, and re-sign all packages and the package
    database. (We will cover revoking old keys when necessary, package
    signatures, and the package database later.)

!!! note
    It may be beneficial to use a long password for this key instead of a short
    memorable one, as a malicious PKGBUILD might attempt to access it if the
    PKGBUILD hasn't been properly vetted first.

Follow the following to generate a GnuPG key for signatures only.

<div class="codehilite"><pre><code><span class="lxc">$ mkdir /home/build/signing_gpg
$ chmod 700 /home/build/signing_gpg
$ GNUPGHOME=/home/build/signing_gpg gpg --pinentry-mode loopback --full-gen-key</span>
gpg (GnuPG) 2.4.7; Copyright (C) 2024 g10 Code GmbH
This is free software: you are free to change and redistribute it.
There is NO WARRANTY, to the extent permitted by law.

gpg: keybox '/home/build/signing_gpg/pubring.kbx' created
Please select what kind of key you want:
   (1) RSA and RSA
   (2) DSA and Elgamal
   (3) DSA (sign only)
   (4) RSA (sign only)
   (9) ECC (sign and encrypt) *default*
  (10) ECC (sign only)
  (14) Existing key from card
Your selection?
<span class="lxc">$ 10</span>
Please select which elliptic curve you want:
(1) Curve 25519 *default*
(4) NIST P-384
(6) Brainpool P-256
Your selection?
<span class="lxc">$ 1</span>
Please specify how long the key should be valid.
         0 = key does not expire
      &lt;n&gt;  = key expires in n days
      &lt;n&gt;w = key expires in n weeks
      &lt;n&gt;m = key expires in n months
      &lt;n&gt;y = key expires in n years
Key is valid for? (0)
<span class="lxc">$ 0</span>
Key does not expire at all
Is this correct? (y/N)
<span class="lxc">$ y</span>

GnuPG needs to construct a user ID to identify your key.

Real name:
<span class="lxc">$ My Name (AUR Helper Signing Key)</span>
Email address:
<span class="lxc">$ my_email@example.com</span>
Comment:
<span class="lxc">$ Key for AnotherAURHelper</span>
You selected this USER-ID:
    "My Name (AUR Helper Signing Key) (Key for AnotherAURHelper) &lt;my_email@example.com&gt;"

Change (N)ame, (C)omment, (E)mail or (O)kay/(Q)uit?
<span class="lxc">$ O</span>
We need to generate a lot of random bytes. It is a good idea to perform
some other action (type on the keyboard, move the mouse, utilize the
disks) during the prime generation; this gives the random number
generator a better chance to gain enough entropy.
Enter passphrase:
<span class="lxc">$ ***********</span>
gpg: /home/build/signing_gpg/trustdb.gpg: trustdb created
gpg: directory '/home/build/signing_gpg/openpgp-revocs.d' created
gpg: revocation certificate stored as '/home/build/signing_gpg/openpgp-revocs.d/BFD86E817FA4B097A8636507A4FDFD431A0D481B.rev'
public and secret key created and signed.
pub   ed25519 2025-03-04 [SC]
      BFD86E817FA4B097A8636507A4FDFD431A0D481B
uid                      My Name (AUR Helper Signing Key) (Key for AnotherAURHelper) &lt;my_email@example.com&gt;</code></pre></div>

Verify you inputed the password correctly:

<div class="codehilite"><pre><code><span class="lxc">$ echo test_file > test_file
$ GNUPGHOME=/home/build/signing_gpg gpg --pinentry-mode loopback --detach-sign test_file</span>
Enter passphrase:
<span class="lxc">$ ***********
$ GNUPGHOME=/home/build/signing_gpg gpg --verify test_file.sig</span>
gpg: assuming signed data in 'test_file'
gpg: Signature made Tue Mar  4 03:59:43 2025 UTC
gpg:                using EDDSA key BFD86E817FA4B097A8636507A4FDFD431A0D481B
gpg: checking the trustdb
gpg: marginals needed: 3  completes needed: 1  trust model: pgp
gpg: depth: 0  valid:   1  signed:   0  trust: 0-, 0q, 0n, 0m, 0f, 1u
gpg: Good signature from "My Name (AUR Helper Signing Key) (Key for AnotherAURHelper) &lt;my_email@example.com&gt;" [ultimate]
<span class="c"># cleanup</span>
<span class="lxc">$ rm test_file test_file.sig</span></code></pre></div>

## Set up Output Dir and Configuration

Create an output directory for your built packages.

<div class="codehilite"><pre><code><span class="lxc">$ mkdir /home/build/aur_pkgs</span></code></pre></div>

Set up a `/home/build/config.toml` file with config for AnotherAURHelper.

!!! note
    The `config.toml` file can be named anything.

Refer to the `example_config.toml` file inside AnotherAURHelper's repo as a
reference.  
At this point, we will clone AnotherAURHelper.

<div class="codehilite"><pre><code><span class="lxc">$ git clone https://github.com/Stephen-Seo/AnotherAURHelper.git</span></code></pre></div>

Your config should look like the following:

    :::python
    ########## MANDATORY VARIABLES
    chroot = "/home/build/chroot"
    # Location to place built packages.
    pkg_out_dir = "/home/build/aur_pkgs"
    # It is recommended to put the repo file in the "pkg_out_dir".
    # If the tar file doesn't already exist, it will be automatically created.
    repo = "/home/build/aur_pkgs/MyRepo.db.tar"
    # Location to clone packages from AUR.
    clones_dir = "/home/build/aur"
    gpg_dir = "/home/build/checking_gpg"
    logs_dir = "/home/build/logs"
    signing_gpg_dir = "/home/build/signing_gpg"
    signing_gpg_key_fp = "BFD86E817FA4B097A8636507A4FDFD431A0D481B"
    editor = "/usr/bin/nano"
    # if true, all logs are prepended with current time in UTC
    is_timed = true
    # if true, all output build logs are prepended with current time in UTC
    is_log_timed = true
    # Default log_limit is 1 GiB
    log_limit = 1073741824
    # If true, then make the build fail if the limit is reached
    error_on_limit = true
    # If true, timestamps are in localtime. If false, timestamps are UTC.
    datetime_in_local_time = true
    # If true, all builds will be done in a tmpfs. Recommended to have a lot of RAM and/or swap.
    tmpfs = false
    # If true, only packages to be built will be printed when USR1 is signaled.
    print_state_info_only_building_sigusr1 = true
    ########## END OF MANDATORY VARIABLES

!!! note
    The `repo = ...` option determines the name of the repository. If you want
    to name it "MyCoolRepo", then it should be set as `repo = "/home/build/aur_pkgs/MyCoolRepo.db.tar"`.

Create some necessary directories.

<div class="codehilite"><pre><code><span class="lxc">$ mkdir -p aur_pkgs
$ mkdir -p aur
$ mkdir -p logs</span></code></pre></div>

Create some necessary symlinks based on the previously set `repo = ...`.

<div class="codehilite"><pre><code><span class="lxc">$ ln -s MyRepo.db.tar /home/build/aur_pkgs/MyRepo.db
$ ln -s MyRepo.files.tar /home/build/aur_pkgs/MyRepo.files</span></code></pre></div>

Here is a few packages you can add to your `config.toml`.

    :::ini
    [[entry]]
    name = "stdman"

    [[entry]]
    name = "cpufetch-git"

## Registering the Repo on other Arch systems

!!! warning
    Some commands/config should be used on in your LXC container and some on a
    different ArchLinux system that will install the packages built by
    AnotherAURHelper. Thus, be sure you are on the right system before inputting
    commands as it may get confusing.

The following assumes that the AUR repo's name is `MyRepo` as indicated in the
previous config.

Add the following to your `/etc/pacman.conf` on an ArchLinux system that will
install the built AUR packages you build.

    :::ini
    [MyRepo]
    SigLevel = Required TrustedOnly
    Server = file:///home/user/aur_pkgs

!!! note
    This config assumes use of `sshfs` or `rsync`.

!!! note
    It is possible to use `nginx` (or others) to host the directory to use as a
    repo accessible over http/https. This is a little more involved but is
    possible. Accessing such on other systems may set the `Server = ...` line
    in the `/etc/pacman.conf` to a url like
    `Server = https://example.com/aur_pkgs`.

We're not done yet, as the other ArchLinux system needs to get the public key
of the AUR Helper signing key to verify the packages built and signed by
AnotherAURHelper.

Export the public key of your GnuPG signing key from your LXC instance.

<div class="codehilite"><pre><code><span class="lxc">$ GNUPGHOME=/home/build/signing_gpg gpg --export > signing_key.pub</span></code></pre></div>

Use `scp`, `sftp`, or `sshfs` to get this public key out of the container. Use
`pacman-key` on the other ArchLinux system to import and locally sign the
public key to trust it.

<div class="codehilite"><pre><code><span class="cmd">> sudo pacman-key -a signing_key.pub</span></code></pre></div>

Check that the imported key is the only key listed when querying for it.

<div class="codehilite"><pre><code><span class="cmd">> sudo pacman-key --finger 'AUR Helper Signing Key'</span>
pub   ed25519 2025-03-04 [SC]
      BFD8 6E81 7FA4 B097 A863  6507 A4FD FD43 1A0D 481B
uid           [ unknown] My Name (AUR Helper Signing Key) (Key for AnotherAURHelper) &lt;my_email@example.com&gt;</code></pre></div>

If there is only one key listed, then you can use the `AUR Helper Signing Key`
string to specify the correct key to sign. (Signing another key in GnuPG means
that you trust it.) If more than one key is listed, you will have to adjust the
string passed to `pacman-key --finger ...` until only the key you want to sign
is shown.

Once you've determined the string that specifies the key you created and want
to sign, sign it.

<div class="codehilite"><pre><code><span class="cmd">> sudo pacman-key --lsign-key 'AUR Helper Signing Key'</span></code></pre></div>

Once this is done, the ArchLinux system will now trust packages signed by your
signing key. If you want to revoke such a key, you can delete it from your
pacman's keyring.

!!! warning
    Be careful with `pacman-key`'s delete command, as you might accidentally
    delete keys you don't mean to delete. If such a thing happens, you may have
    to [regenerate your ArchLinux installation's pacman keyring](https://wiki.archlinux.org/title/Pacman/Package_signing#Resetting_all_the_keys).

Use the following command to delete a key from your ArchLinux system's keyring.

<div class="codehilite"><pre><code><span class="cmd">> sudo pacman-key -d 'AUR Helper Signing Key'</span></code></pre></div>

## Testing

The build process will typically involve running the following.

<div class="codehilite"><pre><code><span class="lxc">$ ./AnotherAURHelper/update.py --config /home/build/config.toml</span></code></pre></div>

Just follow the steps, and by the end of it, it should build your packages,
sign them, and place them in the directory specified in your `config.toml`.

## Serving the Packages

As mentioned earlier, the contents of your `/home/build/aur_pkgs` directory can
be served with `nginx` or others. The directory can be copied from your LXC
container to elsewhere with `ssh` (`sshfs` maybe) or even `rsync`.
