import subprocess
import unittest
import requests, json

from factomd.support.net import nettool
from helpers.helpers import read_data_from_json

class Commands(unittest.TestCase):
    data = read_data_from_json('test_data.json')

    def setUp(self):
        default_config_file = self.data['LLfLL']


    def test_network_bring_up(config_file=data['network_config_file_default']):
        nettool.main(command='up', file=config_file)

    def test_network_bring_up_build(self):
        nettool.main(command='up', build=True, file=self.data['network_config_file'])

    def test_network_status(self):
        nettool.main(command='status', file=self.data['network_config_file'])

    def test_docker_ps(self):
        subprocess.call("docker ps", shell=True)

    def test_weave_status_dns(self):
        subprocess.call("weave status dns", shell=True)

    def test_add34(self):
        nettool.main(command='ins', fromvar='node3', to='node4', action='allow', file=self.data['network_config_file'])

    def test_break34(self):
        nettool.main(command='ins', fromvar='node3', to='node4', action='deny', file=self.data['network_config_file'])

    def test_network_down(self, config_file=default_config_file):
        nettool.main(command='down', file=config_file)

    def test_network_down_destroy(self):
        nettool.main(command='down', destroy=True, file=self.data['network_config_file'])

    def _current_minute(self):
        url = 'http://' + "localhost:8188" + '/debug'
        print ('url', url)
        headers = {'content-type': 'text/plain'}
        payload = {"jsonrpc": "2.0", "id": 0, "method": "current-minute"}
        data = json.dumps(payload)
        print ('data', data)

        r = requests.get(url, data=json.dumps(payload), headers=headers)
        print ('r', r)
        print ('text', r.text)
        return r.text

