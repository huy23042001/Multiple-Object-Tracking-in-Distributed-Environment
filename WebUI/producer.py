import argparse
from datetime import datetime
import json
from kafka import KafkaProducer
from kafka.errors import KafkaError
from numpy import log
import time
import cv2
import base64
from sqlquery import MySQLBuilder
producer = KafkaProducer(bootstrap_servers=['192.168.56.102:9092','192.168.56.103:9093'])
mydb = MySQLBuilder()
cameras = mydb.execute("select * from cameras")

def encode(cam_id, frame):
    _, buff = cv2.imencode('.jpg', frame)
    b64 = base64.b64encode(buff).decode()
    send_time = datetime.now()
    data = {
        'camera_id': cam_id,
        'data': b64,
        'send_time': send_time.timestamp()
    }
    return json.dumps(data).encode('utf-8')
# def run(id):
#     camera = cv2.VideoCapture(id)
#     topic = "camera_" + str(id)

#     while camera.grab():
#         _, img = camera.retrieve()
#         producer.send("streaming", encode(id,img))
#         time.sleep(5)
#         print("sending")

def run(id):
    camera = cv2.VideoCapture(cameras[id][1])
    topic = "camera_" + str(id)
    print(topic)
    while camera.grab():
        _, img = camera.retrieve()
        producer.send(topic, encode(id,img))
        time.sleep(2)
        print("sending")

# # block until all async messages are sent
# producer.flush()

# # configure multiple retries
# producer = KafkaProducer(retries=5)
if __name__  == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--camera", action="store", dest="cam", type=int, default="0")
    args = parser.parse_args()
    run(args.cam)