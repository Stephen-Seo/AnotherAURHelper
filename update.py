#!/usr/bin/env python3

import os
import stat
import sys
import argparse
import subprocess
import re
from packaging import version
import atexit
import glob
import toml
import datetime
import time
import shutil
import getpass
import tempfile

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
SUDO_PROC = False
AUR_GIT_REPO_PATH = "https://aur.archlinux.org"
AUR_GIT_REPO_PATH_TEMPLATE = AUR_GIT_REPO_PATH + "/{}.git"
global GLOBAL_LOG_FILE
GLOBAL_LOG_FILE = "log.txt"
DEFAULT_EDITOR = "/usr/bin/nano"


def log_print(string):
    print(string)
    with open(GLOBAL_LOG_FILE, "a", encoding="utf-8") as lf:
        print(string, file=lf)


def ensure_pkg_dir_exists(pkg, pkg_state):
    log_print('Checking that dir for "{}" exists...'.format(pkg))
    pkgdir = os.path.join(pkg_state['dirs'], pkg)
    if os.path.isdir(pkgdir):
        log_print('Dir for "{}" exists.'.format(pkg))
        return True
    elif os.path.exists(pkgdir):
        log_print('"{}" exists but is not a dir'.format(pkgdir))
        return False
    elif "repo_path" not in pkg_state[pkg]:
        pkg_state[pkg]["repo_path"] = AUR_GIT_REPO_PATH_TEMPLATE.format(pkg)
        try:
            subprocess.run(
                ["git", "clone", pkg_state[pkg]["repo_path"], pkgdir],
                check=True,
            )
        except subprocess.CalledProcessError:
            log_print(
                'ERROR: Failed to git clone "{}" (tried repo path "{}")'.format(
                    pkgdir, pkg_state[pkg]["repo_path"]
                )
            )
            return False
        log_print('Created dir for "{}".'.format(pkg))
        return True
    elif pkg_state[pkg]["repo_path"] == "NO_REPO":
        log_print('"{}" does not exist, but NO_REPO specified for repo_path')
        return False


def update_pkg_dir(pkg, state):
    log_print('Making sure pkg dir for "{}" is up to date...'.format(pkg))

    pkgdir = os.path.join(state['dirs'], pkg)
    # fetch all
    try:
        subprocess.run(
            ["git", "fetch", "-p", "--all"],
            check=True,
            cwd=pkgdir,
        )
    except subprocess.CalledProcessError:
        log_print(
            'ERROR: Failed to update pkg dir of "{}" (fetching).'.format(pkg)
        )
        return False, False

    # get remotes
    remotes = []
    try:
        result = subprocess.run(
            ["git", "remote"],
            check=True,
            cwd=pkgdir,
            capture_output=True,
            encoding="UTF-8",
        )
        remotes = result.stdout.split(sep="\n")
    except subprocess.CalledProcessError:
        log_print(
            'ERROR: Failed to update pkg dir of "{}" (getting remotes).'.format(
                pkg
            )
        )
        return False, False
    remotes = list(filter(lambda s: len(s) > 0, remotes))
    if len(remotes) == 0:
        log_print(
            'ERROR: Failed to update pkg dir of "{}" (getting remotes).'.format(
                pkg
            )
        )
        return False, False

    # get remote that current branch is tracking
    selected_remote = ""
    try:
        result = subprocess.run(
            ["git", "status", "-sb", "--porcelain"],
            check=True,
            cwd=pkgdir,
            capture_output=True,
            encoding="UTF-8",
        )
        for remote in remotes:
            if (
                len(remote.strip()) > 0
                and result.stdout.find(remote.strip()) != -1
            ):
                selected_remote = remote.strip()
                break
    except subprocess.CalledProcessError:
        log_print(
            'ERROR: Failed to update pkg dir of "{}" (getting branch\'s remote).'.format(
                pkg
            )
        )
        return False, False
    if len(selected_remote) == 0:
        log_print(
            'ERROR: Failed to update pkg dir of "{}" (getting branch\'s remote).'.format(
                pkg
            )
        )
        return False, False

    # get hash of current branch
    current_branch_hash = ""
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=format:%H"],
            check=True,
            cwd=pkgdir,
            capture_output=True,
            encoding="UTF-8",
        )
        current_branch_hash = result.stdout.strip()
    except subprocess.CalledProcessError:
        log_print(
            'ERROR: Failed to update pkg dir of "{}" (getting current branch\'s hash).'.format(
                pkg
            )
        )
        return False, False
    if len(current_branch_hash.strip()) == 0:
        log_print(
            'ERROR: Failed to update pkg dir of "{}" (getting current branch\'s hash).'.format(
                pkg
            )
        )
        return False, False

    # get hash of remote branch
    remote_branch_hash = ""
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=format:%H", selected_remote],
            check=True,
            cwd=pkgdir,
            capture_output=True,
            encoding="UTF-8",
        )
        remote_branch_hash = result.stdout.strip()
    except subprocess.CalledProcessError:
        log_print(
            'ERROR: Failed to update pkg dir of "{}" (getting remote branch\'s hash).'.format(
                pkg
            )
        )
        return False, False
    if len(remote_branch_hash.strip()) == 0:
        log_print(
            'ERROR: Failed to update pkg dir of "{}" (getting remote branch\'s hash).'.format(
                pkg
            )
        )
        return False, False

    # update current branch if not same commit
    if current_branch_hash != remote_branch_hash:
        try:
            subprocess.run(
                ["git", "pull"], check=True, cwd=pkgdir
            )
        except subprocess.CalledProcessError:
            try:
                subprocess.run(
                    ["git", "checkout", "--", "*"],
                    check=True,
                    cwd=pkgdir,
                )
                subprocess.run(
                    ["git", "pull"],
                    check=True,
                    cwd=pkgdir,
                )
            except subprocess.CalledProcessError:
                log_print(
                    'ERROR: Failed to update pkg dir of "{}".'.format(pkg)
                )
                return False, False
    elif state[pkg]["skip_branch_up_to_date"]:
        log_print(f'"{pkg}" is up to date')
        return True, True
    log_print('Updated pkg dir for "{}"'.format(pkg))
    return True, False


