import base64
import json
import os
import re
from configparser import ConfigParser
from threading import Thread

from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad
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
regex = re.compile(
    r'"playerName":"([^"]+)","playerUuid":"([0-9a-fA-F-]+)","time":(\d+),"reason":"([^"]+)","sourceServer":"([^"]+)"}')


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
        existing_uuids = {item['playerUuid']: item for item in existing_data}

        if data['playerUuid'] in existing_uuids and existing_uuids[data['playerUuid']]['sourceServer'] == 'Pardon':
            existing_data.remove(existing_uuids[data['playerUuid']])
            # 使用新数据覆盖
            existing_data.append(data)
        else:
            # 检查数据是否已存在
            if data['playerUuid'] in existing_uuids:
                if data["time"] < existing_uuids[data['playerUuid']]['time']:
                    return False, '错误：数据已存在且过时'
                elif data["time"] > existing_uuids[data['playerUuid']]['time']:
                    existing_data.remove(existing_uuids[data['playerUuid']])
                else:
                    return True, '数据已同步成功'

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


def decrypt(encrypted_data, key):
    # 创建 AES 密钥
    secret_key = key.encode('utf-8')

    # 解码 Base64 编码的数据
    encrypted_bytes = base64.b64decode(encrypted_data)

    # 初始化 Cipher 实例
    cipher = AES.new(secret_key, AES.MODE_ECB)

    # 解密数据，使用 PKCS7 填充方式
    decrypted_bytes = unpad(cipher.decrypt(encrypted_bytes), AES.block_size, style='pkcs7')

    # 返回解密后的字符串
    return decrypted_bytes.decode('utf-8')


# 创建接收数据的Flask应用
app_receive = Flask(__name__)


@app_receive.route('/', methods=['POST'])
def receive_data():
    try:
        data = request.json
        data = decrypt(data["data"], SECRET)
        # 检查解密后的数据是否符合JSON格式
        try:
            data = json.loads(data)
        except json.JSONDecodeError:
            return '错误：解密后的数据不是有效的JSON格式', 400

        if not isinstance(data, dict):
            return '错误：无效的数据格式', 400

        # 保存数据到文件
        success, message = save_ban_data(data)
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
        # 去除每个数据项中的 'id' 字段
        data_without_id = [
            {key: value for key, value in item.items() if key != 'id'}  # 使用字典推导式移除 'id'
            for item in ban_data["data"]
        ]
        return jsonify(data_without_id)
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
