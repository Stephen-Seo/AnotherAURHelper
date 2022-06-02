# Another AUR Helper (incomplete)

AUR is the Arch User Repository, where anyone can upload a PKGBUILD and
supplementary sources to allow others to build their own packages for use in the
Arch Linux distribution.

I made an incomplete AUR Helper in Python, and decided to put it in a public
repository. It's messy, and it requires a significant amount of set-up, but it
works for me. It always builds in a CHROOT, and it lets the user check the
PKGBUILD (by default) prior to building. There is no automatic dependency
management. That must be done in the config. An example config is provided.

# Setting up the AUR Helper

The AUR Helper requires several things:

  - A CHROOT to build in
  - A "checking GNUPG" directory that contains the GPG public keys that will be
    checked when building the PKGBUILD
  - A "singing GNUPG" directory that contains the GPG private key that will sign
    the built packages and repository database.
  - SUDO privileges to be able to use `makechrootpkg`

## Dependencies

The `devtools` package is required.

The `python-packaging` and `python-toml` packages are required for the Python
script to run.

## Create the CHROOT

Use `/usr/bin/mkarchroot` to create your CHROOT in a directory.

    mkarchroot $HOME/mychroot base base-devel

You must refer to the CHROOT as `$HOME/mychroot` if you used the same name as in
the previous example.

## Set up the GNUPG dirs

### Checking GNUPG

Just create the directory anywhere, and store it in the `config.toml`. You must
manually add public keys to it if a package requires checking source files with
GNUPG.

    GNUPGHOME=$HOME/myCheckingGNUPGDir gpg --recv-keys A_DEV_KEYS_FINGERPRINT

### Signing GNUPG

You will need to set up a GPG public/private key pair. GNUPG always respects the
`GNUPGHOME` environment variable as the `.gnupg` dir, so set the variable first,
then set up your keys. The keys will be used to sign the packages you build and
the custom repository that stores the package metadata.

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