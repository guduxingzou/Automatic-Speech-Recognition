#-*- coding:utf-8 -*-
#!/usr/bin/python

''' This file is designed to train the models of ASR
author:

      iiiiiiiiiiii            iiiiiiiiiiii         !!!!!!!             !!!!!!    
      #        ###            #        ###           ###        I#        #:     
      #      ###              #      I##;             ##;       ##       ##      
            ###                     ###               !##      ####      #       
           ###                     ###                 ###    ## ###    #'       
         !##;                    `##%                   ##;  ##   ###  ##        
        ###                     ###                     $## `#     ##  #         
       ###        #            ###        #              ####      ####;         
     `###        -#           ###        `#               ###       ###          
     ##############          ##############               `#         #     
     
date:2016-11-09
'''
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import argparse
import time
import os
from six.moves import cPickle
from functools import wraps

import numpy as np
import tensorflow as tf
from tensorflow.python.ops import ctc_ops as ctc
from tensorflow.python.ops import rnn_cell
from tensorflow.python.ops.rnn import bidirectional_rnn

from model import Model

from utils import load_batched_data
from utils import describe
from utils import getAttrs
from utils import output_to_sequence
from utils import list_dirs
from utils import logging

class Trainer(object):
    
    def __init__(self):
	parser = argparse.ArgumentParser()
        parser.add_argument('--train_mfcc_dir', type=str, default='/home/pony/github/data/timit/train/mfcc/',
                       help='data directory containing mfcc numpy files, usually end with .npy')

        parser.add_argument('--train_label_dir', type=str, default='/home/pony/github/data/timit/train/label/',
                       help='data directory containing label numpy files, usually end with .npy')

        parser.add_argument('--test_mfcc_dir', type=str, default='/home/pony/github/data/timit/test/mfcc/',
                       help='data directory containing mfcc numpy files, usually end with .npy')

        parser.add_argument('--test_label_dir', type=str, default='/home/pony/github/data/timit/test/label/',
                       help='data directory containing label numpy files, usually end with .npy')

	parser.add_argument('--log_dir', type=str, default='/home/pony/github/ASR_libri/libri/cha-level/log/timit/',
                       help='directory to log events while training')

        parser.add_argument('--model', type=str, default='brnn',
                       help='set the model of ASR, ie: brnn')

	parser.add_argument('--keep', type=bool, default=True,
                       help='train the model based on model saved')

	parser.add_argument('--save', type=bool, default=True,
                       help='to save the model in the disk')

	parser.add_argument('--evaluation', type=bool, default=True,
                       help='train the model based on model saved')

        parser.add_argument('--learning_rate', type=float, default=0.001,
                       help='set the step size of each iteration')

        parser.add_argument('--num_epoch', type=int, default=200000,
                       help='set the total number of training epochs')

        parser.add_argument('--batch_size', type=int, default=32,
                       help='set the number of training samples in a mini-batch')

        parser.add_argument('--num_feature', type=int, default=39,
                       help='set the dimension of feature, ie: 39 mfccs, you can set 39 ')

        parser.add_argument('--num_hidden', type=int, default=128,
                       help='set the number of neurons in hidden layer')

        parser.add_argument('--num_class', type=int, default=62,
                       help='set the number of labels in the output layer, if timit phonemes, it is 62; if timit characters, it is 28; if libri characters, it is 28')

        parser.add_argument('--save_dir', type=str, default='/home/pony/github/ASR_libri/libri/cha-level/save/timit/',
                       help='set the directory to save the model, containing checkpoint file and parameter file')

        parser.add_argument('--restore_from', type=str, default='/home/pony/github/ASR_libri/libri/cha-level/save/timit/',
                       help='set the directory of check_point path')

        parser.add_argument('--model_checkpoint_path', type=str, default='/home/pony/github/ASR_libri/libri/cha-level/save/timit/model.ckpt0-0',
                       help='set the directory to restore the model, containing checkpoint file and parameter file')

	self.args = parser.parse_args()
	self.start(self.args)

    @describe
    def load_data(self,args,mode='train'):
  	if mode == 'train':	
            return load_batched_data(args.train_mfcc_dir,args.train_label_dir,args.batch_size)
  	elif mode == 'test':	
            return load_batched_data(args.test_mfcc_dir,args.test_label_dir,args.batch_size)
	else:
	    raise TypeError('mode should be train or test.')

    def start(self,args):
	# load data
        batchedData, maxTimeSteps, totalN = self.load_data(args,mode='train')
        test_batchedData, test_maxTimeSteps, test_totalN = self.load_data(args,mode='test')

	model = Model(args,maxTimeSteps)

        with tf.Session(graph=model.graph) as sess:
    	    print('Initializing')
    	    sess.run(model.initial_op)
	    if args.keep == True:
		ckpt = tf.train.get_checkpoint_state(args.restore_from)
		model_checkpoint_path = args.model_checkpoint_path
                if ckpt and ckpt.model_checkpoint_path:
                    model.saver.restore(sess, ckpt.model_checkpoint_path)
    		    print('Model restored from:'+args.restore_from) 
    
    	    for epoch in range(args.num_epoch):
		## training
		start = time.time()
        	print('Epoch', epoch+1, '...')
        	batchErrors = np.zeros(len(batchedData))
        	batchRandIxs = np.random.permutation(len(batchedData)) 
        	for batch, batchOrigI in enumerate(batchRandIxs):
            	    batchInputs, batchTargetSparse, batchSeqLengths = batchedData[batchOrigI]
                    batchTargetIxs, batchTargetVals, batchTargetShape = batchTargetSparse
                    feedDict = {model.inputX: batchInputs, model.targetIxs: batchTargetIxs, model.targetVals: batchTargetVals,model.targetShape: batchTargetShape, model.seqLengths: batchSeqLengths}

                    _, l, er, lmt = sess.run([model.optimizer, model.loss, model.errorRate, model.logitsMaxTest], feed_dict=feedDict)
	    	    print(output_to_sequence(lmt,mode='phoneme'))
                    if (batch % 1) == 0:
                	print('Minibatch', batch, '/', batchOrigI, 'loss:', l)
                	print('Minibatch', batch, '/', batchOrigI, 'error rate:', er)
            	    batchErrors[batch] = er*len(batchSeqLengths)
		    
		    if (args.save==True) and  ((epoch*len(batchRandIxs)+batch+1)%1000==0 or (epoch==args.num_epoch-1 and batch==len(batchRandIxs)-1)):
		        checkpoint_path = os.path.join(args.save_dir, 'model.ckpt'+str(epoch))
                        save_path = model.saver.save(sess,checkpoint_path,global_step=epoch)
                        print('Model has been saved in:'+str(save_path))
	        end = time.time()
		delta_time = end-start
		print('Epoch '+str(epoch+1)+' needs time:'+str(delta_time)+' s')	

		if args.save==True and (epoch+1)%1==0:
		    checkpoint_path = os.path.join(args.save_dir, 'model.ckpt'+str(epoch))
                    save_path = model.saver.save(sess,checkpoint_path,global_step=epoch)
                    print('Model has been saved in file')
                epochER = batchErrors.sum() / totalN
                print('Epoch', epoch+1, 'error rate:', epochER)
		logging(model.logfile,epoch,epochER,delta_time,mode='train')
		
		## evaluation
		if args.evaluation == True:
		    start = time.time()
		    test_model = Model(args,test_maxTimeSteps)

        	    with tf.Session(graph=test_model.graph) as test_sess:
    	                print('Initializing')
    	                test_sess.run(test_model.initial_op)
                    	test_model.saver.restore(test_sess, checkpoint_path)
    		    	print('test model restored from:'+checkpoint_path) 
        	    print('Epoch', epoch+1, '...')
        	    test_batchErrors = np.zeros(len(test_batchedData))
        	    test_batchRandIxs = np.random.permutation(len(test_batchedData)) 
        	    for test_batch, test_batchOrigI in enumerate(test_batchRandIxs):
            	        test_batchInputs, test_batchTargetSparse, test_batchSeqLengths = test_batchedData[test_batchOrigI]
                        test_batchTargetIxs, test_batchTargetVals, test_batchTargetShape = test_batchTargetSparse
                        test_feedDict = {test_model.inputX: test_batchInputs, test_model.targetIxs: test_batchTargetIxs, test_model.targetVals: test_batchTargetVals,test_model.targetShape: test_batchTargetShape, test_model.seqLengths: test_batchSeqLengths}
                        l, er, lmt = test_sess.run([test_model.loss, test_model.errorRate, test_model.logitsMaxTest], feed_dict=test_feedDict)
	    	        print(output_to_sequence(lmt,mode='phoneme'))
                        if (test_batch % 1) == 0:
                	    print('Minibatch', test_batch, '/', test_batchOrigI, 'loss:', l)
                	    print('Minibatch', test_batch, '/', test_batchOrigI, 'error rate:', er)
            	        test_batchErrors[test_batch] = er*len(test_batchSeqLengths)
	            end = time.time()
		    test_delta_time = end-start
                    test_epochER = test_batchErrors.sum() / test_totalN
                    print('Epoch', epoch+1, 'error rate:', test_epochER)
		    logging(model.logfile,epoch,test_epochER,test_delta_time,mode='test')
		    

if __name__ == '__main__':
    t=Trainer()
