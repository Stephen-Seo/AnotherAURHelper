# config.toml settings

## Global Settings

    :::toml
    chroot = "/home/user/Downloads/chroot"

Location of the chroot.

    :::toml
    tmpfs = false

If set to true, creates a new directory, sets it up with tmpfs, and copies the
chroot to it (recommended to have +32GiB ram if this option is used).

    :::toml
    pkg_out_dir = "/home/user/pkgs_out"

The location to place built packages. Should be the same location for the
repository tar file.

    :::toml
    repo = "/home/user/pkgs_out/custom.db.tar"

The repository (tar) file. Change "custom" to any other name to change the name
of the repository

    :::toml
    clones_dir = "/home/user/Downloads/aur"

The location to place the AUR-package-git-clones. Each subdirectory in this
directory should have a PKGBUILD and .SRCINFO as each AUR package should have
these files.

    :::toml
    gpg_dir = "/home/user/gnupg_dir"

The location of the GNUPGHOME dir. This keeps track of gpg keys and is used to
verify sources within PKGBUILDs that use a gpg key. If a build fails due to an
"unknown gpg key", then one can do `GNUPGHOME=/home/user/gnupg_dir gpg
--recv-keys FINGERPRINT` or `GNUPGHOME=/home/user/gnupg_dir gpg --import <
pub_key_file` to save a signer's public key.

    :::toml
    logs_dir = "/home/user/Downloads/logs"

The directory to place all logs.

    :::toml
    signing_gpg_dir = "/home/user/signing_gnupg_dir"

The location to store the signing key used for every package and repo stored in
"pkg\_out\_dir" and "repo". It is recommended to only generate a "SC" key as
mentioned in the guide (--full-gen-key, RSA sign only or ECC sign only).

    :::toml
    signing_gpg_key_fp = "THE_GPG_KEY_FINGERPRINT"

A 40-character-long hexadecimal fingerprint of the signing key. This is
typically displayed using `GNUPGHOME=/home/user/signing_gnupg_dir gpg -K`. If
you want to use a subkey to sign the packages, then you can list/find them with
`GNUPGHOME=/home/user/signing_gnupg_dir gpg -K --with-subkey-fingerprint`.

    :::toml
    editor = "/usr/bin/vim"

The text editor to use when viewing PKGBUILDs or other files. It can be set to
`editor = "/usr/bin/nano"` or any other editor of your choosing.

    :::toml
    is_timed = true

If "is\_timed" is set to "true", then all printed logs will have a timestamp.
Note that the timestamps will be in UTC.

    :::toml
    is_log_timed = true

if "is\_log\_timed" is set to "true", then all saved logs will have a timestamp.
Note that the timestamps will be in UTC.

    :::toml
    log_limit = 1073741824

The log-file-size limit in bytes. The default is 1GiB.

    :::toml
    error_on_limit = true

If "error\_on\_limit" is "true", then the currently built package will be
aborted if its log file exceeds the size limit set by "log\_limit".

    :::toml
    datetime_in_local_time = true

If true, timestamps will be in localtime instead of UTC

    :::toml
    tz_force_offset_hours = -7
    tz_force_offset_minutes = 0

If set, forces the specified time offset when printing logs, regardless of the
option `datetime_in_local_time`.

    :::toml
    print_state_info_only_building_sigusr1 = true

If this option is set to "true", then only the packages that are to be built
will be logged when SIGUSR1 is received during building. Otherwise, all packages
listed in the config.toml will be printed with their status. Note that SIGUSR1
does not stop the build.

    :::toml
    persistent_state_db = "/home/user/aur_helper_state.db"

The path for AnotherAURHelper to create and use a sqlite database to help keep
track of things. The current use of it is to check if a PKGBUILD of a package
was previously determined to be "OK" and will therefore skip checking the
PKGBUILD depending on the per-package options.

    :::toml
    temporary_files_dir = "/home/user/aur_helper_temp_files"

The path for AnotherAURHelper to place temporary files. It is currently used to
keep a backup of "$HOME/.cargo/config.toml" which will write back to its
original location on program exit to ensure the config file remains exactly as
it was before any build starts.

## Per Package Settings

