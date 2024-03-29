import tensorflow as tf
import matplotlib.pyplot as plt
from sklearn.model_selection import train_test_split
import os
from tensorflow.data import Dataset,Iterator
from data.maker import slide_window

import numpy as np
import cv2
class ImageDateSet:
    def __init__(self,positive_dir,negative_dir,img_size=(12,12),batch=50):
        #output image size
        self.img_size = img_size
        #output image bathch
        self.batch = batch
        # where the positive data from
        self.positive_dir = positive_dir
        # where the negative data from
        self.negative_dir = negative_dir
        # get the file list
        file_list = os.listdir(positive_dir)
        # need to generate negative sample?
        if negative_dir is not None:
            file_list.extend(os.listdir(negative_dir))
        # data info
        data_label_info = [(file_name.split('_')[1],file_name.split('_')[2][:-4]) for file_name in file_list]
        self.data_info = []

        for idx,filename in enumerate(file_list):
            lab,pattern = data_label_info[idx]
            if lab == '0':
                self.data_info.append((os.path.join(negative_dir,filename),int(lab),int(pattern)))
            elif lab== '1':
                self.data_info.append((os.path.join(positive_dir,filename),int(lab),int(pattern)))
        # split the train and test
        self.data_train,self.data_test = train_test_split(self.data_info)

        # make Dataset
        self.dataset_train = Dataset.from_tensor_slices(self.conver(self.data_train)).map(self.load_img)
        self.dataset_train = self.dataset_train.shuffle(1000).batch(self.batch).repeat()

        self.dataset_test = Dataset.from_tensor_slices(self.conver(self.data_test)).map(self.load_img)
        self.dataset_test = self.dataset_test.shuffle(1000).batch(self.batch).repeat()
    def getIterator(self):
        iter_train = self.dataset_train.make_initializable_iterator()
        train_op = iter_train.make_initializer(self.dataset_train)
        element_train = iter_train.get_next()

        iter_test = self.dataset_test.make_initializable_iterator()
        test_op = iter_test.make_initializer(self.dataset_test)
        element_test = iter_test.get_next()
        return train_op,element_train,test_op,element_test
    def conver(self,info):
        paths=[]
        labs=[]
        ps=[]
        for path,lab,p in info:
            paths.append(path)
            labs.append(lab)
            ps.append(p)
        return (paths,labs,ps)
    def load_img(self,img_path,label,pattern):
        # read file
        img_file = tf.read_file(img_path)
        #decode the binary data to image
        img_decoded = tf.image.decode_jpeg(img_file, channels=3)
        # resize the image
        resized_image = tf.image.resize_images(img_decoded, [self.img_size[0], self.img_size[1]])
        # convert the label to one-hot encoding
        classes_num = 2
        clss = tf.one_hot(label, classes_num)
        # convert the pattern to one-hot encoding
        pattern_classes = 45
        pattern = tf.one_hot(pattern, pattern_classes)
        return (resized_image,clss,pattern)

def show_img(img,b=True,p=0.05):
    plt.imshow(img)
    plt.show(block=b)
    if not b:
        plt.pause(p)

def img_pyramids(img,pyramcount=3,winsize=(48,48),step=(10,10)):
    pyramids = [np.copy(img)]
    imgs_win = []
    bbox = []
    for i in range(1,pyramcount):
        pyr_img = cv2.pyrDown(pyramids[i-1])
        pyramids.append(pyr_img)
    for image in pyramids:
        for img_win,box in slide_window(image,stride=step,win=winsize):
            if img_win.shape[0] != winsize[0] or img_win.shape[1] != winsize[1]:
                continue
            imgs_win.append(img_win)
            bbox.append(box)
    return pyramids,imgs_win,bbox

def convert_box_pbox(box):
    x,y,w,h = box
    return [x,y,x+w,y+h]

def conver_pbox_box(box):
    x1,y1,x2,y2 = box
    w = x2-x1
    h = y2-y1
    return [x1,y1,w,h]

def overlap(box1,box2):
    in_x_min = max(box1[0],box2[0])
    in_y_min = max(box1[1],box2[1])
    in_x_max = min(box1[2],box2[2])
    in_y_max = min(box1[3],box2[3])
    if in_x_min>in_x_max or in_y_min>in_y_max:
        return 0.0,0.0,0.0
    _, _, w_in, h_in = conver_pbox_box([in_x_min,in_y_min,in_x_max,in_y_max])
    _, _, w_1, h_1 = conver_pbox_box(box1)
    _, _, w_2, h_2 = conver_pbox_box(box2)

    # compute the boxs' area
    in_area = w_in * h_in
    box1_area = w_1 * h_1
    box2_area = w_2 * h_2
    iou = in_area / float(box1_area+box2_area)
    box1_iou = in_area / float(box1_area)
    box2_iou = in_area / float(box2_area)
    return iou,box1_iou,box2_iou


def NMS(bboxs,probs,convert = True,thread=0.5):
    '''
    :param bboxs: [[x,y,w,h].....]
    :param probs [p1,p2,p3....]
    :return:
    '''
    if convert:
        boxs = []
        for box in bboxs:
            boxs.append(convert_box_pbox(box))
        bboxs = boxs
    index_box = np.argsort(np.array(probs) * -1)
    res_box= []

    used_box = [False for i in range(0,len(probs))]

    for bidx in index_box:
        box_prop_max = bboxs[bidx]
        if used_box[bidx]:
            continue
        res_box.append(box_prop_max)
        used_box[bidx] = True
        for idx,box in enumerate(bboxs):
            if used_box[idx]:
                continue
            _,box1_iou,box2_iou = overlap(box_prop_max,box)
            if box2_iou > thread or box1_iou>thread:
                used_box[idx] = True
    if convert:
        boxs = []
        for box in res_box:
            boxs.append(conver_pbox_box(box))
        res_box = boxs
    return res_box

def test_dataset():
    imgdataset = ImageDateSet('/home/dataset/FDDB/pos','/home/dataset/FDDB/neg',batch=50)
    train_op, ele_train, test_op, ele_test = imgdataset.getIterator()
    with tf.Session() as sess:
        sess.run(train_op)
        sess.run(test_op)
        while 1:
            d=sess.run(ele_train)
            print(d[0].shape)

def drwa_bbox(img_origin,bbox,convert=True,show = False):
    img = np.copy(img_origin)
    for box in bbox:
        if convert:
            box = convert_box_pbox(box)
        img = cv2.rectangle(img,(box[0],box[1]),(box[2],box[3]),color=(255,0,0),thickness=2)
    if show:
        show_img(img)
    return img

def test_pyr():
    img = plt.imread('../example/img_1275.jpg')
    img_pyramids(img)

def test_NMS():
    img = plt.imread('../example/img_1275.jpg')
    bboxs = [[10,10,30,40],[20,20,20,30],[60,20,30,40],[80,50,20,20]]
    prob = [0.9,0.7,0.8,0.4]
    drwa_bbox(img,bboxs,show=True)
    NMS_box = NMS(bboxs,prob,thread=0.1)
    drwa_bbox(img,NMS_box,show=True)

def one_hot(targets,deepth):
    #设置类别的数量
    num_classes = deepth
    #需要转换的整数
    #将整数转为一个10位的one hot编码
    return np.array(np.eye(deepth)[targets, :],dtype=int)

# Dataset test
if __name__ == '__main__':
    #test_pyr()
    # test_NMS()
    test_dataset()