def check_pkg_build(pkg, state, editor):
    """Returns "ok", "not_ok", "abort", or "force_build"."""
    pkgdir = os.path.join(state['dirs'], pkg)
    log_print('Checking PKGBUILD for "{}"...'.format(pkg))
    try:
        subprocess.run(
            [editor, "PKGBUILD"], check=True, cwd=pkgdir
        )
    except subprocess.CalledProcessError:
        log_print('ERROR: Failed checking PKGBUILD for "{}"'.format(pkg))
        return "abort"
    while True:
        log_print(
            "PKGBUILD okay? [Y/n/c(heck again)/a(bort)/f(orce build)/b(ack)]"
        )
        user_input = sys.stdin.buffer.readline().decode().strip().lower()
        if user_input == "y" or len(user_input) == 0:
            log_print("User decided PKGBUILD is ok")
            return "ok"
        elif user_input == "n":
            log_print("User decided PKGBUILD is not ok")
            return "not_ok"
        elif user_input == "c":
            log_print("User will check PKGBUILD again")
            return check_pkg_build(pkg, state, editor)
        elif user_input == "a":
            return "abort"
        elif user_input == "f":
            return "force_build"
        elif user_input == "b":
            return "back"
        else:
            log_print("ERROR: User gave invalid input...")
            continue


def check_pkg_version(pkg, pkg_state, repo, force_check_srcinfo):
    """Returns "fail", "install", or "done"."""
    status, current_epoch, current_version = get_pkg_current_version(
        pkg, pkg_state, repo
    )
    if status != "fetched":
        return status
    elif current_version is None:
        log_print(
            'ERROR: Failed to get version from package "{}".'.format(
                pkg_state[pkg]["pkg_name"]
            )
        )
        return "fail"
    log_print(
        'Got version "{}:{}" for installed pkg "{}"'.format(
            current_epoch if current_epoch is not None else "0",
            current_version,
            pkg_state[pkg]["pkg_name"],
        )
    )

    return get_srcinfo_check_result(
        current_epoch, current_version, pkg, force_check_srcinfo, pkg_state
    )


def get_srcinfo_version(pkg, state):
    """Returns (success_bool, pkgepoch, pkgver, pkgrel)"""
    if not os.path.exists(os.path.join(state['dirs'], pkg, ".SRCINFO")):
        log_print(f'ERROR: .SRCINFO does not exist for pkg "{pkg}"')
        return False, None, None, None
    pkgver_reprog = re.compile("^\\s*pkgver\\s*=\\s*([a-zA-Z0-9._+-]+)\\s*$")
    pkgrel_reprog = re.compile("^\\s*pkgrel\\s*=\\s*([0-9.]+)\\s*$")
    pkgepoch_reprog = re.compile("^\\s*epoch\\s*=\\s*([0-9]+)\\s*$")
    pkgver = ""
    pkgrel = ""
    pkgepoch = ""
    with open(
        os.path.join(state['dirs'], pkg, ".SRCINFO"), encoding="UTF-8"
    ) as fo:
        line = fo.readline()
        while len(line) > 0:
            pkgver_result = pkgver_reprog.match(line)
            pkgrel_result = pkgrel_reprog.match(line)
            pkgepoch_result = pkgepoch_reprog.match(line)
            if pkgver_result:
                pkgver = pkgver_result.group(1)
            elif pkgrel_result:
                pkgrel = pkgrel_result.group(1)
            elif pkgepoch_result:
                pkgepoch = pkgepoch_result.group(1)
            line = fo.readline()
    return True, pkgepoch, pkgver, pkgrel


