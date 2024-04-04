# Another AUR Helper (incomplete)

AUR is the Arch User Repository, where anyone can upload a PKGBUILD and
supplementary sources to allow others to build their own packages for use in the
Arch Linux distribution.

I made an incomplete AUR Helper in Python, and decided to put it in a public
repository. It's messy, and it requires a significant amount of set-up, but it
works for me. It always builds in a CHROOT, and it lets the user check the
PKGBUILD (by default) prior to building. There is no automatic dependency
management. That must be done in the config. An example config is provided.

Note that if a "install=\<filename\>" is specified in the PKGBUILD, then the
configured editor will also open the specified file once the PKGBUILD is
approved by the user. This check is necessary because such "install scripts"
define hooks that are run when the package is installed.

# Things to know before using the helper

## Security

Apparently `makechrootpkg` (provided by `devtools` pkg and used by this script)
sources PKGBUILD files directly, meaning that if a malicious PKGBUILD is
attempted to be built, it may cause an RCE kind of exploit with the current
user. Thus, it is recommended to run this script in a container (like Docker or
LXC) so that even if a malicious PKGBUILD is sourced, it will only affect the
container. Though if you do set up a container, you may have to set up a
directory mount to access the built packages.

## Soft-lock due to multiple possible dependencies

Sometimes if a package prompts a user to select between alternate package
dependencies, makechrootpkg will fail to select one by default (it will
constantly output "y" to stdin when a selection requires an integer). This
means you will need to check the logs as it is building a package to make sure
this kind of soft-lock doesn't happen. Use `tail -f LOG_FILE` for example. If
such a soft-lock happens, Ctrl-C the helper, and explicitly set a dependency in
the TOML config file in a "other\_deps" array for the package like so:

    [[entry]]
    name = "sway-git"
    aur_deps = [
        "wlroots-git",
        "swaybg-git"
    ]
    other_deps = [
        "mesa"
    ]

## Package stdout/stderr size limit

The possible issue of output logs filling up disk space is addressed with a
"log\_limit" config option. By default, if the output log file reaches the
limit, the compilation output is no longer logged to file in the logs dir.

Change "log\_limit" in the config to a value in bytes if the default of 1 GiB
is too little for your use case (if the size of your output logs extend past 1
GiB somehow).

### Error when reaching limit

"error\_on\_limit" can be set to true/false in the config. If set to true, then
the build will fail if the limit is reached. If set to false, then the build
will continue even if the limit is reached.

# Setting up the AUR Helper

The AUR Helper requires several things:

  - A CHROOT to build in.
  - A "checking GNUPG" directory that contains the GPG public keys that will be
    checked when building the PKGBUILD.
  - A "signing GNUPG" directory that contains the GPG private key that will sign
    the built packages and repository database.
  - SUDO privileges to be able to use `makechrootpkg`.
  - `/etc/pacman.conf` must be configured to use the custom repository's
    packages if `pacman -U` will not be used.

## Dependencies

The `devtools` package is required.

The `python-toml` package is required for the Python script to run.

## Create the CHROOT

Use `/usr/bin/mkarchroot` to create your CHROOT in a directory.

    mkarchroot $HOME/mychroot/root base base-devel ccache sccache cmake ninja

You must refer to the CHROOT as `$HOME/mychroot` if you used the same name as in
the previous example.

## Set up the GNUPG dirs

### Checking GNUPG

Just create the directory anywhere, and store it in the `config.toml`. You must
manually add public keys to it if a package requires checking source files with
GNUPG.

    GNUPGHOME=$HOME/myCheckingGNUPGDir gpg --recv-keys A_DEV_KEYS_FINGERPRINT

Note that gpg may not automatically create the GNUPGHOME directory.

### Signing GNUPG

You will need to set up a GPG public/private key pair. GNUPG always respects
the `GNUPGHOME` environment variable as the `.gnupg` dir, so set the variable
first, create the directory, then set up your keys. The keys will be used to
sign the packages you build and the custom repository that stores the package
metadata.

Set the `signing_gpg_key_fp` variable in the config to the output fingerprint
from of:

    GNUPGHOME=mySigningGNUPGDir gpg --fingerprint

Note that you must remove the spaces between each part of the fingerprint, like
in the example config.

Keep note of the password you store for this GNUPG key, as you will enter it
every time you use the Python script.

## Set up the config dir

See the `example_config.toml` for more configuration. It should be commented
enough for figuring out how to use it.

