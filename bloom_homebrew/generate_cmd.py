# Software License Agreement (BSD License)
#
# Copyright (c) 2013, Open Source Robotics Foundation, Inc.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#
#  * Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
#  * Redistributions in binary form must reproduce the above
#    copyright notice, this list of conditions and the following
#    disclaimer in the documentation and/or other materials provided
#    with the distribution.
#  * Neither the name of Open Source Robotics Foundation, Inc. nor
#    the names of its contributors may be used to endorse or promote
#    products derived from this software without specific prior
#    written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
# FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE
# COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
# INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
# BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN
# ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

from __future__ import print_function

import os
import sys
import traceback

from bloom.logging import debug
from bloom.logging import error
from bloom.logging import warning
from bloom.logging import fmt
from bloom.logging import info

try:
    from catkin_pkg.packages import find_packages
except ImportError:
    debug(traceback.format_exc())
    error("catkin_pkg was not detected, please install it.", exit=True)


formula_template = """\
# This formula is generated, you should not edit it directly.
require 'formula'

class @(ClassName) < Formula
  homepage '@(Homepage)'
  url '@(RepoUrl)', :tag => '@(ReleaseTag)'
  version '@(Version)'

  # source repos often contain more than one package... not sure if we can handle this
  #head '@(RepoUrl)', :branch => '@(DevelBranch)'

  # FIXEM: these are build depends
  @('\\n  '.join(BuildDepends))

  @('\\n  '.join(Depends))

  option 'with-debug-info', "Build with debug info."

  def install
    args = std_cmake_args
    args.delete '-DCMAKE_BUILD_TYPE=None'
    args.delete_if {|s| s.match(/^-DCMAKE_INSTALL_PREFIX/) }
    args << "-DCMAKE_INSTALL_PREFIX=#{prefix}"
    if build.with? "debug-info"
      args << '-DCMAKE_BUILD_TYPE=RelWithDebInfo'
    else
      args << '-DCMAKE_BUILD_TYPE=Release'
    end
    args << '-DCATKIN_BUILD_BINARY_PACKAGE=1'

    system 'if [ -f "/usr/local/setup.sh" ]; then . "/usr/local/setup.sh"; fi && cmake . ' + args.join(" ") + " && make install"
  end
end
"""


def camelcase(name):
    return "".join([s.capitalize() for s in name.split('-')])


def formula_class_name(pkg_name, rosdistro):
    return camelcase(formula_name(pkg_name, rosdistro))


def formula_name(pkg_name, rosdistro):
    return "ros-{0}-{1}".format(rosdistro, pkg_name.replace('_', '-'))


def formula_file_name(pkg_name, rosdistro):
    return formula_name(pkg_name, rosdistro) + ".rb"


def compose_version(pkg_version, deb_inc):
    return "{0}-{1}".format(pkg_version, deb_inc)


def devel_branch(ros_distro):
    return ros_distro + "-devel"



import shutil
from rosdep2.catkin_support import default_installers
from rosdep2.catkin_support import get_catkin_view
from rosdep2.catkin_support import get_installer
from bloom.generators.common import get_view
from bloom.logging import ansi
from bloom.generators import update_rosdep
from bloom.generators.common import default_fallback_resolver
from rosdep2.lookup import ResolutionError

try:
    import em
except ImportError:
    debug(traceback.format_exc())
    error("empy was not detected, please install it.", exit=True)

## Fix unicode bug in empy
## This should be removed once upstream empy is fixed
## See: https://github.com/ros-infrastructure/bloom/issues/196
#try:
#    em.str = unicode
#    em.Stream.write_old = em.Stream.write
#    em.Stream.write = lambda self, data: em.Stream.write_old(self, data.encode('utf8'))
#except NameError:
#    pass
## End fix


TEMPLATE_EXTENSION = '.em'