def get_pkgbuild_version(pkg, force_check_srcinfo, state):
    """Returns (success, epoch, version, release)"""
    pkgdir = os.path.join(state['dirs'], pkg)
    log_print(f'Getting version of "{pkg}"...')
    while True and not force_check_srcinfo:
        log_print("Use .SRCINFO or directly parse PKGBUILD?")
        user_input = input("1 for .SRCINFO, 2 for PKGBUILD > ")
        if user_input == "1" or user_input == "2":
            break
    # TODO support split packages
    if force_check_srcinfo or user_input == "1":
        srcinfo_fetch_success, pkgepoch, pkgver, pkgrel = get_srcinfo_version(
            pkg, state
        )
        if not srcinfo_fetch_success:
            log_print("ERROR: Failed to get pkg info from .SRCINFO")
            return False, None, None, None
    elif user_input == "2":
        try:
            log_print(
                'Running "makepkg --nobuild" to ensure pkgver in PKGBUILD is updated...'
            )
            subprocess.run(
                ["makepkg", "-c", "--nobuild", "-s", "-r"],
                check=True,
                cwd=pkgdir,
            )
        except subprocess.CalledProcessError:
            log_print(
                'ERROR: Failed to run "makepkg --nobuild" in "{}".'.format(
                    pkg
                )
            )
            if os.path.exists(os.path.join(pkgdir, "src")):
                shutil.rmtree(os.path.join(pkgdir, "src"))
            return False, None, None, None

        if os.path.exists(os.path.join(pkgdir, "src")):
            shutil.rmtree(os.path.join(pkgdir, "src"))
        pkgepoch = ""
        pkgver = ""
        pkgrel = ""

        # TODO maybe sandbox sourcing the PKGBUILD
        pkgbuild_output = subprocess.run(
            [
                "bash",
                "-c",
                f"source {os.path.join(pkgdir, 'PKGBUILD')}; echo \"pkgver=$pkgver\"; echo \"pkgrel=$pkgrel\"; echo \"epoch=$epoch\"",
            ],
            capture_output=True,
            text=True,
        )
        output_ver_re = re.compile(
            "^pkgver=([a-zA-Z0-9._+-]+)\\s*$", flags=re.M
        )
        output_rel_re = re.compile("^pkgrel=([0-9.]+)\\s*$", flags=re.M)
        output_epoch_re = re.compile("^epoch=([0-9]+)\\s*$", flags=re.M)

        match = output_ver_re.search(pkgbuild_output.stdout)
        if match:
            pkgver = match.group(1)
        match = output_rel_re.search(pkgbuild_output.stdout)
        if match:
            pkgrel = match.group(1)
        match = output_epoch_re.search(pkgbuild_output.stdout)
        if match:
            pkgepoch = match.group(1)
    else:
        log_print("ERROR: Unreachable code")
        return False, None, None, None

    if len(pkgepoch) == 0:
        pkgepoch = None
    if len(pkgver) == 0:
        pkgver = None
    if len(pkgrel) == 0:
        pkgrel = None

    if pkgver is not None and pkgrel is not None:
        return True, pkgepoch, pkgver, pkgrel
    else:
        log_print(
            'ERROR: Failed to get PKGBUILD version of "{}".'.format(pkg)
        )
        return False, None, None, None


def get_srcinfo_check_result(
    current_epoch, current_version, pkg, force_check_srcinfo, state
):
    ver_success, pkgepoch, pkgver, pkgrel = get_pkgbuild_version(
        pkg, force_check_srcinfo, state
    )
    if ver_success:
        if current_epoch is None and pkgepoch is not None:
            log_print(
                'Current installed version of "{}" is out of date (missing epoch).'.format(
                    pkg_state[pkg]["pkg_name"]
                )
            )
            return "install"
        elif current_epoch is not None and pkgepoch is None:
            log_print(
                'Current installed version of "{}" is up to date (has epoch).'.format(
                    pkg_state[pkg]["pkg_name"]
                )
            )
            return "done"
        elif (
            current_epoch is not None
            and pkgepoch is not None
            and int(current_epoch) < int(pkgepoch)
        ):
            log_print(
                'Current installed version of "{}" is out of date (older epoch).'.format(
                    pkg_state[pkg]["pkg_name"]
                )
            )
            return "install"
        elif (
            pkgver is not None
            and pkgrel is not None
            and version.parse(current_version)
            < version.parse(pkgver + "-" + pkgrel)
        ):
            log_print(
                'Current installed version of "{}" is out of date (older version).'.format(
                    pkg_state[pkg]["pkg_name"]
                )
            )
            return "install"
        else:
            log_print(
                'Current installed version of "{}" is up to date.'.format(
                    pkg_state[pkg]["pkg_name"]
                )
            )
            return "done"
    else:
        log_print(
            'ERROR: Failed to get pkg_version of "{}"'.format(
                pkg_state[pkg]["pkg_name"]
            )
        )
        return "fail"


