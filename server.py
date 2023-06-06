from base64 import b64decode,b64encode
from datetime import datetime
import json
import cv2
from kafka import KafkaConsumer, KafkaProducer
import pandas as pd
import track
from track import VideoTracker
import torch
import numpy as np
from pyspark.sql import SparkSession
from pyspark.sql.functions import *
from pyspark.sql.types import *
from pyspark.sql.types import StructField, StructType, StringType
from mysql.connector import connect
import threading
from multiprocessing import Process
spark  =  SparkSession.builder.appName('video_tracking.com').getOrCreate()
spark.sparkContext.setLogLevel("WARN")
spark.sparkContext.addPyFile("DS.zip")
spark.sparkContext.addFile("deep_sort.yaml")
spark.sparkContext.addFile("ckpt.t7")
weights = torch.load("yolov5s.pt", map_location = "cpu")['model'].float()
dist_weights = spark.sparkContext.broadcast(weights)
global tracks
tracks= ''
global samples
samples= ''

hosts = "192.168.100.124:9092,192.168.100.125:9093"
schema = StructType([
        StructField("camera_id", IntegerType(),True),
        StructField("send_time", FloatType(),True),
        StructField("object_amount", IntegerType(),True),
        StructField("log_content", StringType(),True),
        StructField("image", StringType(),True),
        StructField("tracks", StringType(),True),
        StructField("samples", StringType(),True)
])      

msg_schema = StructType([
        StructField("camera_id", StringType(),True),
        StructField("data", StringType(),True),
        StructField("send_time", StringType(),True)       
])

def tracking(data):
    tracker = VideoTracker(dist_weights.value)
    global tracks
    global samples
    global mydb
    for df in data:
        cam_id, img, send_time = track.loaddata(df)
        # outputs, frame, yt, st, s, amount = tracker.image_track(img)
        frame, s, amount, tracks, samples = tracker.image_track(img, tracks, samples)
        _, buff = cv2.imencode(".jpg", frame)
        img = b64encode(buff).decode()
        obj = track.create_record(cam_id, send_time, amount, s, img, tracks, samples)
        mydb = connect(
            host="localhost",
            user="hduser",
            password="hduser@123",
            database="object_tracking") 
        cursor = mydb.cursor()
        sql = "INSERT INTO frame (camera_id, send_time, data) VALUES (%s, %s, %s)"
        val = (cam_id, datetime.fromtimestamp(float(send_time)), img)
        cursor.execute(sql, val)
        mydb.commit()
        cursor.close()
        mydb.close()
        # datas.append(obj)
        yield pd.DataFrame([obj])

def process(row):
    mydb = connect(
        host="192.168.56.104",
        user="hduser",
        password="hduser@123",
        database="object_tracking") 
    cursor = mydb.cursor()
    sel_query = "SELECT object_amount FROM event_logs where camera_id = %s ORDER BY ID DESC LIMIT 1"
    cursor.execute(sel_query, [row["camera_id"]])
    data = cursor.fetchall()
    count = cursor.rowcount
    log = row["log_content"]
    if count == 0 or data[0][0] != row["object_amount"]:
        query = "INSERT INTO event_logs (camera_id, send_time, object_amount, log_content) values (%s, %s, %s, %s)"
        val = (row["camera_id"], datetime.fromtimestamp(float(row["send_time"])), row["object_amount"], row["log_content"])
        cursor.execute(query, val)
    else:
        log = ""
    msg = {
        'camera_id': row["camera_id"],
        'data': row["image"],
        'send_time': row["send_time"],
        'log': log
    }
    producer = KafkaProducer(bootstrap_servers=hosts.split(","))
    producer.send("stream_" + str(row["camera_id"]), json.dumps(msg).encode('utf-8')) 
    mydb.commit()
    cursor.close()   


def consum(id):
    print("start with camera " + str(id))
    consumer = KafkaConsumer("camera_" + str(id), bootstrap_servers = hosts.split(","), auto_offset_reset="latest", enable_auto_commit = True)
    global tracks
    global samples
    for msg in consumer:  
        # tracks = acc_tracks.value
        df = spark.sparkContext.parallelize([json.loads(msg.value.decode("utf-8"))]).toDF()
        results_df = df.mapInPandas(tracking, schema)\
                    .select(col("camera_id"),
                            col("send_time"),
                            col("object_amount"),
                            col("log_content"),
                            col("image"),
                            col("tracks"),
                            col("samples"))
        tracks = results_df.select("tracks").collect()[0]["tracks"]
        samples = results_df.select("samples").collect()[0]["samples"]
        stream_df = results_df.select(col("camera_id"),
                            col("send_time"),
                            col("object_amount"),
                            col("log_content"),
                            col("image"))
        stream_df.foreach(process)

# def run(id):
#     thread = threading.Thread(target=consum(id))
#     thread1 = threading.Thread(target=consum(id+1))
#     thread2 = threading.Thread(target=consum(id+2))
#     thread.start()
#     thread1.start()
#     thread2.start()
if __name__ == '__main__':
    procs = []
    for i in range(1,13):
        proc = Process(target=consum, args=(i,))
        procs.append(proc)
        proc.start()
    for proc in procs:
        proc.join()
# proc = threading.Thread(target=consum, args=("camera_1",))
# proc1 = threading.Thread(target=consum, args=("camera_2",))
# proc2 = threading.Thread(target=consum, args=("camera_3",))
# proc3 = threading.Thread(target=consum, args=("camera_4",))
# proc4 = threading.Thread(target=consum, args=("camera_5",))
# proc5 = threading.Thread(target=consum, args=("camera_6",))
# proc6 = threading.Thread(target=consum, args=("camera_7",))
# proc7 = threading.Thread(target=consum, args=("camera_8",))
# proc8 = threading.Thread(target=consum, args=("camera_9",))
# proc9 = threading.Thread(target=consum, args=("camera_10",))
# proc.start()
# proc1.start()
# proc2.start()
# proc3.start()
# proc4.start()
# proc5.start()
# proc6.start()
# proc7.start()
# proc8.start()
# proc9.start()
# proc.join()
# proc1.join()
# proc2.join()
# proc3.join()
# proc4.join()
# proc5.join()
# proc6.join()
# proc7.join()
# proc8.join()
# proc9.join()

# df = spark.readStream\
#         .format("kafka")\
#         .option("kafka.bootstrap.servers", hosts)\
#         .option("subscribe", "streaming")\
#         .load()
    
# data_stream_df = df.select(col('value').cast('string').name("value"))\
#                     .select(from_json(col("value"),msg_schema).name("value"))\
#                     .mapInPandas(tracking, schema)\
#                     .select(col("camera_id"),
#                             col("send_time"),
#                             col("object_amount"),
#                             col("log_content"),
#                             col("image"))
                
# query = data_stream_df.writeStream\
#         .foreach(lambda r: process(r))\
#         .start()
# query.awaitTermination()