def summarize_dependency_mapping(data, deps, build_deps, resolved_deps):
    if len(deps) == 0 and len(build_deps) == 0:
        return
    info("Formula '" + data['Formula'] + "' has dependencies:")
    header = "  " + ansi('boldoff') + ansi('ulon') + \
             "rosdep key           => " + \
             " key" + ansi('reset')
    template = "  " + ansi('cyanf') + "{0:<20} " + ansi('purplef') + \
               "=> " + ansi('cyanf') + "{1}" + ansi('reset')
    if len(deps) != 0:
        info(ansi('purplef') + "Run Dependencies:" +
             ansi('reset'))
        info(header)
        for key in [d.name for d in deps]:
            info(template.format(key, resolved_deps[key]))
    if len(build_deps) != 0:
        info(ansi('purplef') +
             "Build and Build Tool Dependencies:" + ansi('reset'))
        info(header)
        for key in [d.name for d in build_deps]:
            info(template.format(key, resolved_deps[key]))


def format_depends(depends, resolved_deps):
    formatted = []
    for d in depends:
        if resolved_deps[d.name]:
            inst_key, resolved_keys = resolved_deps[d.name]
            if inst_key is "homebrew":
                tmpl = "depends_on \"{0}\""
            elif inst_key is "pip":
                tmpl = "#depends_on \"{0}\" => :python"
            else:
                error("Invalid dependency type {0}".format(inst_key), exit=True)        
            for resolved_key in resolved_keys:
                formatted.append(tmpl.format(resolved_key))
    return formatted



## FIXME: copied and adapted from catkin_support
def resolve_for_os(rosdep_key, os_name, os_version, ros_distro):
    if os_name not in default_installers:
        BloomGenerator.exit("Could not determine the installer for '{0}'"
                            .format(os_name))
    view = get_view(os_name, os_version, ros_distro)
    print("rodep key" + rosdep_key)
    d = view.lookup(rosdep_key)

    inst_key, rule = d.get_rule_for_platform(os_name, os_version, default_installers[os_name], default_installers[os_name][0])
    installer = get_installer(inst_key)
    return (inst_key, installer.resolve(rule))


def resolve_rosdep_key(
    key,
    os_name,
    os_version,
    ros_distro=None,
    ignored=None,
    retry=True
):
    ignored = ignored or []
    ros_distro = ros_distro or DEFAULT_ROS_DISTRO
    try:
        return resolve_for_os(key, os_name, os_version, ros_distro)
    except (KeyError, ResolutionError) as exc:
        debug(traceback.format_exc())
        if key in ignored:
            return None
        if isinstance(exc, KeyError):
            error("Could not resolve rosdep key '{0}'".format(key))
        else:
            error("Could not resolve rosdep key '{0}' for distro '{1}':"
                  .format(key, os_version))
            info(str(exc), use_prefix=False)
        if retry:
            error("Try to resolve the problem with rosdep and then continue.")
            if maybe_continue():
                update_rosdep()
                invalidate_view_cache()
                return resolve_rosdep_key(key, os_name, os_version, ros_distro,
                                          ignored, retry=True)
        BloomGenerator.exit("Failed to resolve rosdep key '{0}', aborting."
                            .format(key))


def resolve_dependencies(
    keys,
    os_name,
    os_version,
    ros_distro=None,
    peer_packages=None,
    fallback_resolver=None
):
    ros_distro = ros_distro or DEFAULT_ROS_DISTRO
    peer_packages = peer_packages or []
    fallback_resolver = fallback_resolver or default_fallback_resolver

    resolved_keys = {}
    keys = [k.name for k in keys]
    for key in keys:
        inst_key, resolved_key = resolve_rosdep_key(key, os_name, os_version, ros_distro,
                                                    peer_packages, retry=True)
        if inst_key not in ["homebrew", "pip"]:
            warning("Ignoring dependecy ({0}, {1}) which can not be expressed in homebrew.".format(inst_key, resolved_key))
            resolved_key = None
        else:
            if resolved_key is None:
                resolved_key = fallback_resolver(key, peer_packages)
        resolved_keys[key] = (inst_key, resolved_key) if resolved_key else None
    return resolved_keys


