import json
import os

def read_data_from_json(file_name):
    """
    Parse json
    :param file_name: json file
    :return: parsed json
    """
    directory = os.path.dirname(__file__)
    filename = os.path.join(directory, '../'+file_name)

    with open(filename) as f:
        json_data = f.read()
        return json.loads(json_data)