def get_pkg_current_version(pkg, pkg_state, repo):
    """Returns (status, epoch, version)"""
    log_print(
        'Checking version of installed pkg "{}"...'.format(
            pkg_state[pkg]["pkg_name"]
        )
    )
    current_epoch = None
    current_version = None
    try:
        result = subprocess.run(
            "tar -tf {} | grep '{}.*/$'".format(
                repo, pkg_state[pkg]["pkg_name"]
            ),
            check=True,
            capture_output=True,
            encoding="UTF-8",
            shell=True,
        )
        reprog = re.compile(
            "^{}-(?P<epoch>[0-9]+:)?(?P<version>[^-/: ]*-[0-9]+)/$".format(
                pkg_state[pkg]["pkg_name"]
            ),
            flags=re.MULTILINE,
        )
        reresult = reprog.search(result.stdout)
        if reresult:
            result_dict = reresult.groupdict()
            if not result_dict["epoch"] is None:
                current_epoch = result_dict["epoch"][:-1]
            if not result_dict["version"] is None:
                current_version = result_dict["version"]
        else:
            log_print(
                "ERROR: Failed to get current version from repo for package {}".format(
                    pkg_state[pkg]["pkg_name"]
                )
            )
            return "fail", None, None
    except subprocess.CalledProcessError:
        log_print("Package not found, assuming building first time.")
        return "install", None, None
    return "fetched", current_epoch, current_version


def get_sudo_privileges():
    global SUDO_PROC
    if not SUDO_PROC:
        log_print("sudo -v")
        try:
            subprocess.run(["sudo", "-v"], check=True)
        except subprocess.CalledProcessError:
            return False
        SUDO_PROC = subprocess.Popen(
            ["while true; do sudo -v; sleep 2m; done"], shell=True
        )
        atexit.register(cleanup_sudo, sudo_proc=SUDO_PROC)
        return True
    return True


def cleanup_sudo(sudo_proc):
    sudo_proc.terminate()


def create_executable_script(dest_filename, script_contents):
    tempf_name = "unknown"
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", delete=False
    ) as tempf:
        print(
            """#!/usr/bin/env python3
import os
import stat
import argparse

def create_executable_script(dest_filename, script_contents):
    with open(dest_filename, mode='w', encoding='utf-8') as f:
        f.write(script_contents)
    os.chmod(dest_filename, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR
                          | stat.S_IRGRP | stat.S_IXGRP
                          | stat.S_IROTH | stat.S_IXOTH)
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Set new file with execute permissions")
    parser.add_argument("--dest_filename")
    parser.add_argument("--script_contents")
    args = parser.parse_args()

    create_executable_script(args.dest_filename, args.script_contents)
""",
            file=tempf,
        )
        tempf_name = tempf.name
    try:
        subprocess.run(
            [
                "sudo",
                "/usr/bin/env",
                "python3",
                tempf_name,
                "--dest_filename",
                dest_filename,
                "--script_contents",
                script_contents,
            ],
            check=True,
        )
    except subprocess.CalledProcessError:
        log_print(
            f'ERROR: Failed to create executable script "{dest_filename}"'
        )
        return False
    return True


def setup_ccache(chroot):
    # set up ccache stuff
    try:
        subprocess.run(
            [
                "sudo",
                "sed",
                "-i",
                "/^BUILDENV=/s/!ccache/ccache/",
                f"{chroot}/root/etc/makepkg.conf",
            ],
            check=True,
        )
    except subprocess.CalledProcessError:
        log_print("ERROR: Failed to enable ccache in makepkg.conf")
        sys.exit(1)


def cleanup_ccache(chroot):
    # cleanup ccache stuff
    try:
        subprocess.run(
            [
                "sudo",
                "sed",
                "-i",
                "/^BUILDENV=/s/ ccache/ !ccache/",
                f"{chroot}/root/etc/makepkg.conf",
            ],
            check=True,
        )
    except subprocess.CalledProcessError:
        log_print("ERROR: Failed to disable ccache in makepkg.conf")
        sys.exit(1)


def setup_sccache(chroot):
    sccache_script = """#!/usr/bin/env sh
export PATH=${PATH/:\/usr\/local\/bin/}
/usr/bin/env sccache $(basename "$0") "$@"
"""
    if (
        not create_executable_script(
            f"{chroot}/root/usr/local/bin/gcc", sccache_script
        )
        or not create_executable_script(
            f"{chroot}/root/usr/local/bin/g++", sccache_script
        )
        or not create_executable_script(
            f"{chroot}/root/usr/local/bin/clang", sccache_script
        )
        or not create_executable_script(
            f"{chroot}/root/usr/local/bin/clang++", sccache_script
        )
        or not create_executable_script(
            f"{chroot}/root/usr/local/bin/rustc", sccache_script
        )
    ):
        log_print("ERROR: Failed to set up sccache wrapper scripts")
        sys.exit(1)


def cleanup_sccache(chroot):
    # cleanup sccache stuff
    try:
        subprocess.run(
            [
                "sudo",
                "rm",
                "-f",
                f"{chroot}/root/usr/local/bin/gcc",
                f"{chroot}/root/usr/local/bin/g++",
                f"{chroot}/root/usr/local/bin/clang",
                f"{chroot}/root/usr/local/bin/clang++",
                f"{chroot}/root/usr/local/bin/rustc",
            ],
            check=False,
        )
    except BaseException:
        log_print("WARNING: Failed to cleanup sccache files")


