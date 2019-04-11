nettool_file = '/home/factom/factom/network_testing_tool/factomd/support/net/nettool.py '
network_config_file = ' -f /home/factom/robertubuntu/network_testing_tool/factomd/support/net/suite/single_fault.yml'

# import sys
import subprocess
# sys.path.append('/home/factom/factom/network_testing_tool/factomd/support/net/')
# import nettool
import requests, json

# subprocess.call('/home/factom/factom/network_testing_tool/factomd/support/net/nettool.py up -f /home/factom/robertubuntu/network_testing_tool/factomd/support/net/suite/single_fault.yml', shell=True)
subprocess.call(nettool_file + 'up' + network_config_file, shell=True)

# nettool.py up -f /home/factom/robertubuntu/network_testing_tool/factomd/support/net/suite/single_fault.yml

# talk to node5 federated
# url = 'http://' + "localhost:8588" + '/v2'
# print ('url', url)
# headers = {'content-type': 'text/plain'}
# payload = {"jsonrpc": "2.0", "id": 0, "method": "current-minute"}
# data = json.dumps(payload)
# print ('data', data)

# r = requests.get(url, data=json.dumps(payload), headers=headers)
# print ('r', r)
# print ('text', r.text)

# text {"jsonrpc":"2.0","id":0,"result":{"leaderheight":3,"directoryblockheight":2,"minute":0,"currentblockstarttime":1522963125403643755,"currentminutestarttime":1522963125393773036,"currenttime":1522967650243770100,"directoryblockinseconds":60,"stalldetected":true}}



# /home/factom/PycharmProjects/factom_python_objects_library
