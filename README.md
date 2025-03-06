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

# Guide to setting this up with LXC

[This Github Pages website contains a detailed guide into setting up
AnotherAURHelper with LXC.](https://stephen-seo.github.io/AnotherAURHelper/setup_lxc/)

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

## Soft-lock if `sccache` is preinstalled in chroot

Apparently, some packages automatically use ccache/sccache if it is installed in
the chroot, and in some cases, causes a soft-lock during a build. It is
recommended to not have ccache/sccache preinstalled in the chroot and to just
let the aur-helper-script install it when necessary.

For example, when building `tenacity-git` with sccache preinstalled, the build
will hang after the final build step. Apparently, killing the running `sccache`
process stops the soft-lock in this case.

## Preloading ccache/sccache

This script expects ccache and sccache not to be installed in the chroot (for
reasons as mentioned in the previous section) and ccache or sccache will be
appended to a pkg's "other_deps" if a ccache or sccache directory is configured
for it.

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

Note that packages with this option enabled may fail to build if
`$HOME/.cargo/registry` and `$HOME/.cargo/git` does not exist for the user
running AnotherAURHelper.

## `is_timed` and `is_log_timed`

If `is_timed` is `true` in the config, then output logs are prepended with a
timestamp.

If `is_log_timed` is `true` in the config, then output build logs are prepended
with a timestamp.

## `only_check_SRCINFO` and `only_check_PKGBUILD`

These options can be set for a package entry to always check one or the other
(of .SRCINFO or PKGBUILD) so that the user does not have to pick.

    [[entry]]
    name = "ttf-clear-sans"
    only_check_SRCINFO = true

    [[entry]]
    name = "cpufetch-git"
    only_check_PKGBUILD = true

## `hash_compare_PKGBUILD`

This option can be set for a package entry to only check the PKGBUILD if the
PKGBUILD changed between the start of executing `update.py` and after the aur
package is git-pull'd from the AUR.

~~Note that this may cause a package's PKGBUILD to not be checked if the
PKGBUILD was fetched, then `update.py` was aborted and restarted again.~~

The sqlite database at the path specified by `persistent_state_db = ...` keeps
track of when a package's PKGBUILD was decided to be "ok" by the user. This
prevents a PKGBUILD that hasn't been checked to be skipped by this option.

    [[entry]]
    name = "glfw-git"
    hash_compare_PKGBUILD = true

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
