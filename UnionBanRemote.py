import json
import os
import re
from configparser import ConfigParser

from flask import Flask, request, jsonify

# 读取配置文件
config = ConfigParser()
config.read('config.ini')

# 获取配置
PORT_SEND = int(config.get('server', 'port_send'))
PORT_RECEIVE = int(config.get('server', 'port_receive'))
DATA_FILE = config.get('server', 'data_file')
SECRET = config.get('server', 'secret')

app = Flask(__name__)

# 正则表达式
regex = re.compile(r'"uuid":"([0-9a-fA-F-]+)","reason":"([^"]+)","time":"([^"]+)"$')


# 接收数据的路由
@app.route('/', methods=['POST'])
def receive_data():
    data = request.json
    if isinstance(data, dict):
        # 检查secret字段
        if 'secret' not in data or data['secret'] != SECRET:
            return 'Fault: Invalid secret.', 403

        data_str = json.dumps(data)
        match = regex.match(data_str)
        if match:
            # 保存数据到文件
            save_ban_data(data)
            return 'Data received and saved.', 200
        else:
            return 'Invalid data format.', 400
    else:
        return 'Invalid data format.', 400


# 发送数据的路由
@app.route('/', methods=['GET'])
def send_data():
    ban_data = read_ban_data()
    return jsonify(ban_data)


# 读取ban-data.json文件中的数据
def read_ban_data():
    if not os.path.exists(DATA_FILE):
        return []
    with open(DATA_FILE, 'r') as file:
        return json.load(file)


# 将数据保存到ban-data.json文件
def save_ban_data(data):
    ban_data = read_ban_data()
    ban_data.append(data)
    with open(DATA_FILE, 'w') as file:
        json.dump(ban_data, file, indent=2)


if __name__ == '__main__':
    # 启动两个服务器实例
    from threading import Thread


    def run_server(port):
        app.run(port=port)


    thread_send = Thread(target=run_server, args=(PORT_SEND,))
    thread_receive = Thread(target=run_server, args=(PORT_RECEIVE,))

    thread_send.start()
    thread_receive.start()

    thread_send.join()
    thread_receive.join()
