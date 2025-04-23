# Key handling with AnotherAURHelper

AnotherAURHelper maintains an ArchLinux repository. This is achieved by the
following things:

1. Every package is signed with the `signing key`.
2. After every time a package is built, the database file is signed by the
`signing key`.

Note that the database file contains information about every package in the
repository and it must be signed after packages are added/removed, otherwise
pacman will notice the mismatch between signature file and database file.

!!! note
    The database filename depends on the name of the repository. If your config
    has the line `repo = "/home/build/aur_pkgs/MyCoolRepo.db.tar`, then the
    database file is `MyCoolRepo.db.tar`, and the name of the repository is
    referred to as `MyCoolRepo`.

## Rotating the Signing Key

If you ever need to replace the signing key, here are the steps you need to
follow to ensure your repository is usable.

### Removing Old Signatures

If your config has `pkg_out_dir = "/home/build/aur_pkgs"`, then you can just
remove every file ending with the suffix `.sig` to remove old signatures.

    rm /home/build/aur_pkgs/*.sig

### Revoking the Old Signing Key

On every ArchLinux machine that has trusted the previous key, you need to
delete the previous signing key as root.

First, determine you have selected the correct key with `--finger`.

<div class="codehilite"><pre><code><span class="cmd">> sudo pacman-key --finger 'AUR Helper Signing Key'</span>
pub   ed25519 2025-03-04 [SC]
      BFD8 6E81 7FA4 B097 A863  6507 A4FD FD43 1A0D 481B
uid           [  full  ] My Name (AUR Helper Signing Key) (Key for AnotherAURHelper) &lt;my_email@example.com&gt;</code></pre></div>

Then, you can remove the key with a single command.

!!! warning
    If you accidentally remove multiple keys, you may have to refresh the pacman
    key database on your ArchLinux machine. [The Arch Wiki has instructions for
    this here](https://wiki.archlinux.org/title/Pacman/Package_signing#Resetting_all_the_keys).

<div class="codehilite"><pre><code><span class="cmd">> sudo pacman-key --delete 'AUR Helper Signing Key'</span></code></pre></div>

### Re-registering the New Signing Key

You can follow the steps in the [`Setup with LXC`](https://stephen-seo.github.io/AnotherAURHelper/setup_lxc)
guide to recreate the new key and to re-register the new key with the ArchLinux
machines.

!!! note
    You must remove the previous key completely, otherwise you might re-use the
    old key by mistake. The most sure way to do this is to remove the
    `signing_gpg` directory and make recreate the directory with `700`
    permissions.

### Re-signing the Packages

!!! note
    gpg may only require you to input the password for your signing key once
    because it caches your credentials with `gpg-agent`. If you don't use gpg
    for long enough, the cache expires, and then you have to re-input your
    gpg password again when you use it.

Every package in your `pkg_out_dir` directory should be signed with the new key.

<div class="codehilite"><pre><code><span class="lxc">$ GNUPGHOME=/home/build/signing_gpg find /home/build/aur_pkgs -regex '^/home/build/aur_pkgs/.*pkg\.tar\.\(xz\|zst\)$' -execdir gpg --detach-sign '{}' ';'</span></code></pre></div>

The previous command should sign every package with the new key that you set up.

### Re-creating and Signing the Database File

The easiest way to re-set-up the database file is to remove it, then add
entries.

<div class="codehilite"><pre><code><span class="lxc">$ rm /home/build/aur_pkgs/MyRepo.db.tar</span>
<span class="lxc">$ find /home/build/aur_pkgs -regex '^/home/build/aur_pkgs/.*pkg\.tar\.\(xz\|zst\)$' -execdir repo-add --include-sigs /home/build/aur_pkgs/MyRepo.db.tar '{}' ';'
$ GNUPGHOME=/home/build/signing_gpg gpg --detach-sign /home/build/aur_pkgs/MyRepo.db.tar</span></code></pre></div>
