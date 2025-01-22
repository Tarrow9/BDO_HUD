import socket
import requests

def get_local_ip():
    hostname = socket.gethostname()  # 호스트 이름 가져오기
    local_ip = socket.gethostbyname(hostname)  # IP 주소 가져오기
    response = requests.get('https://api.ipify.org?format=json')
    public_ip = response.json()['ip']
    return local_ip, hostname, public_ip

print("Local IP:", get_local_ip())
