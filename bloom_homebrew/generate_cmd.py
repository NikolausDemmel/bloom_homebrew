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

class :{camelcase_name} < Formula
  homepage ':{homepage}'
  url ':{url}'
  version ':{version}'
  sha1 ':{sha1}'

:{depends}

  def install
    system "cmake", *std_cmake_args
    system "make install"
  end
end
"""


def camelcase(name):
    pass


def generate_substitutions_from_package(pkg, rosdistro):
    subs = {}
    subs['camelcase_name'] = pkg.name.lower().split('-')
    return subs


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


def get_subs(pkg, ros_distro):
    return generate_substitutions_from_package(pkg, ros_distro)


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
    if len(pkgs_dict) > 1:
        sys.exit("Multiple packages found, this tool only supports one package at a time.")

    ros_distro = os.environ.get('ROS_DISTRO', 'groovy')

    # Allow args overrides
    ros_distro = args.ros_distro or ros_distro

    # Summarize
    info(fmt("@!@{gf}==> @|") +
         fmt("Generating Homebrew formula for package(s) %s" %
            ([p.name for p in pkgs_dict.values()])))

    for path, pkg in pkgs_dict.items():
        template_files = None
        try:
            subs = get_subs_fn(pkg, ros_distro)
            if _place_template_files:
                # Place template files
                place_template_files(path)
            if _process_template_files:
                # Just process existing template files
                template_files = process_template_files(path, subs)
            if not _place_template_files and not _process_template_files:
                # If neither, do both
                place_template_files(path)
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
