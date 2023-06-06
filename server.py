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
global topics
topics = ["camera_0", "camera_1"]

hosts = "192.168.56.102:9092,192.168.56.103:9093"
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
            host="192.168.56.104",
            user="admin",
            password="password",
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
        user="admin",
        password="password",
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


def consum(topic):
    print(topic)
    consumer = KafkaConsumer(topic, bootstrap_servers = hosts.split(","), auto_offset_reset="latest", enable_auto_commit = True)
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
proc = threading.Thread(target=consum, args=("camera_0",))
proc1 = threading.Thread(target=consum, args=("camera_1",))
proc.start()
proc1.start()
proc.join()
proc1.join()
# p = mp.Pool(10)
# p.map(consum, topics)
# p.start()
# p.join()
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