from rosdistro import get_cached_distribution, get_index, get_index_url
#from rosdistro.dependency_walker import DependencyWalker
from rosdistro.manifest_provider import get_release_tag


def get_distro(distro_name):
    index = get_index(get_index_url())
    return get_cached_distribution(index, distro_name)



def generate_substitutions_from_package(
    package,
    distro_name,
    distro,
    installation_prefix='/usr',
    deb_inc='0',
    peer_packages=None,
    releaser_history=None,
    fallback_resolver=None
):
    os_name = 'osx'
    os_version = 'foobar' # todo: what should this be?

    distro_pkg = distro.release_packages[package.name]
    release_repo = distro.repositories[distro_pkg.repository_name].release_repository

    peer_packages = peer_packages or []
    data = {}
    # Name, Version, Description
    data['ClassName'] = formula_class_name(package.name, distro_name)

    # todo: do we need something like deb_inc for homebrew???
    data['Version'] = compose_version(package.version, deb_inc)
    # Repository
    data['RepoUrl'] = release_repo.url
    data['ReleaseTag'] = get_release_tag(release_repo, package.name)
    data['DevelBranch'] = devel_branch(distro_name)
    # Websites
    websites = [str(url) for url in package.urls if url.type == 'website']
    homepage = websites[0] if websites else ''
    if homepage == '':
        warning("No homepage set, defaulting to ''")
    data['Homepage'] = homepage
    # Package name
    data['Formula'] = formula_name(package.name, distro_name)
    # Installation prefix
    data['InstallationPrefix'] = installation_prefix
    # Resolve dependencies

    # FIXME: build vs run depends
    depends = package.run_depends
    build_depends = package.build_depends + package.buildtool_depends
    unresolved_keys = depends + build_depends
    resolved_deps = resolve_dependencies(unresolved_keys, os_name,
                                         os_version, distro_name,
                                         peer_packages, fallback_resolver)
    #print(depends)
    #print(resolved_deps)
    data['Depends'] = sorted(
        set(format_depends(depends, resolved_deps))
    )
    data['BuildDepends'] = sorted(
        set(format_depends(build_depends, resolved_deps))
    )
    # Summarize dependencies
    summarize_dependency_mapping(data, depends, build_depends, resolved_deps)

    def convertToUnicode(obj):
        if sys.version_info.major == 2:
            if isinstance(obj, str):
                return unicode(obj.decode('utf8'))
            elif isinstance(obj, unicode):
                return obj
        else:
            if isinstance(obj, bytes):
                return str(obj.decode('utf8'))
            elif isinstance(obj, str):
                return obj
        if isinstance(obj, list):
            for i, val in enumerate(obj):
                obj[i] = convertToUnicode(val)
            return obj
        elif isinstance(obj, type(None)):
            return None
        elif isinstance(obj, tuple):
            obj_tmp = list(obj)
            for i, val in enumerate(obj_tmp):
                obj_tmp[i] = convertToUnicode(obj_tmp[i])
            return tuple(obj_tmp)
        elif isinstance(obj, int):
            return obj
        raise RuntimeError('need to deal with type %s' % (str(type(obj))))

    for item in data.items():
        data[item[0]] = convertToUnicode(item[1])

    return data


def get_subs(pkg, ros_distro_name, distro):
    return generate_substitutions_from_package(
        pkg,
        ros_distro_name,
        distro
    )


def prepare_arguments(parser):
    add = parser.add_argument
    add('package_path', nargs='?',
        help="path to or containing the package.xml of a package")
    action = parser.add_mutually_exclusive_group(required=False)
    add = action.add_argument
    add('--place-template-files', '--place', action='store_true',
        help="places debian/* template files only")
    add('--process-template-files', '--process', action='store_true',
        help="processes templates in debian/* only")
    add = parser.add_argument
    add('--ros-distro', '--rosdistro', '-r',
        help='ROS distro, e.g. groovy, hydro (used for rosdep)')
    return parser