### Per Package Example

    :::toml
    [[entry]]
    name = "helix-git"
    pkg_name = "helix-git-package"
    repo_path = "https://aur.archlinux.org/helix-git"
    repo_branch = "master"
    skip_branch_up_to_date = false
    only_check_SRCINFO = false
    only_check_PKGBUILD = true
    hash_compare_PKGBUILD = true
    ccache_dir = "/home/user/ccache_dirs/helix_git_does_not_use_ccache"
    sccache_dir = "/home/user/sccache_dirs/helix_may_use_sccache"
    sccache_cache_size = "5G"
    sccache_rust_only = true
    link_cargo_registry = false
    full_link_cargo_registry = true
    aur_deps = [
        "wlroots-git",
        "sway-git"
    ]
    other_deps = [
        "xorg-xwayland",
        "stdman"
    ]

### Per Package Options Explanation

    :::toml
    name = "helix-git"

The "name" of the package. This is the name of the git clone directory of a
package. This is also the name used when cloning from https://aur.archlinux.org
.

    :::toml
    pkg_name = "helix-git-package"

The "informal" name of the package. Only used for logging about the package.
Defaults to "name" if unset.

    :::toml
    repo_path = "https://aur.archlinux.org/helix-git"

If set to `NO_REPO`, the software will not attempt to clone from
aur.archlinux.org. If unset, the default path
`https://aur.archlinux.org/{name}.git` will be used. If set, this path will be
used when cloning the repo for the first time.

    :::toml
    repo_branch = "master"

If `repo_branch` is set, then it will be the target branch when cloning for the
first time.

    :::toml
    skip_branch_up_to_date = false

Skips prompt for a package if it is already "up-to-date". A package is
"up-to-date" if the repository does not have a new commit.

    :::toml
    only_check_SRCINFO = false

Skips prompt for checking between SRCINFO or PKGBUILD and checks SRCINFO
directly.

    :::toml
    only_check_PKGBUILD = true

Skips prompt for checking between SRCINFO or PKGBUILD and checks PKGBUILD
directory.

    :::toml
    hash_compare_PKGBUILD = true

Skips checking PKGBUILD prompt with "editor" if the hash of the PKGBUILD on
start of AnotherAURHelper does not match the hash of the PKGBUILD after
`git pull`.

    :::toml
    ccache_dir = "/home/user/ccache_dirs/helix_git_does_not_use_ccache"

If "ccache\_dir" is specified, then ccache will be set up for the build and it
will be cached in the specified directory.

    :::toml
    sccache_dir = "/home/user/sccache_dirs/helix_may_use_sccache"

If "sccache\_dir" is specified, then sccache will be set up for the build and it
will be cached in the specified directory.

    :::toml
    sccache_cache_size = "5G"

Forces the sccache cache size to the given value. (Refer to sccache
documentation on environment variable SCCACHE\_CACHE\_SIZE for what values are
acceptable.)

    :::toml
    sccache_rust_only = true

Forces the use of sccache to be used only by the Rust compiler.

    :::toml
    link_cargo_registry = false

Binds "$HOME/.cargo/git" to "/build/.cargo/git" and "$HOME/.cargo/registry" to
"/build/.cargo/registry" in the chroot. This enables sharing of the host's cache
to the chroot's cache for Rust packages.

    :::toml
    full_link_cargo_registry = true

Binds "$HOME/.cargo" to "/build/.cargo" in the chroot. This enables sharing of
the host's cache to the chroot's cache for Rust packages. Note that if this is
used, then "$HOME/.cargo/config.toml" will be copied to a temporary directory,
and when AnotherAURHelper exits, the config.toml in the temporary directory is
copied back to prevent it being overwritten somehow during package building.

    :::toml
    aur_deps = [
        "wlroots-git",
        "sway-git"
    ]

Uses the "pkg\_out\_dir" and "repo" to install previously built AUR packages
specified by "aur\_deps". It is recommended to move the named dependencies
before this package in the config.toml so it always loads the latest built
version of it as AnotherAURHelper builds all packages in sequential order in
the config.toml.

    :::toml
    other_deps = [
        "xorg-xwayland",
        "stdman"
    ]

Like "aur\_deps", but for packages already available in the package
repositories.
