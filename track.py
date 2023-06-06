import base64
from datetime import datetime
import json
from utils.general import (
    non_max_suppression, scale_coords, xyxy2xywh)
from utils.torch_utils import select_device, time_synchronized
from utils.datasets import letterbox
from kafka import KafkaProducer
from utils_ds.parser import get_config
from utils_ds.draw import draw_boxes
from deep_sort import build_tracker
from base64 import b64decode,b64encode
import os
import time
import numpy as np
import warnings
import cv2
import torch
import torch.backends.cudnn as cudnn
import sys
import pandas as pd
from mysql.connector import connect
from myobjects import TrackObj
from deep_sort.sort.track import Track
from deep_sort.sort.detection import Detection

class VideoTracker(object):
    def __init__(self, weights):
        currentUrl = os.path.dirname(__file__)
        sys.path.append(os.path.abspath(os.path.join(currentUrl, 'yolov5')))
        cudnn.benchmark = True
        print('Initialize DeepSORT & YOLO-V5')
        # ***************** Initialize ******************************************************
        self.img_size = 480                   # image size in detector, default is 640
        self.frame_interval = 2      # frequency
        self.conf_thres = 0.5
        self.iou_thres = 0.5
        self.agnostic_nms = False
        self.device = select_device("") # default is "cpu",cuda device, i.e. 0 or 0,1,2,3 or cpu'
        self.half = self.device.type != 'cpu'  # half precision only supported on CUDA
        self.augment=False
        self.tracks = []
        self.samples = {}
        # ***************************** initialize DeepSORT **********************************
        cfg = get_config()
        cfg.merge_from_file("./deep_sort.yaml")

        use_cuda = self.device.type != 'cpu' and torch.cuda.is_available()
        self.deepsort = build_tracker(cfg, use_cuda=use_cuda)

        # ***************************** initialize YOLO-V5 **********************************
        self.detector = weights  # load to FP32
        
        self.detector.to(self.device).eval()
        if self.half:
            self.detector.half()  # to FP16

        self.names = self.detector.module.names if hasattr(self.detector, 'module') else self.detector.names
        if self.device == 'cpu':
            warnings.warn("Running in cpu mode which maybe very slow!", UserWarning)  

    def image_track(self, im0, tracks, samples):
        """
        :param im0: original image, BGR format
        :return:
        """
        # preprocess ************************************************************
        # Padded resize
        self.Tracks_encode(tracks)
        self.Samples_encode(samples)
        img = letterbox(im0, new_shape=self.img_size)[0]
        # Convert
        img = img[:, :, ::-1].transpose(2, 0, 1)  # BGR to RGB, to 3x416x416
        img = np.ascontiguousarray(img)
        
        # numpy to tensor
        img = torch.from_numpy(img).to(self.device)
        img = img.half() if self.half else img.float()  # uint8 to fp16/32
        img /= 255.0  # 0 - 255 to 0.0 - 1.0
        if img.ndimension() == 3:
            img = img.unsqueeze(0)
        s = '%gx%g ' % img.shape[2:]    # print string

        # Detection time *********************************************************
        # Inference
        # t1 = time_synchronized()
        with torch.no_grad():
            pred = self.detector(img, augment=self.augment)[0]  # list: bz * [ (#obj, 6)]

        # Apply NMS and filter object other than person (cls:0)
        pred = non_max_suppression(pred, self.conf_thres, self.iou_thres,
                                   classes=None, agnostic=self.agnostic_nms)
        # t2 = time_synchronized()

        # get all obj ************************************************************
        det = pred[0]  # for video, bz is 1
        amount = 0
        if det is not None and len(det):  # det: (#obj, 6)  x1 y1 x2 y2 conf cls
            # Rescale boxes from img_size to original im0 size
            det[:, :4] = scale_coords(img.shape[2:], det[:, :4], im0.shape).round()

            bbox_xywh = xyxy2xywh(det[:, :4]).cpu()
            confs = det[:, 4:5].cpu()
            clss = det[:, -1].cpu()

            # ****************************** deepsort ****************************q
            outputs, self.tracks, self.samples = self.deepsort.update(bbox_xywh, confs, clss, im0, self.tracks, self.samples)

            # (#ID, 5) x1,y1,x2,y2,track_ID
        else:
            outputs = torch.zeros((0, 5))

        # t3 = time.time()
        s=""
        amount = 0
        if (len(outputs) > 0 ):
            
            bbox_xyxy = outputs[:, :4]
            identities = outputs[:, -2]
            clss=outputs[:,-1]
            class_names = []
            for i in clss:
                class_names.append(self.names[i])
            im0 = draw_boxes(im0, bbox_xyxy, class_names, identities)
            tensor_clss = torch.from_numpy(clss)
            for c in tensor_clss.unique():
                n = (tensor_clss[:] == c).sum()  # detections per class
                amount+= int(n)
                s += str(int(n)) + " " + self.names[int(c)] + ","
            s = s.rstrip(s[-1])
        # return outputs, im0, t2-t1, t3-t2, s, amount
        return im0, s, amount, self.getTracks(), self.getSamples()
    
    def Samples_encode(self, json_samples):
        if json_samples != "":
            self.samples = {}
            tmp = json.loads(json_samples)
            print(tmp)
            for k in tmp:
                self.samples[int(k)] = tmp[k] 
    def getSamples(self):
        for key in self.samples:
            for i in range(len(self.samples[key])):
                if type(self.samples[key][i]) is not list:      
                    self.samples[key][i] = self.samples[key][i].tolist()
        return json.dumps(self.samples)
    def getTracks(self):   
        ls = []  
        for track in self.tracks:
            track.class_id = int(track.class_id)
            track.mean = track.mean.tolist()
            track.covariance = track.covariance.tolist()
            if track.yolo_bbox != [0,0,0,0]:
                track.yolo_bbox.tlwh = track.yolo_bbox.tlwh.tolist()
                track.yolo_bbox.feature = track.yolo_bbox.feature.tolist()
                track.yolo_bbox = track.yolo_bbox.__dict__
            for i in range(len(track.features)):
                if (type(track.features[i]) is not list):
                    track.features[i] = track.features[i].tolist()
            ls.append(track.__dict__)
        return json.dumps(ls)
    
    def Tracks_encode(self, tracks_str):
        if tracks_str != '':
            tracks = json.loads(tracks_str)
            self.tracks =[]
            for track in tracks:
                if track["yolo_bbox"] != [0,0,0,0]:
                    track["yolo_bbox"] = Detection(track["yolo_bbox"]["tlwh"],
                    track["yolo_bbox"]["confidence"], track["yolo_bbox"]["feature"])
                self.tracks.append(Track(track["mean"], track["covariance"], track["track_id"], 
                    track["class_id"], track["_n_init"], track["_max_age"],track["features"], 
                    track["age"], track["time_since_update"], track["hits"], track["state"], 
                    track["yolo_bbox"]))
        
