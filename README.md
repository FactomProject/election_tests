# election_tests
---
Python test suite for proper functioning of factomd election functions

## Getting Started
---
This is a standalone* package of python code that will set up docker networks of `factomd` images and perform various tests on them involving faulting various nodes at various minutes in the life of a directory block and verifying that the network reacts correctly. "Faulting" and "reconnecting" nodes is implemented by filtering out incoming and/or outgoing communications of a node via Linux iptables which manipulate firewall IP packet filter rules.

*Standalone means that the code necessary to create, manage, manipulate, and remove the requisite docker networks is included in this package. This code includes the factomd network creation code that also resides on `github` at `https://github.com/FactomProject/nettool` where it is fully documented. A concise version of this documentation explaining how to work with the network is presented here in the code at `election_tests\net\nettool.py`

The `factomd` codebase to be tested is NOT included in the package and the location of this codebase must be specified via the package's configuration files.

The package also depends on the availability of a number of standard Python modules which it imports:
 - docopt, re, subprocess, unittest, requests, json, time, os, datetime

## Configuration
---

### `config.yml` - configuration file template
---
`election_tests\net\config.yml` is the template configuration file which can be used as a model from which to generate a separate configuration file for each of the tests to be performed. It also contains good documentation on the items addressed in the configuration file.

### Configuration files
---
`election_tests\net\suite\` contains a collection of configuration files which may prove useful. They employ a standard naming scheme for clarity:
- `L` denotes a leader server node.
- `A` denotes an audit server node.
- `_` denotes a follower node.
The nodes in these configuration file are arranged in a linear pattern unless showing a suffix:
- `mesh` for all nodes connected to each other
- `star` for all nodes connected to and only to node1

Inside each configuration file itself, these items are addressed (details are in `election_tests\net\config.yml`):
- the path to the factomd codebase to be tested against
- default flags to be applied when running the factomd codebase
- initial configuration of each node in the network
- initial rules of message filtering between nodes in the network (if no rules are specified, the default configuration is that all nodes are fully connected to all other nodes)
- this naming convention may make your life easier:
  - node name = node*n*
  - ui port = 8*n*90 (allows use of `localhost:8*n*90` in browser to access control panel of the node)
  - api port = 8*n*88

### `test_data.json`
---
`election_tests\test_data.json` contains configurable test data that may be accessed by the tests themselves:
- IP address of a wallet server
- private and public keys of 2 factoid addresses
- private key of an entry credit address
- path to `nettool.py`
- path to default configuration file
- paths to test configuration files
- identities for nodes to use

## `network_tests_all.py`
---
Currently, all tests are included in one file: `election_tests\network_tests_all.py`.

### On startup
---
- `server_configuration = 'LLLAALL'` - sets a default network configuration which will apply until a particular test overrides it with its own configuration. This is needed if using utility functions that don't define their own configuration files
- `build` and `destroy` - set to True to rebuild image and fresh database, set to False to resume with old images and database, default False
- `WAITTIME = 500` - set to how many seconds to wait before abandoning the test

### Utilities
---
At the end of the file are some handy commands for election testing:
- `test_network_up` - just bring the network up
- `test_network_down` - just take the network down. If a test aborts, the network may be left up. Trying to then bring up a new network when one is already open will not work, so it must first be shut down manually
- `test_network_status` - report the current status of the network
- `test_docker_ps` - issue the `docker_ps` command
- `test_weave_status_dns` - issue the `weave status dns` command

If `weave scope` is installed on your system, issuing the `scope launch` command will allow you to:
- access a real-time graphical depiction of the network on your browser at `localhost:4040`
- access each of the docker containers in the network directly

### Current test suite
---
The entire test suite is executed by running `test_overnight_battery`
This sequentially runs these tests:
- `test_single_election` in each minute from minute 0 to minute 9. This faults a single leader in the designated minute.
- `test_double_election` in each minute from minute 0 to minute 9. This faults *two* leaders in the designated minute.
- `test_sequential_elections` in each minute from minute 0 to minute 9. This faults a leader in the designated minute and then faults another leader in the following minute.

The content of the suite can be changed by:
- commenting out any of these tests that aren't to be run
- altering the minute specification `for target_minute in range(10)` of any of the tests, e.g. `for target_minute in range(5, 10, 2)` will perform the test in each of minutes 5, 7, and 9.



































