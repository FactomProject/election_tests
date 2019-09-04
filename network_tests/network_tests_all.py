import re, subprocess, unittest, requests, json, time, os
from datetime import timedelta, datetime

import net.nettool
from helpers.helpers import read_data_from_json

'''
set 'network_config_file' in 'test_data.json' to match 'network' file in test e.g. 'LLAL'
set 'build=' and 'destroy='
run 'test_network_down' to clear the network

need to test single election in every minute, double election in at least minute 0, 1, and 9, sequential election in consecutive minutes including 9 then 0
'''

class NetworkTests(unittest.TestCase):
    data = read_data_from_json('test_data.json')
    wallet_address = data['wallet_address']

    # set this as the network to use for non-overnight_battery commands
    # In any case, this is the configuration file that determines factomd command line parameters, e.g. blocktime
    server_configuration = 'LLLAALL'
    config_file = data[server_configuration]

    # remove any logging files leftover in source directory so that they dont obfuscate any logging files created during this run
    directory = os.path.dirname(__file__)
    filename = os.path.join(directory, config_file)
    with open(filename) as f: filedata = f.read().splitlines()
    sourcepath = [line.split(':')[1] for line in filedata if line.split(':')[0]=='factomd_path'][0][2:-1]
    cmd = ['rm -rf '+sourcepath+'!(CLA).txt; rm -rf '+sourcepath+'engine/*.txt']
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True)

    '''
    set build and destroy to True when:
    switching network configuration files, or
    changing anything in a network configuration file
    rebuilding a fresh database
    '''
    # build = False
    # destroy = False
    build = True
    destroy = True
    # how many seconds to wait for an operation to complete
    WAITTIME = 500

    def test_overnight_battery(self):
        battery_start_time = time.time()
        # remove old log files
        for i in range(9):
            node = 'node' + str(i+1)
            cmd = ['docker', 'exec', '-it', node, 'bash', '-c', 'rm -rf *.txt']
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

        # single elections, minutes 0 to 9
        batch_start_time = time.time()
        server_configuration = 'LLAL'
        for target_minute in range(1):
            self.test_single_election(server_configuration, target_minute, nodes_to_fault=(4,))
        self.print_elapsed_time('batch', batch_start_time)

        # double elections, minutes 0 to 9
        batch_start_time = time.time()
        server_configuration = 'LLLAALL'
        for target_minute in range(10):
            self.test_double_election(server_configuration, target_minute, nodes_to_fault=(7, 6))
        self.print_elapsed_time('batch', batch_start_time)

        # sequential elections, in subsequent minute, minutes 0 to 9
        batch_start_time = time.time()
        server_configuration = 'LLLAALL'
        for target_minute in range(10):
            self.test_sequential_elections(server_configuration, target_minute, nodes_to_fault=(7, 6))
        self.print_elapsed_time('batch', batch_start_time)

        # test that network stops on the loss of a majority of the block's original leaders
        batch_start_time = time.time()
        server_configuration = 'LAALL'
        self.test_majority_election(server_configuration, 0, nodes_to_fault=(5, 4))
        self.print_elapsed_time('batch', batch_start_time)

    @classmethod
    def tearDownClass(cls):
    # pause network after tests are completed so that the nodes don't continue generating uninteresting log files
        nodes = 9
        for i in range(1, nodes+1):
            node = 'node' + str(i)
            cmd = ['docker', 'pause', node]
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

    # *******************************************************************************

    def test_single_election(self, server_configuration, target_minute, nodes_to_fault, expect_stall=False, new=True):
        faulting_finished_in_same_minute = False
        while not faulting_finished_in_same_minute:

            # bring up network and verify correct operation
            test_start_time, config_file, initial_audit_server_list, initial_federated_server_list = self.initialize_network('Single election', server_configuration, target_minute, new)
            print()

            # fault node
            current_audit_server_list, current_federated_server_list, end_test, faulting_finished_in_same_minute = self.fault(nodes_to_fault=(nodes_to_fault[0],))

            if end_test: break

            elif faulting_finished_in_same_minute:
                    # verify node promotion
                    self.verify_promotion(initial_audit_server_list, current_federated_server_list, number_of_servers_to_promote=1)

                    # verify node demotion
                    self.verify_demotion((nodes_to_fault[0],), current_audit_server_list)

            else:
                self.timestamped_print('Faulting ended in a different minute from which it started. Lets try this test again!')

        # reconnect faulted nodes
        self.reconnect_nodes(config_file, nodes_to_fault)

        # stop network
        net.nettool.main(command='down', destroy=True, file=config_file)

        self.timestamped_print('Single election test successful in minute', str(target_minute))
        self.print_elapsed_time('test', test_start_time)

    # *******************************************************************************

    def test_double_election(self, server_configuration, target_minute, nodes_to_fault, new=True):
        faulting_finished_in_same_minute = False
        while not faulting_finished_in_same_minute:

            # bring up network and verify correct operation
            test_start_time, config_file, initial_audit_server_list, initial_federated_server_list = self.initialize_network('Double', server_configuration, target_minute, new)
            print()

            # fault node 6 and node 7
            current_audit_server_list, current_federated_server_list, end_test, faulting_finished_in_same_minute = self.fault(nodes_to_fault=nodes_to_fault)

            if faulting_finished_in_same_minute:
                # verify node 4 and node 5 promotion
                self.verify_promotion(initial_audit_server_list, current_federated_server_list, number_of_servers_to_promote=2)

                # verify node 6 and 7 demotion
                self.verify_demotion(nodes_to_fault, current_audit_server_list)

                # reconnect node 6 and 7
                self.reconnect_nodes(config_file, nodes_to_fault)

                # stop network
                net.nettool.main(command='down', destroy=True, file=config_file)

                self.timestamped_print('Double election test successful in minute', str(target_minute))
            else:
                self.timestamped_print('Faulting ended in a different minute from which it started. Lets try this test again!')
                self.print_elapsed_time('test', test_start_time)

    # *******************************************************************************

    def test_sequential_elections(self, server_configuration, target_minute, nodes_to_fault, new=True):
        # multiple nodes_to_fault must be in descending order

        # bring up network and verify correct operation
        test_start_time, config_file, initial_audit_server_list, initial_federated_server_list = self.initialize_network('Sequential',  server_configuration, target_minute, new)
        print()

        # fault 1st node
        current_audit_server_list, current_federated_server_list, end_test, faulting_finished_in_same_minute = self.fault(
            nodes_to_fault=(nodes_to_fault[0],))
        if end_test:
            self.restart_test(test_start_time, config_file)
        else:

            # verify 1st audit promotion
            self.verify_promotion(initial_audit_server_list, current_federated_server_list, number_of_servers_to_promote=1)

            # verify 1st leader demotion
            self.verify_demotion((nodes_to_fault[0],), current_audit_server_list)

            # update server configuration
            server_configuration = server_configuration[:-1]
            initial_audit_server_list = current_audit_server_list

            # fault 2nd node
            self.fault(nodes_to_fault=(nodes_to_fault[1],))

            self.verify_minutes_match_node1(len(server_configuration), nodes_to_fault)

            current_audit_server_list, current_federated_server_list = self.get_servers()
            print()
            connected_server_list = current_audit_server_list + current_federated_server_list
            connected_server_list.remove(1)
            connected_server_list.remove(nodes_to_fault[0])
            connected_server_list.remove(nodes_to_fault[1])
            connected_server_list.sort()

            self.verify_node_authority_sets_match_node1(connected_server_list)
            self.timestamped_print('current_audit_server_list', current_audit_server_list)

            # verify audit server promotion
            self.verify_promotion(initial_audit_server_list, current_federated_server_list, number_of_servers_to_promote=1)

            # verify node 6 demotion
            self.verify_demotion((6,), current_audit_server_list)

            # reconnect faulted nodes
            self.reconnect_nodes(config_file, nodes_to_fault)

            # stop network
            net.nettool.main(command='down', destroy=True, file=config_file)

            self.timestamped_print('Sequential election test successful in minute', str(target_minute))
            self.print_elapsed_time('test', test_start_time)
    # *******************************************************************************

    def test_majority_election(self, server_configuration, target_minute, nodes_to_fault, new=True):
        # multiple nodes_to_fault must be in descending order

        # bring up network and verify correct operation
        test_start_time, config_file, initial_audit_server_list, initial_federated_server_list = self.initialize_network(
            'Majority', server_configuration, target_minute, new)
        print()

        # fault 1st node
        current_audit_server_list, current_federated_server_list, end_test, faulting_finished_in_same_minute = self.fault(
            nodes_to_fault=(nodes_to_fault[0],))
        if end_test:
            self.restart_test(test_start_time, config_file)
        else:

            # verify 1st audit promotion
            self.verify_promotion(initial_audit_server_list, current_federated_server_list,
                                  number_of_servers_to_promote=1)

            # verify 1st leader demotion
            self.verify_demotion((nodes_to_fault[0],), current_audit_server_list)

            # update server configuration
            server_configuration = server_configuration[:-1]
            initial_audit_server_list = current_audit_server_list

            # fault 2nd node
            self.fault(nodes_to_fault=(nodes_to_fault[1],), expect_stall=False)

            self.print_elapsed_time('test', test_start_time)
            # stop network
            net.nettool.main(command='down', destroy=True, file=config_file)

    # *******************************************************************************

    # *******************************************************************************

    def print_elapsed_time(self, group, start_time):
        self.timestamped_print(group, 'elapsed time = ', str(timedelta(seconds=time.time() - start_time))[:-3])
        print('--------------------------------------------------------------')
        print('--------------------------------------------------------------')
        print()

    def timestamped_print(self, *stuff):
        print(str(datetime.now())[:-3], ' '.join([str(item) for item in stuff]))

    def initialize_network(self, test_type, server_configuration, target_minute=0, new=True):
        ready = False
        self.timestamped_print('server_configuration', server_configuration)
        config_file = self.data[server_configuration]
        self.timestamped_print('config_file', config_file)
        test_start_time = time.time()
        self.timestamped_print(test_type,'election target minute', target_minute)

        # start network
        net.nettool.main(command='up', build=new, file=config_file)
        self.timestamped_print('waiting for docker to come up')

        # set target authority set
        desired = []
        for server in range(1, len(server_configuration)+1): desired.append(server_configuration[server-1])
        self.timestamped_print('desired', ''.join(desired))
        print()

        # wait for authority set to match target authority set
        for seconds in range(self.WAITTIME):
            actual = []
            for server in range(1, len(server_configuration) + 1): actual.append(json.loads(self.debug_api('summary', server))['result']['Summary'].split(']')[1][1])
            self.timestamped_print('actual', ''.join(actual))
            self.get_servers()
            if actual == desired:
                ready = True
                break
            else: time.sleep(1)
        self.assertTrue(ready, 'Authority set never matched target authority set')
        self.timestamped_print('initial promotion complete')
        print()

        self.wait_for_target_minute(target_minute)

        self.timestamped_print('initial')
        audit_server_list, federated_server_list = self.get_servers()
        return test_start_time, config_file, audit_server_list, federated_server_list

    def get_servers(self, nodenumber=1):
        # get audit servers
        serverdump = json.loads(self.debug_api('audit-servers', nodenumber))['result']['AuditServers']
        audit_server_list = []
        audit_server_id_list = []
        for audit_server in serverdump:
            audit_server_list.append(self.data[audit_server['ChainID']])
            audit_server_id_list.append(audit_server['ChainID'])

        # get federated servers
        serverdump = json.loads(self.debug_api('federated-servers', nodenumber))['result']['FederatedServers']
        federated_server_list = []
        federated_server_id_list = []
        for federated_server in serverdump:
            federated_server_list.append(self.data[federated_server['ChainID']])
            federated_server_id_list.append(federated_server['ChainID'])

        # display servers
        block, minute = self.current_block_minute()
        self.timestamped_print('node', str(nodenumber), 'block', str(block).rjust(3), 'minute', minute, 'audit_server_list', audit_server_list)
        # self.timestamped_print('node', str(nodenumber), 'block', str(block).rjust(3), 'minute', minute, 'federated_server_list', federated_server_list, 'audit_server_list', audit_server_list)
        return audit_server_list, federated_server_list

    def wait_for_target_minute(self, target_minute):
        self.timestamped_print('waiting for target minute')
        self.timestamped_print('target          minute',  target_minute)
        start_block, start_minute = self.current_block_minute()
        self.timestamped_print('start block', str(start_block).rjust(3), 'minute', start_minute)
        for seconds in range(self.WAITTIME):
            for quarter_seconds in range(4):
                block, minute = self.current_block_minute()
                if minute == target_minute and (minute != start_minute or block != start_block): break
                time.sleep(0.25)
            self.timestamped_print('      block', str(block).rjust(3), 'minute', minute, 'seconds', str(seconds).rjust(3))
            if minute == target_minute and (minute != start_minute or block != start_block): break
        self.assertLess(seconds, self.WAITTIME-1, 'Target minute ' + str(target_minute) + ' not found')
        print()

    def fault(self, nodes_to_fault, expect_stall=False):
        end_test = False
        pre_block, pre_minute = self.current_block_minute()

        for node in nodes_to_fault:
            self.verify_faulting_nodes_minute_matches_node1(nodes_to_fault)

            # fault node
            self.timestamped_print('faulting node', node)
            print('********************************************************')
            fault_start_time = time.time()
            # sim-ctrl method
            result = self.debug_api_with_parameters('sim-ctrl', node, {'commands':['x']})
            # filter API method
            self.factomd_api_with_parameters('message-filter', node, {'output-regex':'.*', 'input-regex':'.*'})
            '''
            TODO when FD-945 is implemented, change the above line to:
            self.debug_api_with_parameters('message-filter', node, {'output-regex': 'off', 'input-regex':'off'})
            '''
            self.timestamped_print('fault elapsed time = ', str(timedelta(seconds=time.time() - fault_start_time))[:-3])
            print()

        post_block, post_minute = self.current_block_minute()

        if post_block == pre_block and post_minute == pre_minute:
            # faulting completed in target minute
            faulting_finished_in_same_minute = True
            self.wait_for_new_minute(expect_stall)
            current_audit_server_list, current_federated_server_list = self.get_servers()
            print()

        elif expect_stall:
            # test is over if network was expected to stall
            self.wait_for_new_minute(expect_stall)
            self.timestamped_print('Network successfully stalled')
            current_audit_server_list, current_federated_server_list, end_test, faulting_finished_in_same_minute = [], [], True, False

        else:
            # abort test if faulting didn't finish in same minute it started
            current_audit_server_list, current_federated_server_list, end_test, faulting_finished_in_same_minute = [], [], False, False

        return current_audit_server_list, current_federated_server_list, end_test, faulting_finished_in_same_minute

    def verify_faulting_nodes_minute_matches_node1(self, nodes_to_fault):
        self.timestamped_print('verifying nodes to be faulted are in same minute as node 1')
        for seconds in range(self.WAITTIME):
            for quarter_seconds in range(4):
                match = True
                block1, minute1 = self.current_block_minute(1)
                self.timestamped_print('node 1 block', str(block1).rjust(3), 'minute', minute1)
                for node in nodes_to_fault:
                    block, minute = self.current_block_minute(node)
                    self.timestamped_print('node', node, 'block', str(block).rjust(3), 'minute', minute)
                    if minute != minute1:
                        match = False
                    if match == False: break
                print()
                if match == True: break
                time.sleep(0.25)
            if match == True: break
            self.assertTrue(match, 'Not all nodes to be faulted minute match node 1 minute')

    def wait_for_new_minute(self, expect_stall=False, nodenumber=1):
        old_block, old_minute = self.current_block_minute(nodenumber)
        self.timestamped_print('waiting for new minute')
        self.timestamped_print('node', nodenumber, 'block', str(old_block).rjust(3), 'minute', old_minute)

        # report every second
        for seconds in range(self.WAITTIME):

            # but check every quarter second
            for quarter_seconds in range(4):
                block, minute = self.current_block_minute(nodenumber)
                if minute != old_minute: break
                time.sleep(6)
            self.timestamped_print('node', nodenumber, 'block', str(block).rjust(3), 'minute', minute, 'seconds', str(seconds).rjust(3))
            if minute != old_minute: break
        advanced = minute != old_minute
        if expect_stall != advanced:
            self.timestamped_print('minute advance performed correctly')
            print()
        else:
            if expect_stall:
                self.timestamped_print('node ' + str(nodenumber) + ' minute advanced past ' + str(old_minute))
                self.timestamped_print('Network should have stalled but did not')
            else:
                self.timestamped_print('node ' + str(nodenumber) + ' minute did not advance past ' + str(old_minute))
                self.timestamped_print('Network should not have stalled but did')
            self.assertTrue(False, 'Network did not function as predicted')

    def verify_node_authority_sets_match_node1(self, nodes_to_check):
        self.timestamped_print('verifying authority sets of connected servers match')
        node_audit_server_list = {}
        node_federated_server_list = {}
        for seconds in range(self.WAITTIME):
            for quarter_seconds in range(4):
                node1_audit_server_list, node1_federated_server_list = self.get_servers(1)
                for server in nodes_to_check:
                    node_audit_server_list[server], node_federated_server_list[server] = self.get_servers(server)
                print()
                if all([node_audit_server_list[server] == node1_audit_server_list and node_federated_server_list[server] == node1_federated_server_list for server in nodes_to_check]): break
                time.sleep(0.25)
            if all([node_audit_server_list[server] == node1_audit_server_list and node_federated_server_list[
                server] == node1_federated_server_list for server in nodes_to_check]):
                break
        if seconds == self.WAITTIME - 1:
            self.assertTrue(True, 'Not all server authority sets match node 1 authority set')

    def verify_promotion(self, initial_audit_server_list, current_federated_server_list, number_of_servers_to_promote):
        self.timestamped_print('verifying node promotion')
        initial_audit_server_list.sort()
        promoted_server_count = 0
        for initial_audit_server in initial_audit_server_list:
            self.timestamped_print('initial_audit_server', initial_audit_server)
            if initial_audit_server in current_federated_server_list:
                self.timestamped_print('promoted')
                promoted_server_count += 1
                self.timestamped_print('promoted_server_count', promoted_server_count)
        if promoted_server_count != number_of_servers_to_promote: self.assertTrue(False, 'Wrong number of audit servers promoted')
        self.timestamped_print('audit servers properly promoted')
        print()

    def verify_demotion(self, nodes_to_fault, current_audit_server_list):
        self.timestamped_print('verifying node demotion')
        for node in nodes_to_fault:
            self.assertIn(node, current_audit_server_list, 'Federated server ' + str(node) + ' not demoted')
            self.timestamped_print('federated_server', str(node), 'properly demoted')
        print()

    def reconnect_nodes(self, config_file, nodes_to_reconnect):
        self.timestamped_print('reconnecting faulted nodes')
        for node in nodes_to_reconnect:
            self.timestamped_print('reconnecting node', node)

            # sim-ctrl method
            result = self.debug_api_with_parameters('sim-ctrl', node, {'commands':['x']})
            # filter API method
            # self.factomd_api_with_parameters('message-filter', node, {'output-regex': 'off', 'input-regex':'off'})
            '''
            TODO when FD-945 is implemented, change the above line to:
            self.debug_api_with_parameters('message-filter', node, {'output-regex': 'off', 'input-regex':'off'})
            '''
            # nettool method
            # net.nettool.main(command='ins', fromvar='node1', to='node' + str(node), action='allow', file=config_file)

            self.timestamped_print('waiting for reconnected node', str(node), 'to sync')
            # node has resynced when it advances from minute node 1 is in
            self.advance_from_main_node(node)
            self.timestamped_print('Reconnected node', str(node), 'properly resyncing')
            print()

    def verify_minutes_match_node1(self, number_of_nodes, disconnected_nodes):
        self.timestamped_print('verify all minutes match except disconnected nodes')
        for seconds in range(self.WAITTIME):
            for quarter_seconds in range(4):
                match = True
                block1, minute1 = self.current_block_minute(1)
                self.timestamped_print('node 1 block', str(block1).rjust(3), 'minute', minute1)
                for node in range(1, number_of_nodes):
                    server = node +1
                    block, minute = self.current_block_minute(server)
                    self.timestamped_print('node', server, 'block', str(block).rjust(3), 'minute', minute)
                    if server in disconnected_nodes:
                        # disconnected nodes should be behind
                        if minute == minute1: match = False
                    elif minute != minute1: match = False
                    if match == False: break
                print()
                if match == True: break
                time.sleep(0.25)
            if match == True: break
        self.assertTrue(match, 'Not all nodes minutes caught up with node 1 minute')

    def advance_from_main_node(self, nodenumber=1):
        advanced = False
        main_block, main_minute = self.current_block_minute()
        self.timestamped_print('node 1 block', str(main_block).rjust(3), 'minute', main_minute)
        self.timestamped_print('waiting for advance on main node')

        # report every second
        for seconds in range(self.WAITTIME):

            # check every quarter second
            for quarter_seconds in range(4):
                block, minute = self.current_block_minute(nodenumber)
                if block > main_block or block == main_block and minute > main_minute:
                    advanced = True
                    break
                time.sleep(0.25)
            self.timestamped_print('node', nodenumber, 'block', str(block).rjust(3), 'minute', minute, 'seconds', str(seconds).rjust(3))
            if advanced: break
        self.assertTrue(advanced, 'node ' + str(nodenumber) + ' never advanced past block ' + str(main_block) + ' minute ' + str(main_minute))

    def restart_test(self, test_start_time, config_file):
        self.timestamped_print('Faulting ended in a different minute from which it started. Lets try this test again!')
        self.print_elapsed_time('test', test_start_time)
        # stop network
        net.nettool.main(command='down', destroy=True, file=config_file)

    # *******************************************************************************
    # no longer used?
    # *******************************************************************************

    def current_block_minute(self, nodenumber=1):
        result = json.loads(self.factomd_api('current-minute', str(nodenumber)))['result']
        current_block = result['leaderheight']
        current_minute = result['minute']
        return current_block, current_minute

    def factomd_api(self, method, nodenumber=1):
        url = 'http://' + 'localhost:' + '8' + str(nodenumber) + '88' + '/v2'
        headers = {'Host': 'localhost:8088', 'content-type': 'text/plain'}
        payload = {"jsonrpc": "2.0", "id": 0, "method": method}
        r = requests.get(url, data=json.dumps(payload), headers=headers)
        return r.text

    def factomd_api_with_parameters(self, method, nodenumber, params_dict):
        url = 'http://' + 'localhost:' + '8' + str(nodenumber) + '88' + '/v2'
        headers = {'Host': 'localhost:8088', 'content-type': 'text/plain'}
        payload = {"jsonrpc": "2.0", "id": 0, "params": params_dict, "method": method}
        r = requests.get(url, data=json.dumps(payload), headers=headers)
        return r.text

    def debug_api(self, method, nodenumber=1):
        url = 'http://' + 'localhost:' + '8' + str(nodenumber) + '88' + '/debug'
        headers = {'Host': 'localhost:8088', 'content-type': 'text/plain'}
        payload = {"jsonrpc": "2.0", "id": 0, "method": method}
        r = requests.get(url, data=json.dumps(payload), headers=headers)
        return r.text

    def debug_api_with_parameters(self, method, nodenumber, params_dict):
        url = 'http://' + 'localhost:' + '8' + str(nodenumber) + '88' + '/debug'
        headers = {'Host': 'localhost:8088', 'content-type': 'text/plain'}
        payload = {"jsonrpc": "2.0", "id": 0, "params": params_dict, "method": method}
        r = requests.get(url, data=json.dumps(payload), headers=headers)
        return r.text

    def wallet_api(self, method):
        url = 'http://' + self.wallet_address +'/v2'
        headers = {'content-type': 'text/plain'}
        payload = {"jsonrpc": "2.0", "id": 0, "method": method}
        r = requests.post(url, data=json.dumps(payload), headers=headers)
        return r.text

    def wallet_api_with_parameters(self, method, params_dict):
        url = 'http://' + self.wallet_address +'/v2'
        headers = {'content-type': 'text/plain'}
        payload = {"jsonrpc": "2.0", "id": 0, "params": params_dict, "method": method}
        self.timestamped_print('payload', json.dumps(payload))
        r = requests.post(url, data=json.dumps(payload), headers=headers)
        return r.text

    def _network_bring_up(network_config_file):
        net.nettool.main(command='up', file=network_config_file)

    def _network_bring_down(network_config_file):
        net.nettool.main(command='down', file=network_config_file)

    # *********************************************************************************

    # *******************************************************************************

    # ***************************************************************************

    def test_network_up(self):
        net.nettool.main(command='up', build=self.build, file=self.config_file)

    def test_network_down(self):
        net.nettool.main(command='down', destroy=self.destroy, file=self.config_file)

    def test_network_status(self):
        net.nettool.main(command='status', file=self.data['network_config_file'])

    def test_docker_ps(self):
        subprocess.call("docker ps", shell=True)

    def test_weave_status_dns(self):
        subprocess.call("weave status dns", shell=True)

    # ***************************************************************************











