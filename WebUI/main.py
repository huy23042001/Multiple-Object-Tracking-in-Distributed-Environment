from base64 import b64decode, b64encode
import json
import time
import cv2
import numpy as np
from flask import Flask, Response, jsonify, render_template, request
from kafka import KafkaConsumer
import logging, os, sys, time
from pygtail import Pygtail
from send_mail import SendMail
import multiprocessing.dummy as mp
from datetime import datetime
from sqlquery import MySQLBuilder

bootstrap_servers=['192.168.56.102:9092', '192.168.56.103:9093']
topics = ["stream_0", "stream_1"]
email = SendMail()
mydb = MySQLBuilder()
def b64_to_img(b64):
    im_bytes=b64decode(b64)
    return im_bytes 

cameras = mydb.execute("select * from cameras")

def encode(frame):
    _, buff = cv2.imencode('.jpg', frame)
    b64 = b64encode(buff).decode()
    return b64
# Set the consumer in a Flask App
app = Flask(__name__)
app.config["SECRET_KEY"] = "SECRETKEYSECRETKEYSECRETKEYSECRETKEYSECRETKEY"
app.config["DEBUG"] = os.environ.get("FLASK_DEBUG", True)
app.config["JSON_AS_ASCII"] = False

LOG_FILE = 'app.log'
log = logging.getLogger('__name__')

@app.route('/', methods=['GET', 'POST'])
def index():
    log.info("route =>'/env' - hit!")
    return render_template('index1.html', len=len(cameras), cameras = cameras)

@app.route('/query', methods=['GET', 'POST'])
def query():
    return render_template('query.html', len=len(cameras), cameras = cameras)

@app.route('/submit', methods=['GET','POST'])
def submit():
    db = MySQLBuilder()
    data = json.loads(request.data)
    print(data)
    query = "select c.id, c.location, send_time, substring(log_content,1, length(log_content)-1) from event_logs e inner join cameras c on e.camera_id = c.id"
    str_filter = ""
    if (data["camera_id"] != "-1"):
        str_filter += " where camera_id = " + str(data["camera_id"])
    # if (data["camera_id"])
    if (data["start"] != ""):
        dt = datetime.strptime(data["start"].strip(), '%m/%d/%Y %H:%M:%S')    
        if (str_filter != ""):
            str_filter+=" and send_time > '" + str(dt) + "'"
        else:
            str_filter+=" where send_time > '" + str(dt) + "'"
    if (data["end"] != ""):
        dt = datetime.strptime(data["end"].strip(), '%m/%d/%Y %H:%M:%S')    
        if (str_filter != ""):
            str_filter+=" and send_time < '" + str(dt) + "'"
        else:
            str_filter+=" where send_time < '" + str(dt) + "'"
    objs = data["objects"]
    for i in objs:
        if str_filter != "":
            str_filter += " and log_content like '%" + str(i["value"]) + "  " + i["key"].lower()  + "%'"
        else:
            str_filter += " where log_content like '%" + str(i["value"]) + "  " + i["key"].lower()  + "%'"
    
    query +=str_filter + " order by send_time"
    sql_results = db.execute(query)
    final_results = []
    for r in sql_results:
        item = list(r)
        item[2] = str(item[2])
        final_results.append(item)
    return jsonify(sql_results)
@app.route('/log')
def progress_log():
	def generate():
		for line in Pygtail(LOG_FILE, every_n=1):
			yield "data:" + str(line) + "\n\n"
			time.sleep(0.5)
	return Response(generate(), mimetype= 'text/event-stream')

@app.route('/video/<int:topic>', methods=['GET'])
def video_feed(topic):
    return Response(
        get_video_stream(topic), 
        mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/video/<filename>')
def video(filename):
    return render_template('video.html',file=filename)

def get_video_stream(topic):
    consumer = KafkaConsumer(
            "stream_"+str(topic), 
            bootstrap_servers=['192.168.56.102:9092', '192.168.56.103:9093'])
    for msg in consumer:
        msg_data = json.loads(msg.value)
        if (msg_data["log"] != ""):
            email.send("Camera_ID " + str(msg_data["camera_id"]) + ": " + msg_data["log"])
            f = open("app.log", "a")
            f.write("\n" + "Camera_ID " + str(msg_data["camera_id"]) + ": " + msg_data["log"])
            f.close() 
        yield (b'--frame\r\n'
               b'Content-Type: image/jpg\r\n\r\n' + b64_to_img(msg_data["data"]) + b'\r\n\r\n')
    
def gen(id):
    cam = cv2.VideoCapture(cameras[id][1])
    while True:
        success, frame = cam.read()  # read the camera frame
        if not success:
            break
        else:
            ret, buffer = cv2.imencode('.jpg', frame)
            frame = buffer.tobytes()
            f = open("app.log", "a")
            f.write("\n" + "Camera_ID " + str(id)+ ": " + "log..............")
            f.close()
            yield (b'--frame\r\n'
                b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n\r\n')
            # time.sleep(1)

if __name__ == "__main__":
    app.run(host='localhost', port="5000", debug=True)
