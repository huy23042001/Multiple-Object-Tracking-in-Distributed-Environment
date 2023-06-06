import argparse
from datetime import datetime
import json
from kafka import KafkaProducer
import time
import cv2
import base64
from sqlquery import MySQLBuilder
from multiprocessing import Process
import threading
producer = KafkaProducer(bootstrap_servers=['192.168.100.124:9092','192.168.100.125:9093'])
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

def run(id,source):
    camera = cv2.VideoCapture(source)
    topic = "camera_" + str(id)
    print(topic)
    while camera.grab():
        _, img = camera.retrieve()
        producer.send(topic, encode(id,img))
        time.sleep(2)
        print("camera " + str(id) + " sending")

# # block until all async messages are sent
# producer.flush()

# # configure multiple retries
# producer = KafkaProducer(retries=5)
if __name__  == '__main__':
    procs = []
    for cam in cameras: 
        proc =  threading.Thread(target=run, args=(cam[0], cam[1]))
        procs.append(proc)
        proc.start()
    # for proc in procs:
    #     proc.join()