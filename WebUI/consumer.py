import json
import cv2
from kafka import KafkaConsumer
import concurrent.futures
class Consumer(object):
    def __init__(self,):
        self.consumer = KafkaConsumer(
            group_id = "my-group",
            bootstrap_servers=['192.168.56.102:9092', '192.168.56.103:9093'])
        self.consumer.subscribe(['stream_0','stream_1'])

    def stream(self):
        while True:
            # poll messages each certain ms
            raw_messages = self.consumer.poll(
                timeout_ms=100, max_records=200
            )
            # for each messages batch
            for topic_partition, messages in raw_messages.items():
                # if message topic is k_connectin_status
                if topic_partition.topic == 'camera_0':
                    # print(json.loads(messages.value)["camera_id"])
                    print(messages)
                # if message topic is k_armed_status
                elif topic_partition.topic == 'camera_1':
                    # print(json.loads(messages.value)["camera_id"])
                    print(messages)
consum = Consumer()
consum.stream()