# Setting up the Repository

Create a directory for where you will store built packages and the repository.

The name of the repo must be similar to the `repo` specified in the config.

For example, if your repo's name is `MyAURRepo`, then `repo` should be set to
`.../MyAURRepo.db.tar`.

You must also create symlinks such that `MyAURRepo.db` points to
`MyAURRepo.db.tar` and `MyAURRepo.files` points to `MyAURRepo.files.tar`.

The Python script should automatically make a relative (not absolute) symlink to
`MyAURRepo.db.tar.sig` with the name `MyAURRepo.db.sig` after signing (which
should happen after each package is built and signed). Note the name doesn't
have to be `MyAURRepo`, but is based on the `repo` variable set in the config.

To use the repository, you can add an entry to your `/etc/pacman.conf` with the
following:

    [MyAURRepo]
    SigLevel = Required TrustedOnly
    Server = file:///home/MyAURRepoDirectory
    # Optionally set a file with `Server = ...` entries
    # Include = /etc/pacman.d/my_repo_server_list

Note that `SigLevel` is set expecting the `MyAURRepo.db` file to be signed (the
Python script usually signs the `.db` file after a package has been successfully
built).

# Making your system trust the new Repository

Export the public key from your `signingGPGDirectory`.

    GNUPGHOME=mySigningGNUPGDir gpg --export MySigningKeyName > $HOME/MySigningKey.pub

Use `pacman-key` to add and trust it.

    sudo pacman-key -a $HOME/MySigningKey.pub

First check that the name is unique:

    sudo pacman-key --finger MySigningKeyName

Then trust it:

    sudo pacman-key --lsign-key MySigningKeyName

After these steps, `pacman` should now trust the packages and repository signed
by the GPG key you set up.

# Using the AUR Helper

Typically, you will invoke:

    ./update.py --config my_config.toml

If you want to build in the CHROOT without updating the CHROOT, add the
`--no-update` flag.

If you want to check only specific packages in the list of packages in the
config use something like `-p <package-name>`. You can use `-p <package_name>`
multiple times if you want to check a handful of packages only.

If you want to not skip a package marked with `skip_branch_up_to_date` in the
config, then use `--no-skip <package-name>`, and the script will act as if
`skip_branch_up_to_date` was not specified for the named package.

When building, the script will not directly output to the terminal it is run in,
but rather appends to log files in the log directory specified in the config. To
see the output while building, you can use something like:

    tail -f $MY_LOG_DIR/google-chrome_stdout_2022-06-02_05-27-49_UTC

It may be helpful to periodically clear out the logs directory in between
invocations of the AUR Helper script.

It is recommended to use the script with a prepared config.

# Other Notes

~~By default, `makechrootpkg` does not verify integrity of files in the
PKGBUILD. Use the `makechrootpkg_noskipinteg.hook` to modify the
`makechrootpkg` script to not skip integrity checks.~~

`update.py` now does integrity checks before building with `makechrootpkg`. It
is no longer necessary to modify the `/usr/bin/makechrootpkg` because the
integrity checks are done separately.

If the hook was used previously, remove it from `/etc/pacman.d/hooks` and
reinstall `devtools`.

## `link_cargo_registry`

If you have `.cargo/registry` and `.cargo/git` in your home directory, and you
don't want to re-download the Rust registry every time you update a Rust
package, you can specify `link_cargo_registry = true` for a package in your
config (see `ion-git` in the `example_config.toml`) and that will bind-mount
these two directories into the chroot, which will share your local Rust cache
with the chroot.

    [[entry]]
    name = "ion-git"
    link_cargo_registry = true

## `is_timed` and `is_log_timed`

If `is_timed` is `true` in the config, then output logs are prepended with a
timestamp.

If `is_log_timed` is `true` in the config, then output build logs are prepended
with a timestamp.

## sccache and Rust

If using `sccache` causes a build error when building a package compiling Rust,
one may specify in the config to only wrap `rustc` and nothing else by
specifying `sccache_rust_only`:

    [[entry]]
    name = "helix-git"
    link_cargo_registry = true
    sccache_dir="/home/user/aur/sccache_helix-git"
    sccache_rust_only = true

## Signal Handling

The script is set up to handle `SIGINT` and `SIGUSR1`. `SIGINT` (Ctrl-C) will
print the known package list and status, and exit. `SIGUSR1` will also print
the known package list and status, but will not stop the script.