def update_pkg_list(
    pkgs,
    pkg_state,
    chroot,
    pkg_out_dir,
    repo,
    logs_dir,
    no_update,
    signing_gpg_dir,
    signing_gpg_key_fp,
    signing_gpg_pass,
    no_store,
):
    if not get_sudo_privileges():
        log_print("ERROR: Failed to get sudo privileges")
        sys.exit(1)
    if not no_update:
        log_print("Updating the chroot...")
        try:
            subprocess.run(
                ["arch-nspawn", "{}/root".format(chroot), "pacman", "-Syu"],
                check=True,
            )
        except subprocess.CalledProcessError:
            log_print("ERROR: Failed to update the chroot")
            sys.exit(1)
    for pkg in pkgs:
        log_print(f'Building "{pkg}"...')
        if "ccache_dir" in pkg_state[pkg]:
            cleanup_sccache(chroot)
            setup_ccache(chroot)
        else:
            cleanup_ccache(chroot)
            if "sccache_dir" in pkg_state[pkg]:
                setup_sccache(chroot)
            else:
                cleanup_sccache(chroot)

        command_list = [
            "makechrootpkg",
            "-c",
            "-r",
            chroot,
        ]
        post_command_list = [
            "--",
            "--syncdeps",
            "--noconfirm",
            "--log",
            "--holdver",
        ]
        for dep in pkg_state[pkg]["other_deps"]:
            dep_fullpath = get_latest_pkg(dep, "/var/cache/pacman/pkg")
            if not dep_fullpath:
                log_print('ERROR: Failed to get dep "{}"'.format(dep))
                sys.exit(1)
            command_list.insert(1, "-I")
            command_list.insert(2, dep_fullpath)
        for aur_dep in pkg_state[pkg]["aur_deps"]:
            aur_dep_fullpath = get_latest_pkg(aur_dep, pkg_out_dir)
            if not aur_dep_fullpath:
                log_print('ERROR: Failed to get aur_dep "{}"'.format(aur_dep))
                sys.exit(1)
            command_list.insert(1, "-I")
            command_list.insert(2, aur_dep_fullpath)
        if "ccache_dir" in pkg_state[pkg]:
            command_list.insert(1, "-d")
            command_list.insert(2, f'{pkg_state[pkg]["ccache_dir"]}:/ccache')
            post_command_list.insert(1, "CCACHE_DIR=/ccache")
        elif "sccache_dir" in pkg_state[pkg]:
            command_list.insert(1, "-d")
            command_list.insert(2, f'{pkg_state[pkg]["sccache_dir"]}:/sccache')
            post_command_list.insert(1, "SCCACHE_DIR=/sccache")
            post_command_list.insert(
                2, f'SCCACHE_CACHE_SIZE={pkg_state[pkg]["sccache_cache_size"]}'
            )
            post_command_list.insert(3, "RUSTC_WRAPPER=/usr/bin/sccache")
        nowstring = datetime.datetime.now(datetime.timezone.utc).strftime(
            "%Y-%m-%d_%H-%M-%S_%Z"
        )
        # log_print(f"Using command list: {command_list + post_command_list}") # DEBUG
        with open(
            os.path.join(logs_dir, "{}_stdout_{}".format(pkg, nowstring)),
            "w",
        ) as log_stdout, open(
            os.path.join(logs_dir, "{}_stderr_{}".format(pkg, nowstring)),
            "w",
        ) as log_stderr:
            try:
                subprocess.run(
                    command_list + post_command_list,
                    check=True,
                    cwd=pkgdir,
                    stdout=log_stdout,
                    stderr=log_stderr,
                )
            except subprocess.CalledProcessError:
                log_print(
                    'ERROR: Failed to build pkg "{}" in chroot'.format(pkg)
                )
                pkg_state[pkg]["build_status"] = "fail"
                continue

        if no_store:
            pkg_state[pkg]["build_status"] = "success"
            continue

        pkg_list = glob.glob(os.path.join(SCRIPT_DIR, pkg, "*.pkg.tar*"))

        log_print("Signing package...")
        for gpkg in pkg_list:
            try:
                command_list = [
                    "gpg",
                    "--batch",
                    "--passphrase-fd",
                    "0",
                    "--pinentry-mode",
                    "loopback",
                    "--default-key",
                    signing_gpg_key_fp,
                    "--detach-sign",
                    gpkg,
                ]
                subprocess.run(
                    command_list,
                    check=True,
                    cwd=os.path.join(SCRIPT_DIR, pkg),
                    input=signing_gpg_pass,
                    text=True,
                    env={"GNUPGHOME": signing_gpg_dir},
                )
            except subprocess.CalledProcessError:
                log_print(f'ERROR: Failed to sign pkg "{pkg}"')

        log_print("Adding built pkgs to repo...")
        try:
            command_list = ["repo-add", repo]
            for gpkg in pkg_list:
                command_list.append(gpkg)
            subprocess.run(command_list, check=True)
        except subprocess.CalledProcessError:
            log_print(
                'ERROR: Failed to add built pkg(s) "{}" to repo.'.format(pkg)
            )
            pkg_state[pkg]["build_status"] = "add_fail"
            continue

        log_print(f'Signing "{repo}"...')
        try:
            subprocess.run(
                [
                    "/usr/bin/rm",
                    "-f",
                    str(os.path.join(pkg_out_dir, f"{repo}.sig")),
                ]
            )
            subprocess.run(
                [
                    "/usr/bin/gpg",
                    "--batch",
                    "--passphrase-fd",
                    "0",
                    "--pinentry-mode",
                    "loopback",
                    "--default-key",
                    signing_gpg_key_fp,
                    "--detach-sign",
                    str(os.path.join(pkg_out_dir, f"{repo}")),
                ],
                check=True,
                input=signing_gpg_pass,
                text=True,
                env={"GNUPGHOME": signing_gpg_dir},
            )
            repo_sig_name = f"{repo}.sig"
            if repo_sig_name.rfind("/") != -1:
                repo_sig_name = repo_sig_name.rsplit(sep="/", maxsplit=1)[1]
            subprocess.run(
                [
                    "/usr/bin/ln",
                    "-sf",
                    repo_sig_name,
                    str(os.path.join(pkg_out_dir, f"{repo}")).removesuffix(
                        ".tar"
                    )
                    + ".sig",
                ]
            )
        except subprocess.CalledProcessError:
            log_print(f'WARNING: Failed to sign "{repo}"')

        pkg_state[pkg]["build_status"] = "success"

        log_print("Moving pkg to pkgs directory...")
        for f in pkg_list:
            log_print(f'Moving "{f}"...')
            os.rename(f, os.path.join(pkg_out_dir, os.path.basename(f)))
            sig_name = f + ".sig"
            if os.path.exists(sig_name):
                log_print(f'Moving "{sig_name}"...')
                os.rename(
                    sig_name,
                    os.path.join(pkg_out_dir, os.path.basename(sig_name)),
                )

    for pkg in pkgs:
        log_print(f'"{pkg}" status: {pkg_state[pkg]["build_status"]}')


