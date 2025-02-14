import json
import os
import re
from configparser import ConfigParser
from threading import Thread
from flask import Flask, request, jsonify

# 读取配置文件
config = ConfigParser()
config.read('config.ini')

# 获取配置
PORT_SEND = int(config.get('server', 'port_send'))
PORT_RECEIVE = int(config.get('server', 'port_receive'))
DATA_FILE = config.get('server', 'data_file')
SECRET = config.get('server', 'secret')

# 确保数据文件存在
if not os.path.exists(DATA_FILE):
    with open(DATA_FILE, 'w') as file:
        json.dump({"data": [], "CountFinal": 0}, file, indent=2)

# 正则表达式
regex = re.compile(r'"playerUuid":"([0-9a-fA-F-]+)","reason":"([^"]+)","time":"([^"]+)","sourceServer":"([^"]+)","playerName":"([^"]+)"')

# 读取ban-data.json文件中的数据
def read_ban_data():
    try:
        with open(DATA_FILE, 'r') as file:
            return json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"data": [], "CountFinal": 0}

# 将数据保存到ban-data.json文件
def save_ban_data(data):
    try:
        ban_data = read_ban_data()

        # 检查 sourceServer 是否为 Pardon，如果是则删除对应 uuid 的数据
        existing_data = ban_data["data"]
        existing_uuids = {item['uuid']: item for item in existing_data}

        if data['uuid'] in existing_uuids and existing_uuids[data['uuid']]['sourceServer'] == 'Pardon':
            existing_data.remove(existing_uuids[data['uuid']])
            # 使用新数据覆盖
            existing_data.append(data)
        else:
            # 检查数据是否已存在
            if data['uuid'] in existing_uuids:
                return False, '错误：数据已存在'

            # 为新数据分配一个唯一的序号
            new_id = ban_data["CountFinal"] + 1
            data_with_id = {**data, 'id': new_id}
            existing_data.append(data_with_id)
            ban_data["CountFinal"] = new_id

        with open(DATA_FILE, 'w') as file:
            json.dump(ban_data, file, indent=2)
        return True, '数据保存成功'
    except Exception as e:
        raise RuntimeError(f'保存数据时出错: {str(e)}')

# 创建接收数据的Flask应用
app_receive = Flask(__name__)

@app_receive.route('/', methods=['POST'])
def receive_data():
    try:
        data = request.json
        if not isinstance(data, dict):
            return '错误：无效的数据格式', 400

        # 检查secret字段
        if 'secret' not in data or data['secret'] != SECRET:
            return '错误：无效的密钥', 403

        # 检查data字段是否存在
        if 'data' not in data:
            return '错误：缺少data字段', 400

        # 检查data字段是否符合正则表达式
        if not regex.search(json.dumps(data['data'])):
            return '错误：无效的数据格式', 400

        # 保存数据到文件
        success, message = save_ban_data(data['data'])
        if success:
            return '数据接收并保存成功', 200
        else:
            return message, 400
    except Exception as e:
        return f'错误：{str(e)}', 500

# 创建发送数据的Flask应用
app_send = Flask(__name__)

@app_send.route('/', methods=['GET'])
def send_data():
    try:
        ban_data = read_ban_data()
        return jsonify(ban_data["data"])
    except Exception as e:
        return f'错误：{str(e)}', 500

if __name__ == '__main__':
    # 启动两个服务器实例
    def run_server(app, port):
        app.run(host='0.0.0.0', port=port)

    thread_send = Thread(target=run_server, args=(app_send, PORT_SEND))
    thread_receive = Thread(target=run_server, args=(app_receive, PORT_RECEIVE))

    thread_send.start()
    thread_receive.start()

    thread_send.join()
    thread_receive.join()
