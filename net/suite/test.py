import requests, json

# talk to node5 federated
url = 'http://' + "localhost:8588" + '/v2'
print ('url', url)
headers = {'content-type': 'text/plain'}
payload = {"jsonrpc": "2.0", "id": 0, "method": "current-minute"}
data = json.dumps(payload)
print ('data', data)

r = requests.get(url, data=json.dumps(payload), headers=headers)
print ('r', r)
print ('text', r.text)

# text {"jsonrpc":"2.0","id":0,"result":{"leaderheight":3,"directoryblockheight":2,"minute":0,"currentblockstarttime":1522963125403643755,"currentminutestarttime":1522963125393773036,"currenttime":1522967650243770100,"directoryblockinseconds":60,"stalldetected":true}}