def get_latest_pkg(pkg, cache_dir):
    globbed = glob.glob(os.path.join(cache_dir, pkg + "*"))
    if len(globbed) > 0:
        globbed.sort()
        reprog = re.compile(
            ".*"
            + pkg
            + "-[0-9a-zA-Z.+_:]+-[0-9a-zA-Z.+_]+-(any|x86_64).pkg.tar.(xz|gz|zst)$"
        )
        result = list(filter(lambda x: reprog.match(x), globbed))
        if len(result) == 0:
            return None
        else:
            return result[-1]
    else:
        return None


def confirm_result(pkg, state_result):
    """Returns "continue", "recheck", "force_build", or "abort"."""
    while True:
        log_print(
            'Got "{}" for pkg "{}", action: [C(ontinue), r(echeck), f(orce build),\
 s(kip), b(ack) a(abort)]'.format(
                state_result, pkg
            )
        )
        user_input = sys.stdin.buffer.readline().decode().strip().lower()
        if user_input == "c" or len(user_input) == 0:
            return "continue"
        elif user_input == "r":
            return "recheck"
        elif user_input == "f":
            return "force_build"
        elif user_input == "s":
            return "skip"
        elif user_input == "b":
            return "back"
        elif user_input == "a":
            return "abort"
        else:
            log_print("Got invalid input")
            continue


def print_state_info_and_get_update_list(pkg_state):
    to_update = []
    log_print("package state:")
    for (pkg_name, pkg_dict) in pkg_state.items():
        if "state" in pkg_dict:
            log_print(f"    {pkg_name:40}: {pkg_dict['state']}")
            if pkg_dict["state"] == "install":
                to_update.append(pkg_name)
        else:
            log_print(f"    {pkg_name:40}: not reached")
    return to_update


def test_gpg_passphrase(signing_gpg_dir, signing_key_fp, passphrase):
    with tempfile.NamedTemporaryFile() as tempnf:
        tempnf.write(b"Test file content")
        tempnf.flush()
        try:
            subprocess.run(
                [
                    "gpg",
                    "--batch",
                    "--passphrase-fd",
                    "0",
                    "--pinentry-mode",
                    "loopback",
                    "--default-key",
                    signing_key_fp,
                    "--detach-sign",
                    tempnf.name,
                ],
                check=True,
                input=passphrase,
                text=True,
                env={"GNUPGHOME": signing_gpg_dir},
            )
            os.remove(tempnf.name + ".sig")
        except subprocess.CalledProcessError:
            log_print("ERROR: Failed to sign test file with gpg")
            return False
    log_print("Verified passphrase works by signing dummy test file")
    return True


