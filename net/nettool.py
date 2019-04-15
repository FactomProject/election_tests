#!/usr/bin/env python3

"""
A tool for testing a factomd network in a docker environment.

Usage:
    ./nettool.py (-h | --help)
    ./nettool.py status [-f FILE | --file FILE]
    ./nettool.py up [--build] [-f FILE | --file FILE]
    ./nettool.py down [--destroy] [-f FILE | --file FILE]
    ./nettool.py ins <from> <to> <action> [--one-way] [-f FILE | --file FILE]
    ./nettool.py add <from> <to> <action> [--one-way] [-f FILE | --file FILE]
    ./nettool.py del <from> <to> <action> [--one-way] [-f FILE | --file FILE]


Commands:
    status                    Show the current status of the environment.
    up                        Ensure the environment is up and running.
    down                      Stop the environment.
    ins <from> <to> <action>  Insert a new network rule at the beginning.
    add <from> <to> <action>  Append a new network rule at the end.
    del <from> <to> <action>  Delete an existing rule.

Options:
    -h --help               Show this screen.
    -f, --file FILE         YAML config file describing the environment
                            [default: config.yml].
    --build                 Rebuild all container images (useful after e.g.
                            you have updated the factomd code).
    --destroy               Destroy all artifacts created by the tool.
    --one-way               If true, the rule will be added/deleted
                            assymetrically, otherwise the rule is added/deleted
                            both ways.
"""
from docopt import docopt

# from ..net.base import config, environment, log
import net.base.config
import net.base.environment
import net.base.log


def main(**kwargs):
    cfg_file = kwargs['file']      if 'file'       in kwargs else '../factomd/support/net/config.yml'
    fromvar =  kwargs['fromvar']   if 'fromvar'    in kwargs else ''
    to =       kwargs['to']        if 'to'         in kwargs else ''
    action =   kwargs['action']    if 'action'     in kwargs else ''
    one_way =  True                if 'one_way'    in kwargs else False

    command = kwargs['command']
    if command is 'status': _print_status(cfg_file)
    elif command is 'up':
        build = kwargs['build'] if 'build' in kwargs else False
        # build = True if 'build' in kwargs else False
        _environment_up(cfg_file, build)
    elif command is 'down':
        destroy = kwargs['destroy'] if 'destroy' in kwargs else False
        # destroy = True if 'destroy' in kwargs else False
        _environment_down(cfg_file, destroy)
    elif command is 'ins':
        _environment_ins(cfg_file, fromvar, to, action, one_way)
    elif command is 'add':
        _environment_add(cfg_file, fromvar, to, action, one_way)
    elif command is 'del':
        _environment_del(cfg_file, fromvar, to, action, one_way)

    else:
        raise Exception("Error parsing arguments")

    net.base.log.section("Done")


def _print_status(config_file):
    env = _environment_from_file(config_file)
    env.print_info()


def _environment_up(config_file, build_mode):
    env = _environment_from_file(config_file)
    env.up(build_mode=build_mode)


def _environment_down(config_file, destroy_mode):
    env = _environment_from_file(config_file)
    env.down(destroy_mode=destroy_mode)


def _environment_ins(config_file, source, target, action, one_way):
    env = _environment_from_file(config_file)
    env.rules.insert(source, target, action, one_way)


def _environment_add(config_file, source, target, action, one_way):
    env = _environment_from_file(config_file)
    env.rules.append(source, target, action, one_way)


def _environment_del(config_file, source, target, action, one_way):
    env = _environment_from_file(config_file)
    env.rules.delete(source, target, action, one_way)


def _environment_from_file(config_file):
    net.base.log.info("Reading config from:", config_file)
    cfg = net.base.config.read_file(config_file)
    return net.base.environment.Environment(cfg)


if __name__ == "__main__":
    main(docopt(__doc__))