def b64_to_img(b64):
    im_bytes=b64decode(b64)
    arr=np.frombuffer(im_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, flags=cv2.IMREAD_COLOR)
    return img

def loaddata(df):
    row = df.values.tolist()[0]
    frame = b64_to_img(row[1])
    return row[0], frame, row[2]

def create_record(cam_id, send_time, amount, log, img, tracks, samples):
    obj = {
        "camera_id": cam_id,
        "send_time": send_time,
        "object_amount": amount,
        "log_content": log,
        "image": str(img),
        "tracks": tracks,
        "samples": samples
    }
    return obj

# def save_image(cam_id, frame, send_time, amount):
#     mydb = connect(
#         host="192.168.56.105",
#         user="admin",
#         password="password",
#         database="test") 
#     cursor = mydb.cursor()
#     # sql = "INSERT INTO frame (camera_id, send_time, data) VALUES (%s, %s, %s)"
#     # val = (cam_id, datetime.fromtimestamp(float(send_time)), frame)
#     # cursor.execute(sql, val)
#     mydb.commit()
#     cursor.close()
#     mydb.close()
def run(weight, msg, tracks):
    tracker = VideoTracker(weight)
    i=0
    for df in msg:
        cam_id, img, send_time = loaddata(df)
        # outputs, frame, yt, st, s, amount = tracker.image_track(img)
        frame, s, amount = tracker.image_track(img, tracks)
        _, buff = cv2.imencode(".jpg", frame)
        img = base64.b64encode(buff).decode()
        obj = create_record(cam_id, send_time, amount, s, img, tracker.getTracks())
        # datas.append(obj)
        yield pd.DataFrame([obj])