def place_template_files(path, pkg_name, rosdistro):
    info(fmt("@!@{bf}==>@| Placing fromula template in the 'homebrew' folder."))
    homebrew_path = os.path.join(path, 'homebrew')
    if not os.path.exists(homebrew_path):
        os.makedirs(homebrew_path)
    template_file = formula_file_name(pkg_name, rosdistro) + ".em"
    debug("Placing template '{0}'".format(template_file))
    formula_dst = os.path.join(homebrew_path, template_file)
    if os.path.exists(formula_dst):
        debug("Removing existing file '{0}'".format(formula_dst))
        os.remove(formula_dst)
    with open(formula_dst, 'w') as f:
        f.write(formula_template)


def __process_template_folder(path, subs):
    items = os.listdir(path)
    processed_items = []
    for item in list(items):
        item = os.path.abspath(os.path.join(path, item))
        if os.path.basename(item) in ['.', '..', '.git', '.svn']:
            continue
        if os.path.isdir(item):
            sub_items = __process_template_folder(item, subs)
            processed_items.extend([os.path.join(item, s) for s in sub_items])
        if not item.endswith(TEMPLATE_EXTENSION):
            continue
        with open(item, 'r') as f:
            template = f.read()
        # Remove extension
        template_path = item[:-len(TEMPLATE_EXTENSION)]
        # Expand template
        info("Expanding '{0}' -> '{1}'".format(
            os.path.relpath(item),
            os.path.relpath(template_path)))
        result = em.expand(template, **subs)
        # Write the result
        with open(template_path, 'w') as f:
            f.write(result)
        # Copy the permissions
        shutil.copymode(item, template_path)
        processed_items.append(item)
    return processed_items


def process_template_files(path, subs):
    info(fmt("@!@{bf}==>@| In place processing templates in 'homebrew' folder."))
    debian_dir = os.path.join(path, 'homebrew')
    if not os.path.exists(debian_dir):
        sys.exit("No debian directory found at '{0}', cannot process templates."
                 .format(debian_dir))
    return __process_template_folder(debian_dir, subs)


def main(args=None, get_subs_fn=None):
    get_subs_fn = get_subs_fn or get_subs
    _place_template_files = True
    _process_template_files = True
    package_path = os.getcwd()
    if args is not None:
        package_path = args.package_path or os.getcwd()
        _place_template_files = args.place_template_files
        _process_template_files = args.process_template_files

    pkgs_dict = find_packages(package_path)
    if len(pkgs_dict) == 0:
        sys.exit("No packages found in path: '{0}'".format(package_path))
    #if len(pkgs_dict) > 1:
    #    sys.exit("Multiple packages found, this tool only supports one package at a time.")

    ros_distro_name = os.environ.get('ROS_DISTRO', 'groovy')

    # Allow args overrides
    ros_distro_name = args.ros_distro or ros_distro_name

    # Summarize
    info(fmt("@!@{gf}==> @|") +
         fmt("Generating Homebrew formula for package(s) %s" %
            ([p.name for p in pkgs_dict.values()])))

    # get rosdisro
    distro = get_distro(ros_distro_name)

    for path, pkg in pkgs_dict.items():

        # FIXME: process multiple into one folder hack:
        path = package_path

        template_files = None
        try:
            subs = get_subs_fn(pkg, ros_distro_name, distro)
            if _place_template_files:
                # Place template files
                place_template_files(path, pkg.name, ros_distro_name)
            if _process_template_files:
                # Just process existing template files
                template_files = process_template_files(path, subs)
            if not _place_template_files and not _process_template_files:
                # If neither, do both
                place_template_files(path, pkg.name, ros_distro_name)
                template_files = process_template_files(path, subs)
            if template_files is not None:
                for template_file in template_files:
                    os.remove(os.path.normpath(template_file))
        except Exception as exc:
            debug(traceback.format_exc())
            error(type(exc).__name__ + ": " + str(exc), exit=True)
        except (KeyboardInterrupt, EOFError):
            sys.exit(1)

# This describes this command to the loader
description = dict(
    title='homebrew',
    description="Generates a Homebrew Formula for a catkin package",
    main=main,
    prepare_arguments=prepare_arguments
)
