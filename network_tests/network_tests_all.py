import re, subprocess, unittest, requests, json, time, os, sys
from datetime import timedelta, datetime

# from factomd.support.net import nettool
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

    print('data',data)
    for dd in data:
        if dd[0] == 'L' or dd[0] == 'A' or dd[0] == '_':
            print('yeah',dd, " ", data[dd])
            with open(data[dd], "r+") as f:
                # line.split(':')[1]
                filedata3 = f.readlines()
                for line in enumerate(filedata3):
                    print('line',line)
                    if line[1].split(':')[0].replace(" ", "") == 'factomd_path':
                        filedata3[line[0]] = 'factomd_path: "/Users/joshuabrigati/go/src/github.com/FactomProject/factomd/" \n'
                        print('foundit!', line)
                        f.truncate(0)

                print('filedata3',filedata3)
                f.writelines(filedata3)


    # set this as the network to use for non-overnight_battery commands
    # In any case, this is the configuration file that determines factomd command line parameters, e.g. blocktime
    server_configuration = 'LLLAALL'
    config_file = data[server_configuration]
    print("config_file:", config_file)

    # remove any logging files leftover in source directory so that they dont obfuscate any logging files created during this run
    directory = os.path.dirname(__file__)
    print('directory', directory)
    filename = os.path.join(directory, config_file)
    filename2 = os.path.join(directory, data['network_config_file_default'])

    with open(filename2) as f:
        filedata2 = f.read().splitlines()
    print('filedata2', filedata2)
    sourcepath = [line.split(':')[1] for line in filedata2 if line.split(':')[0]=='factomd_path'][0][2:-1]
    print('sourcepath',sourcepath)


    print('filename2', filename2)
    print('version', sys.version)
    # with open(filename) as f: filedata = f.read().splitlines()
    # print('filedata',filedata)
    # sourcepath = [line.split(':')[1] for line in filedata if line.split(':')[0]=='factomd_path'][0][2:-1]
    # print('sourcepath',sourcepath)
    cmd = ['rm -rf '+sourcepath+'!(CLA).txt; rm -rf '+sourcepath+'engine/*.txt']
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True)

    '''set build and destroy to True when:
    switching network configuration files, or
    changing anything in a network configuration file
    rebuilding a fresh database'''
    # build = False
    # destroy = False
    build = True
    destroy = True
    BLOCKTIME = 30
    # how many seconds to wait for an operation to complete
    WAITTIME = 500

    def test_overnight_battery(self):
        battery_start_time = time.time()
        for i in range(9):
            node = 'node' + str(i+1)
            cmd = ['docker', 'exec', '-it', node, 'bash', '-c', 'rm -rf *.txt']
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

        # single elections, minutes 0 to 9
        batch_start_time = time.time()
        server_configuration = 'LLAL'
        for target_minute in range(10):
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
        # batch_start_time = time.time()
        # # test that network stalls if majority of feds are faulted
        # server_configuration = 'LAL'
        # self.test_single_election(server_configuration, nodes_to_fault=(3,), expect_stall=True)
        # server_configuration = 'LLAL'
        # self.test_stop_on_loss_of_original_majority(server_configuration, nodes_to_fault=(4,))
        # self.print_elapsed_time('batch', batch_start_time)

        self.print_elapsed_time('battery', battery_start_time)

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
        print('server_configuration',server_configuration, 'target_minute', target_minute, 'nodes_to_fault', nodes_to_fault)
        faulting_finished_in_same_minute = False
        while not faulting_finished_in_same_minute:

            # bring up network and verify correct operation
            test_start_time, config_file, initial_audit_server_list, initial_federated_server_list = self.initialize_network('Single election', server_configuration, target_minute, new)
            print()

            # fault node
            # current_audit_server_list, current_federated_server_list, end_test, faulting_finished_in_same_minute = self.fault(nodes_to_fault=(nodes_to_fault[0],))
            current_audit_server_list, current_federated_server_list, end_test, faulting_finished_in_same_minute = self.fault(nodes_to_fault=nodes_to_fault)

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
            # current_audit_server_list, current_federated_server_list, faulting_finished_in_same_minute = self.fault(nodes_to_fault=(nodes_to_fault[0],))
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
            # original_server_configuration = server_configuration
            server_configuration = server_configuration[:-1]
            initial_audit_server_list = current_audit_server_list

            # take disconnected node 7 off the available audit server list
            # initial_audit_server_list.remove(nodes_to_fault[0])

            # fault 2nd node
            # current_audit_server_list, current_federated_server_list, end_test, faulting_finished_in_same_minute = self.fault(nodes_to_fault=(nodes_to_fault[1],))
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

    def test_stop_on_loss_of_original_majority(self, server_configuration, nodes_to_fault, target_minute=0, new=True):
        # cancel the test and start over if faulting ever does not finish in the same minute it started
        faulting_finished_in_same_minute = False
        while not faulting_finished_in_same_minute:

            # bring up network and verify correct operation
            test_start_time, config_file, initial_audit_server_list, initial_federated_server_list = self.initialize_network('Fed majority loss',  server_configuration, target_minute, new)
            print()

            # fault nodes
            current_audit_server_list, current_federated_server_list, faulting_finished_in_same_minute = self.fault(server_configuration, config_file, initial_audit_server_list, nodes_to_fault=nodes_to_fault)
            if faulting_finished_in_same_minute:

                # verify node promotion
                self.verify_promotion(initial_audit_server_list, current_federated_server_list, number_of_servers_to_promote=len(nodes_to_fault))

                # verify node demotion
                self.verify_demotion(nodes_to_fault, current_audit_server_list)

                # # update server configuration
                # original_server_configuration = server_configuration
                # server_configuration = server_configuration[:-1]
                # # audit_servers = [audit + 1 for audit, server in enumerate(server_configuration) if server == 'A']
                # initial_audit_server_list = current_audit_server_list
                #
                # # take disconnected node 7 off the available audit server list
                # initial_audit_server_list.remove(7)
                # # original_federated_server_list = initial_federated_server_list
                # # initial_federated_server_list = current_federated_server_list
                #
                # # fault node 6
                # current_audit_server_list, current_federated_server_list, faulting_finished_in_same_minute = self.fault(server_configuration, config_file, initial_audit_server_list, nodes_to_fault=(6, ))
                # if faulting_finished_in_same_minute:
                #
                #     # verify audit server promotion
                #     self.verify_promotion(initial_audit_server_list, current_federated_server_list, number_of_servers_to_promote=1)
                #
                #     # verify node 6 demotion
                #     self.verify_demotion(6, current_audit_server_list)

                # reconnect faulted nodes
                self.reconnect_nodes(config_file, nodes_to_fault)

                # stop network
                net.nettool.main(command='down', destroy=True, file=config_file)

                self.timestamped_print('Sequential election test successful in minute', str(target_minute))
                self.print_elapsed_time('test', test_start_time)
                # else:
                #     server_configuration = original_server_configuration
                #     self.restart_test(test_start_time, config_file)
            else: self.restart_test(test_start_time, config_file)

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
        # self.timestamped_print('fed servers', [server[6:10] for server in federated_server_id_list], 'audit servers', [server[6:10] for server in audit_server_id_list])
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
            result = self.debug_api_with_parameters('sim-ctrl', node, {'commands':['x']})
            # self.factomd_api_with_parameters('message-filter', node, {'output-regex':'.*', 'input-regex':'.*'})
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

    # def fault(self, server_configuration, config_file, initial_audit_server_list, nodes_to_fault, expect_stall=False):
    #     end_test = False
    #     for node in nodes_to_fault:
    #         self.timestamped_print('faulting node', node)
    #         print('***************')
    #         pre_block, pre_minute = self.current_block_minute()
    #
    #         self.verify_faulting_nodes_minute_matches_node1(nodes_to_fault)
    #
    #         fault_start_time = time.time()
    #         # fault node
    #         # self.debug_api_with_parameters('sim-ctrl', 1, {'commands':[str(node-1),'x']})
    #         net.nettool.main(command='ins', fromvar='node1', to='node' + str(node), action='deny', file=config_file)
    #
    #         self.timestamped_print('fault elapsed time = ', str(timedelta(seconds=time.time() - fault_start_time))[:-3])
    #         print()
    #
    #     post_block, post_minute = self.current_block_minute()
    #     print('pre_block', pre_block, 'pre_minute', pre_minute)
    #     print('post_block', pre_block, 'post_minute', post_minute)
    #     if post_block == pre_block and post_minute == pre_minute:
    #         faulting_finished_in_same_minute = True
    #
    #         self.wait_for_new_minute(expect_stall)
    #         self.verify_minutes_match_node1(len(server_configuration), nodes_to_fault)
    #
    #         current_audit_server_list, current_federated_server_list = self.get_servers()
    #         print()
    #         self.verify_node_authority_sets_match_node1(initial_audit_server_list)
    #         self.timestamped_print('current_audit_server_list', current_audit_server_list)
    #     elif expect_stall:
    #         self.wait_for_new_minute(expect_stall)
    #         self.timestamped_print('Network successfully stalled')
    #         current_audit_server_list, current_federated_server_list, end_test, faulting_finished_in_same_minute = [], [], True, False
    #     else:
    #         # abort test if faulting didn't finish in same minute it started
    #         current_audit_server_list, current_federated_server_list, end_test, faulting_finished_in_same_minute = [], [], False, False
    #     print('end_test', end_test)
    #     print('faulting_finished_in_same_minute', faulting_finished_in_same_minute)
    #     print()
    #     return current_audit_server_list, current_federated_server_list, end_test, faulting_finished_in_same_minute
    #
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
                time.sleep(0.25)
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
            self.assertTrue(True, 'Network did not function as predicted')

    def verify_node_authority_sets_match_node1(self, nodes_to_check):
        self.timestamped_print('verifying authority sets of connected servers match')
        node_audit_server_list = {}
        node_federated_server_list = {}
        for seconds in range(self.WAITTIME):
            for quarter_seconds in range(4):
                node1_audit_server_list, node1_federated_server_list = self.get_servers(1)
                for server in nodes_to_check:
                    node_audit_server_list[server], node_federated_server_list[server] = self.get_servers(server)
                    # self.timestamped_print('audit match', node_audit_server_list[server] == node1_audit_server_list)
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

    # def demotion_check_old(self, federated_server_list, current_audit_server_list, list_position):
    #     self.timestamped_print('verifying node demotion')
    #     self.assertIn(federated_server_list[list_position], current_audit_server_list, 'Federated server ' + federated_server_list[list_position] + ' not demoted')
    #     self.timestamped_print('federated_server', federated_server_list[list_position], 'properly demoted')
    #     print()

    def reconnect_nodes(self, config_file, nodes_to_reconnect):
        self.timestamped_print('reconnecting faulted nodes')
        for node in nodes_to_reconnect:
            self.timestamped_print('reconnecting node', node)

            # self.factomd_api_with_parameters('message-filter', node, {'output-regex': 'off', 'input-regex':'off'})
            result = self.debug_api_with_parameters('sim-ctrl', node, {'commands':['x']})
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
    def wait_for_new_block(self, nodenumber=1, errormessage='Node did not advance to next block'):
        old_block = self.current_block_minute(nodenumber)[0]
        print()
        self.timestamped_print('node', nodenumber, 'old_block', str(old_block).rjust(3))
        self.timestamped_print('waiting for new block')
        for seconds in range(self.WAITTIME):
            block = self.current_block_minute(nodenumber)[0]
            print ('node', nodenumber, 'block', str(block).rjust(3), 'seconds', str(seconds).rjust(3))
            if block > old_block: break
            time.sleep(1)
        self.assertGreater(block, old_block, errormessage)
        self.wait_for_new_minute(nodenumber)

    # *******************************************************************************

    def get_datadump(self, nodenumber):
        r = requests.get('http://localhost:' + '8' + str(nodenumber) + '90' + '/factomd?item=dataDump')
        dump = json.loads(r.text)['DataDump5']['RawDump']
        found = ([m.start() + 23 for m in re.finditer('Connected - IP:', dump)])
        connections = sorted([dump[z] for z in found])
        return connections

    def current_block(self, nodenumber=1):
        summary = json.loads(self.debug_api('summary', str(nodenumber)))['result']['Summary']
        current_block = summary.split('[')[1].split(' ')[-1]
        # self.timestamped_print('current_block', current_block)
        return current_block

    def current_block_minute(self, nodenumber=1):
        result = json.loads(self.factomd_api('current-minute', str(nodenumber)))['result']
        current_block = result['leaderheight']
        current_minute = result['minute']
        return current_block, current_minute

    def current_minute(self, nodenumber=1):
        minute = json.loads(self.debug_api('current-minute', str(nodenumber)))['result']['Minute']
        return minute

    def leader_height(self, nodenumber=1):
        leader_height = json.loads(self.factomd_api('heights', str(nodenumber)))['result']['leaderheight']
        return leader_height

    def factomd_api(self, method, nodenumber=1):
        url = 'http://' + 'localhost:' + '8' + str(nodenumber) + '88' + '/v2'
        headers = {'content-type': 'text/plain'}
        payload = {"jsonrpc": "2.0", "id": 0, "method": method}
        r = requests.get(url, data=json.dumps(payload), headers=headers)
        return r.text

    def factomd_api_with_parameters(self, method, nodenumber, params_dict):
        url = 'http://' + 'localhost:' + '8' + str(nodenumber) + '88' + '/v2'
        headers = {'content-type': 'text/plain'}
        payload = {"jsonrpc": "2.0", "id": 0, "params": params_dict, "method": method}
        r = requests.get(url, data=json.dumps(payload), headers=headers)
        return r.text

    def debug_api(self, method, nodenumber=1):
        url = 'http://' + 'localhost:' + '8' + str(nodenumber) + '88' + '/debug'
        headers = {'content-type': 'text/plain'}
        payload = {"jsonrpc": "2.0", "id": 0, "method": method}
        r = requests.get(url, data=json.dumps(payload), headers=headers)
        return r.text

    def debug_api_with_parameters(self, method, nodenumber, params_dict):
        url = 'http://' + 'localhost:' + '8' + str(nodenumber) + '88' + '/debug'
        headers = {'content-type': 'text/plain'}
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


    def test_multiple_elections_different_blocks(self):
        config_file = self.data['LAAAALLLL']
        # change target minute to check elections occurring at different minutes
        target_minute = 5

        initial_audit_server_list, initial_federated_server_list = self.initialize_network(config_file, target_minute)

        # fault 2 leaders
        self.timestamped_print('faulting nodes 8 and 9')
        net.nettool.main(command='ins', fromvar='node7', to='node8', action='deny', file=config_file)
        cutoff_height = self.leader_height(1)
        self.timestamped_print('cutoff_height', cutoff_height)

        self.wait_for_new_block(cutoff_height, errormessage='Node 1 did not advance after faulting')

        current_audit_server_list, current_federated_server_list = self.get_servers()

        # verify 2 audit servers promotion
        promoted = 0
        for initial_audit_server in initial_audit_server_list:
            if initial_audit_server in current_federated_server_list: promoted += 1
        self.assertEquals(promoted, 2, 'Audit servers not promoted')
        self.timestamped_print('Audit servers properly promoted')

        # verify node 8 demotion
        self.assertIn(initial_federated_server_list[-1], current_audit_server_list,
                      'Federated server ' + initial_federated_server_list[-1] + ' not demoted')
        self.timestamped_print('node 8 properly demoted')

        # verify node9 demotion
        self.assertIn(initial_federated_server_list[-3], current_audit_server_list,
                      'Federated server ' + initial_federated_server_list[-3] + ' not demoted')
        self.timestamped_print('node 9 properly demoted')

        # # reconnect lost nodes
        # self.timestamped_print('reconnecting nodes 6 and 7')
        # net.nettool.main(command='ins', fromvar='node5', to='node6', action='allow', file=config_file)
        #
        # # wait for reconnected node 6 to restart
        # self.timestamped_print('waiting for reconnected node 6 to sync')
        # self.wait_for_new_block(cutoff_height, 6, 'Reconnected_node 6 did not resync')
        # self.timestamped_print('Reconnected_node6 properly resyncing')
        #
        # # wait for reconnected node 7 to restart
        # self.timestamped_print('waiting for reconnected node 7 to sync')
        # self.wait_for_new_block(cutoff_height, 7, 'Reconnected_node 7 did not resync')
        # self.timestamped_print('Reconnected_node 7 properly resyncing')
        #
        # # wait for node 6 and node 7 to be told they are now audit servers
        # self.timestamped_print('waiting for node 6 and node 7 to show themselves as audit servers')
        # for x in range(0, self.WAITTIME):
        #     one = self.get_servers()
        #     six = self.get_servers(6)
        #     seven = self.get_servers(7)
        #     if one == six and one == seven: break
        #     time.sleep(1)
        # self.assertTrue(one == six and one == seven, 'node 6 and node 7 were not informed of their audit status')
        # self.timestamped_print('node 6 and node 7 acknowledge they are audit servers')



        # we are now in next block

        # fault 2 other leaders
        self.timestamped_print('faulting nodes 6 and 7')
        net.nettool.main(command='ins', fromvar='node5', to='node6', action='deny', file=config_file)
        cutoff_height = self.leader_height(1)
        self.timestamped_print('cutoff_height', cutoff_height)

        self.wait_for_new_block(cutoff_height, errormessage='Node 1 did not advance after faulting')

        current_audit_server_list, current_federated_server_list = self.get_servers()
        self.timestamped_print('initial_audit_server_list', initial_audit_server_list)
        self.timestamped_print('initial_federated_server_list', initial_federated_server_list)
        self.timestamped_print('current_audit_server_list', current_audit_server_list)
        self.timestamped_print('current_federated_server_list', current_federated_server_list)

        # verify audit server promotion
        promoted = 0
        for initial_audit_server in initial_audit_server_list:
            if initial_audit_server in current_federated_server_list: promoted += 1
        self.assertEquals(promoted, 4, 'Audit servers not promoted')
        self.timestamped_print('Audit servers properly promoted')

        # verify node 6 demotion
        self.assertIn(initial_federated_server_list[-2], current_audit_server_list,
                      'Federated server ' + initial_federated_server_list[-2] + ' not demoted')
        self.timestamped_print('node 7 properly demoted')

        # verify node 7 demotion
        self.assertIn(initial_federated_server_list[-4], current_audit_server_list,
                      'Federated server ' + initial_federated_server_list[-4] + ' not demoted')
        self.timestamped_print('node 8 properly demoted')


    def test_repeat_multiple_elections_different_blocks(self):
        for x in range(1, 1001):
            print()
            self.timestamped_print('****run****', x)
            self.test_network_down()
            self.test_multiple_elections_different_blocks()


    # *********************************************************************************

    def test_one(self):
        network = 'LLLAALL'
        config_file = self.data[network]
        initial_audit_server_list, initial_federated_server_list = self.initialize_network(config_file)

        for x in range(0, 100):
            one = self.get_servers()
            six = self.get_servers(6)
            self.timestamped_print('one', one)
            self.timestamped_print('six', six)
            if one == six: break
            time.sleep(1)
        self.assertTrue(one == six, 'node 6 and node 7 were not informed of their audit status')


    def test_connections(self):
        network = 'LLLL_mesh'
        config_file = self.data[network]

        self.initialize_network(config_file)
        for node in range(1, 5): self.timestamped_print('node', node, 'connections', self.get_datadump(node))


    def test_connection_monitor(self):
        network = 'LLLL_mesh'
        config_file = self.data[network]

        # /home/factom/PycharmProjects/election_tests/net/suite/nettool.main(command='ins', fromvar='node2', to='node3', action='allow', file=config_file)
        net.nettool.main(command='ins', fromvar='node2', to='node3', action='allow', file=config_file)
        for x in range(1, 311):
            self.timestamped_print(x, 'seconds')
            for node in range(1, 5): self.timestamped_print('node', node, 'connections', self.get_datadump(node))
            time.sleep(1)


    # *********************************************************************************

    def test_partition(self):
        network = 'LLLL'
        config_file = self.data[network]

        self.initialize_network(config_file)
        for node in range(1, 5): self.timestamped_print('node', node, 'connections', self.get_datadump(node))

        self.timestamped_print('partitioning network')
        net.nettool.main(command='ins', fromvar='node2', to='node3', action='deny', file=config_file)
        cutoff_height = self.leader_height(1)
        self.timestamped_print('cutoff_height', cutoff_height)

        self.timestamped_print('verifying network stall')
        for seconds in range(0, self.WAITTIME):
            height = self.leader_height(1)
            self.timestamped_print('node 1 height', str(height).rjust(3), 'seconds', str(seconds).rjust(3))
            if height > cutoff_height: break
            time.sleep(1)
        self.assertEqual(height, cutoff_height, 'Partitioned Network did not stall')
        self.timestamped_print('verifyied network stall')
        for node in range(1, 5): self.timestamped_print('node', node, 'connections', self.get_datadump(node))

        self.wallet_api('import-addresses', 1, {'addresses': [{'secret': self.data['factoid_wallet_address1']},
                                                              {'secret': self.data['factoid_wallet_address2']}]})

        transaction_name = 'here_to_there'
        self.factomd_api_with_parameters('new-transaction', 1, {'tx-name': 'here_to_there'})
        self.factomd_api_with_parameters('add-input', 1, {'tx-name': 'here_to_there'})

        self.timestamped_print('restoring network')
        net.nettool.main(command='ins', fromvar='node2', to='node3', action='allow', file=config_file)
        cutoff_height = self.leader_height(1)
        self.timestamped_print('cutoff_height', cutoff_height)

        self.timestamped_print('verifying network restart')
        for seconds in range(0, self.WAITTIME):
            height = self.leader_height(1)
            self.timestamped_print('node 1 height', str(height).rjust(3), 'seconds', str(seconds).rjust(3))
            if height > cutoff_height: break
            time.sleep(1)
        self.assertGreater(height, cutoff_height, 'Network did not restart')
        for node in range(1, 5): self.timestamped_print('node', node, 'connections', self.get_datadump(node))


    def test_transactions(self):
        transaction_name = 'here_to_there4'
        self.timestamped_print(self.wallet_api('all-addresses'))
        self.timestamped_print(self.factomd_api_with_parameters('factoid-balance', 1,
                                               {"address": 'FA2hWZgbpJKeVQhYckHML2XuJV4DgHoN7ZgBRpWdNh1rpqjR931F'}))
        self.timestamped_print(self.factomd_api_with_parameters('factoid-balance', 1,
                                               {"address": 'FA3EPZYqodgyEGXNMbiZKE5TS2x2J9wF8J9MvPZb52iGR78xMgCb'}))
        print()

        importer = self.wallet_api_with_parameters('import-addresses', {
            'addresses': [{'secret': self.data['input_private_address'], 'secret': self.data['output_private_address']}]})
        self.timestamped_print('importer', importer)
        print()

        self.timestamped_print(self.factomd_api_with_parameters('factoid-balance', 1,
                                               {"address": 'FA2hWZgbpJKeVQhYckHML2XuJV4DgHoN7ZgBRpWdNh1rpqjR931F'}))
        self.timestamped_print(self.factomd_api_with_parameters('factoid-balance', 1,
                                               {"address": 'FA3EPZYqodgyEGXNMbiZKE5TS2x2J9wF8J9MvPZb52iGR78xMgCb'}))
        print()

        new = self.wallet_api_with_parameters('new-transaction', {'tx-name': transaction_name})
        self.timestamped_print('new', new)
        print()

        input = self.wallet_api_with_parameters('add-input',
                                                {'tx-name': transaction_name, 'address': self.data['input_public_address'],
                                                 'amount': 100000000})
        self.timestamped_print('input', input)
        print()

        output = self.wallet_api_with_parameters('add-output', {'tx-name': transaction_name,
                                                                'address': self.data['output_public_address'],
                                                                'amount': 100000000})
        self.timestamped_print('output', output)
        print()

        fee = self.wallet_api_with_parameters('sub-fee',
                                              {'tx-name': transaction_name, 'address': self.data['output_public_address']})
        self.timestamped_print('fee', fee)
        print()

        sign = self.wallet_api_with_parameters('sign-transaction', {'tx-name': transaction_name})
        self.timestamped_print('sign', sign)
        print()

        compose = self.wallet_api_with_parameters('compose-transaction', {'tx-name': transaction_name})
        self.timestamped_print('compose', compose)
        self.timestamped_print('result', json.loads(compose)['result'])
        print()

        submit = self.factomd_api_with_parameters('factoid-submit', 1,
                                                  {'transaction': json.loads(compose)['result']['params']['transaction']})
        self.timestamped_print('submit', submit)
        print()

        self.timestamped_print('node 1 height', str(self.leader_height(1)).rjust(3))
        for seconds in range(0, self.WAITTIME):
            pend = self.factomd_api_with_parameters('pending-transactions', 1, {'address': 'output_public_address'})
            self.timestamped_print('pend', pend, seconds, 'seconds')
            ack = self.factomd_api_with_parameters('factoid-ack', 1, {'txid': json.loads(submit)['result']['txid']})
            self.timestamped_print('ack', ack, seconds, 'seconds')
            print()
            time.sleep(1)


    # *******************************************************************************

    def test_time_entries(self):
        self.timestamped_print(self.wallet_api('all-addresses'))

        # transaction_name = 'buy_entry_credits'
        # self.wallet_api_with_parameters('import-addresses', {'addresses': [                   {'secret':self.data['input_private_address']}]})
        #
        # self.timestamped_print(self.factomd_api_with_parameters('factoid-balance', 1, {"address":self.data['input_private_address']}))
        # print()
        #
        # new = self.wallet_api_with_parameters('new-transaction', {'tx-name':transaction_name})
        # print('new', new)
        # print()
        #
        # input = self.wallet_api_with_parameters('add-input', {'tx-name':transaction_name,'address':self.data['input_public_address'], 'amount':100000000})
        # print('input', input)
        # print()
        #
        # output = self.wallet_api_with_parameters('add-output', {'tx-name':transaction_name,'address':self.data['output_public_address'], 'amount':100000000})
        # print('output', output)
        # print()
        #
        # fee = self.wallet_api_with_parameters('sub-fee', {'tx-name':transaction_name,'address':self.data['output_public_address']})
        # print('fee', fee)
        # print()
        #
        # sign = self.wallet_api_with_parameters('sign-transaction', {'tx-name':transaction_name})
        # print('sign', sign)
        # print()
        #
        # compose = self.wallet_api_with_parameters('compose-transaction', {'tx-name':transaction_name})
        # print('compose', compose)
        # print('result', json.loads(compose)['result'])
        # print()
        #
        # submit = self.factomd_api_with_parameters('factoid-submit', 1, {'transaction':json.loads(compose)['result']['params']['transaction']})
        # print('submit', submit)
        # print()
        #
        # print('node 1 height', str(self.leader_height(1)).rjust(3))
        # for seconds in range(0, self.WAITTIME):
        #     pend = self.factomd_api_with_parameters('pending-transactions', 1, {'address':'output_public_address'})
        #     print('pend', pend, seconds, 'seconds')
        #     ack = self.factomd_api_with_parameters('factoid-ack', 1, {'txid':json.loads(submit)['result']['txid']})
        #     print('ack', ack, seconds, 'seconds')
        #     print()
        #     time.sleep(1)
        #


    def test_unlimited_election_broadcast(self):
        network = 'LLALL_mesh'
        config_file = self.data[network]

        initial_audit_server_list, initial_federated_server_list = self.initialize_network(config_file)

        # fault leader
        self.timestamped_print('isolating node 4')
        net.nettool.main(command='ins', fromvar='*', to='node4', action='deny', file=config_file)
        net.nettool.main(command='ins', fromvar='node4', to='*', action='deny', file=config_file)

        self.wait_for_new_block(errormessage='Node 1 did not advance after faulting')

        current_audit_server_list, current_federated_server_list = self.get_servers()

        # verify node 3 promotion
        for initial_audit_server in initial_audit_server_list: self.assertIn(initial_audit_server,
                                                                             current_federated_server_list,
                                                                             'Audit server ' + initial_audit_server + ' not promoted')
        self.timestamped_print('node 3 properly promoted')

        # verify node 4 demotion
        self.assertIn(initial_federated_server_list[-1], current_audit_server_list,
                      'Federated server ' + initial_federated_server_list[-1] + ' not demoted')
        self.timestamped_print('node 4 properly demoted')

        # reconnect lost node
        self.timestamped_print('reconnecting node 4')
        net.nettool.main(command='ins', fromvar='*', to='node4', action='allow', file=config_file)
        net.nettool.main(command='ins', fromvar='node4', to='*', action='allow', file=config_file)

        self.wait_for_new_block(errormessage='Node 1 did not advance after reconnection')

        # node syncing?
        self.timestamped_print('waiting for reconnected node to sync')
        self.wait_for_new_block(4, 'Reconnected_node 4 did not resync')
        self.timestamped_print('Reconnected_node 4 properly resyncing')

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