if __name__ == "__main__":
    editor = None
    parser = argparse.ArgumentParser(description="Update AUR pkgs")
    parser.add_argument(
        "--config", help="Info and pkg(s) to update in a .toml config"
    )
    parser.add_argument(
        "-p", "--pkg", action="append", help="Pkg(s) to update", metavar="pkg"
    )
    parser.add_argument(
        "--no-skip",
        action="append",
        help="Pkg(s) to not skip if up to date",
        metavar="noskip",
    )
    parser.add_argument(
        "-e",
        "--editor",
        default=None,
        help="editor to use when viewing PKGBUILDs",
        metavar="editor",
    )
    parser.add_argument("--chroot", help="Chroot to build in")
    parser.add_argument("--pkg-dir", help="Destination for built pkgs")
    parser.add_argument("--repo", help="repository tar file")
    parser.add_argument("--gpg-dir", help="gpg home for checking signatures")
    parser.add_argument("--logs-dir", help="dir to put logs")
    parser.add_argument(
        "--no-update", help="Do not update chroot", action="store_true"
    )
    parser.add_argument("--signing-gpg-dir", help="gpg home for signing key")
    parser.add_argument(
        "--signing-gpg-key-fp", help="gpg fingerprint for signing key"
    )
    parser.add_argument(
        "--no-store",
        action="store_true",
        help="Don't sign built package and add to repo",
    )
    args = parser.parse_args()

    if (
        args.pkg
        and not args.config
        and (
            not args.chroot
            or not args.pkg_dir
            or not args.repo
            or not args.gpg_dir
            or not args.logs_dir
        )
    ):
        log_print(
            "ERROR: --pkg requires also --chroot, --pkg_dir, --repo, --gpg_dir, and --logs_dir"
        )
        sys.exit(1)

    pkg_state = {}
    other_state = {}
    if args.pkg and not args.config:
        for pkg in args.pkg:
            pkg_state[pkg] = {}
            pkg_state[pkg]["aur_deps"] = []
        other_state['chroot'] = args.chroot
        other_state['pkgdir'] = args.pkg_dir
        other_state['repo'] = args.repo
        other_state['gpg_home'] = args.gpg_dir
        other_state['logs_dir'] = args.logs_dir
        if args_logs_dir is not None:
            GLOBAL_LOG_FILE = args_logs_dir + "/update.py_logs"
            log_print(
                f"{datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M %Z')}"
            )
            log_print(f"Set GLOBAL_LOG_FILE to {GLOBAL_LOG_FILE}")
        other_state['signing_gpg_dir'] = args.signing_gpg_dir
        other_state['signing_gpg_key_fp'] = args.signing_gpg_key_fp
        if args_signing_gpg_key_fp is None:
            log_print(
                'ERROR: Signing key fingerprint "signing_gpg_key_fp" not present in config'
            )
            sys.exit(1)
        if args_signing_gpg_dir is not None and not args.no_store:
            other_state['signing_gpg_pass'] = getpass.getpass("gpg signing key pass: ")
            if not test_gpg_passphrase(
                other_state['signing_gpg_dir'],
                other_state['signing_gpg_key_fp'],
                other_state['signing_gpg_pass'],
            ):
                sys.exit(1)
    elif args.config:
        d = toml.load(args.config)
        for entry in d["entry"]:
            pkg_state[entry["name"]] = {}
            if "aur_deps" in entry:
                pkg_state[entry["name"]]["aur_deps"] = entry["aur_deps"]
            else:
                pkg_state[entry["name"]]["aur_deps"] = []
            if "repo_path" in entry:
                pkg_state[entry["name"]]["repo_path"] = entry["repo_path"]
            if "pkg_name" in entry:
                pkg_state[entry["name"]]["pkg_name"] = entry["pkg_name"]
            else:
                pkg_state[entry["name"]]["pkg_name"] = entry["name"]
            if "ccache_dir" in entry:
                pkg_state[entry["name"]]["ccache_dir"] = entry["ccache_dir"]
            elif "sccache_dir" in entry:
                pkg_state[entry["name"]]["sccache_dir"] = entry["sccache_dir"]
                if "sccache_cache_size" in entry:
                    pkg_state[entry["name"]]["sccache_cache_size"] = entry[
                        "sccache_cache_size"
                    ]
                else:
                    pkg_state[entry["name"]]["sccache_cache_size"] = "5G"
            if "other_deps" in entry:
                pkg_state[entry["name"]]["other_deps"] = entry["other_deps"]
            else:
                pkg_state[entry["name"]]["other_deps"] = []
            if "skip_branch_up_to_date" in entry and not (
                not args.no_skip is None and entry["name"] in args.no_skip
            ):
                pkg_state[entry["name"]]["skip_branch_up_to_date"] = True
            else:
                pkg_state[entry["name"]]["skip_branch_up_to_date"] = False
        other_state['chroot'] = d["chroot"]
        other_state['pkgdir'] = d["pkg_dir"]
        other_state['repo'] = d["repo"]
        other_state['gpg_home'] = d["gpg_dir"]
        other_state['logs_dir'] = d["logs_dir"]
        ohter_state['dirs'] = d["dirs_dir"]
        if args_logs_dir is not None:
            GLOBAL_LOG_FILE = args_logs_dir + "/update.py_logs"
            log_print(
                f"{datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M %Z')}"
            )
            log_print(f"Set GLOBAL_LOG_FILE to {GLOBAL_LOG_FILE}")
        if args.pkg:
            to_keep = [args_pkg for args_pkg in args.pkg]
            removal = []
            for existing in pkg_state.keys():
                if existing in to_keep:
                    pass
                else:
                    removal.append(existing)
            for to_remove in removal:
                del pkg_state[to_remove]

        if "signing_gpg_dir" in d and not args.no_store:
            args_signing_gpg_dir = d["signing_gpg_dir"]
            args_signing_gpg_key_fp = d["signing_gpg_key_fp"]
            args_signing_gpg_pass = getpass.getpass("gpg signing key pass: ")
            if not test_gpg_passphrase(
                args_signing_gpg_dir,
                args_signing_gpg_key_fp,
                args_signing_gpg_pass,
            ):
                sys.exit(1)
        if "editor" in d:
            editor = d["editor"]
    else:
        log_print('ERROR: At least "--config" or "--pkg" must be specified')
        sys.exit(1)

    if args.editor is not None:
        editor = args.editor

    if editor is None:
        editor = DEFAULT_EDITOR

    os.putenv("CHROOT", os.path.realpath(args_chroot))
    os.putenv("GNUPGHOME", os.path.realpath(args_gpg_home))
    if not os.path.exists(args_logs_dir):
        os.makedirs(args_logs_dir)
    elif not os.path.isdir(args_logs_dir):
        log_print(
            'ERROR: logs_dir "{}" must be a directory'.format(args_logs_dir)
        )
        sys.exit(1)
    pkg_list = [temp_pkg_name for temp_pkg_name in pkg_state.keys()]
    i = 0
    while i < len(pkg_list):
        going_back = False
        if not ensure_pkg_dir_exists(pkg_list[i], pkg_state):
            print_state_info_and_get_update_list(pkg_state)
            sys.exit(1)
        skip = False
        if (
            "repo_path" not in pkg_state[pkg_list[i]]
            or pkg_state[pkg_list[i]]["repo_path"] != "NO_REPO"
        ):
            update_pkg_dir_count = 0
            update_pkg_dir_success = False
            while update_pkg_dir_count < 5:
                (success, skip_on_same_ver) = update_pkg_dir(
                    pkg_list[i], pkg_state
                )
                if success:
                    update_pkg_dir_success = True
                    break
                else:
                    time.sleep(1)
                    update_pkg_dir_count += 1
            if not update_pkg_dir_success:
                log_print('Failed to update pkg dir for "{}"', pkg_list[i])
                print_state_info_and_get_update_list(pkg_state)
                sys.exit(1)
        if skip_on_same_ver:
            check_pkg_version_result = check_pkg_version(
                pkg_list[i], pkg_state, args_repo, True
            )
            if check_pkg_version_result != "install":
                log_print(f"Pkg {pkg_list[i]} is up to date, skipping...")
                pkg_state[pkg_list[i]]["state"] = "up to date"
                i += 1
                continue
        check_pkg_build_result = check_pkg_build(pkg_list[i], pkg_state, editor)
        if check_pkg_build_result == "ok":
            pass
        elif check_pkg_build_result == "not_ok":
            pkg_state[pkg_list[i]]["state"] = "skip"
            i += 1
            continue
        elif check_pkg_build_result == "force_build":
            pkg_state[pkg_list[i]]["state"] = "install"
            i += 1
            continue
        elif check_pkg_build_result == "invalid":
            continue
        elif check_pkg_build_result == "back":
            if i > 0:
                i -= 1
            continue
        else:  # check_pkg_build_result == "abort":
            print_state_info_and_get_update_list(pkg_state)
            sys.exit(1)
        while True:
            if skip_on_same_ver and check_pkg_version_result is not None:
                state_result = check_pkg_version_result
            else:
                state_result = check_pkg_version(
                    pkg_list[i], pkg_state, args_repo, False
                )
            confirm_result_result = confirm_result(pkg_list[i], state_result)
            if confirm_result_result == "continue":
                pkg_state[pkg_list[i]]["state"] = state_result
                break
            elif confirm_result_result == "recheck":
                check_pkg_version_result = None
                continue
            elif confirm_result_result == "force_build":
                pkg_state[pkg_list[i]]["state"] = "install"
                break
            elif confirm_result_result == "skip":
                pkg_state[pkg_list[i]]["state"] = "skip"
                break
            elif confirm_result_result == "back":
                if i > 0:
                    i -= 1
                going_back = True
                break
            else:  # confirm_result_result == "abort"
                print_state_info_and_get_update_list(pkg_state)
                sys.exit(1)
        if going_back:
            pass
        else:
            i += 1

    log_print("Showing current actions:")
    pkgs_to_update = print_state_info_and_get_update_list(pkg_state)
    if len(pkgs_to_update) > 0:
        log_print("Continue? [Y/n]")
        user_input = sys.stdin.buffer.readline().decode().strip().lower()
        if user_input == "y" or len(user_input) == 0:
            if args.no_update:
                log_print("Updating (without updating chroot)...")
            else:
                log_print("Updating...")
            update_pkg_list(
                pkgs_to_update,
                pkg_state,
                os.path.realpath(args_chroot),
                os.path.realpath(args_pkg_dir),
                os.path.realpath(args_repo),
                os.path.realpath(args_logs_dir),
                args.no_update,
                "" if args.no_store else args_signing_gpg_dir,
                "" if args.no_store else args_signing_gpg_key_fp,
                "" if args.no_store else args_signing_gpg_pass,
                args.no_store,
            )
        else:
            log_print("Canceled.")
    else:
        log_print("No packages to update, done.")
