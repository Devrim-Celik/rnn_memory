"""
This file contains some simple logic for creating the desired type of recurrent cell and for
constructing the model functions.

This grew over time, I started out with the first couple of variants and later added more and
more complicated architectures, so the code is quite long, but don't let that intimidate you, it
is also quite straight forward. 

We have static and dynamic classification model functions, in case you want to use static_rnn or dynamic_rnn.
It should be noted though that the dynamic variant of the fast weights (the one which does not store the entire
matrix but calculates it from a list of old hidden states) does only work with static_rnn.
"""

from autoconceptor import Autoconceptor
from irnn_cell import IRNNCell
from fast_weight_cell import FastWeightCell
from dynamic_fast_weight_cell import DynamicFastWeightCell
from tensorflow.python.framework import ops
from tensorflow.python.util import nest
from tensorflow.python.ops import array_ops
from tensorflow.python.framework import tensor_shape
from tensorflow.python.ops import math_ops
from tensorflow.python.ops import init_ops
import tensorflow as tf
import numpy as np

def get_rnn_cell(cell_type, config):
    if(cell_type == 'rnn'):
        cell = tf.contrib.rnn.BasicRNNCell(config.layer_dim, dtype=config.dtype)
    elif(cell_type == 'multi_rnn'):
        cell = tf.nn.rnn_cell.MultiRNNCell([tf.contrib.rnn.BasicRNNCell(config.layer_dim, dtype=config.dtype) for _ in range(4)])
    elif(cell_type == 'lstm'):
        cell = tf.contrib.rnn.BasicLSTMCell(config.layer_dim, dtype=config.dtype)
    elif(cell_type == 'multi_lstm'):
        cell = tf.nn.rnn_cell.MultiRNNCell(
            [tf.contrib.rnn.DropoutWrapper(
                tf.nn.rnn_cell.LSTMCell(config.layer_dim,dtype=config.dtype),output_keep_prob=config.dropout_keep_prob) for _ in range(2)])
    elif(cell_type == 'irnn'):
        cell = IRNNCell(config.layer_dim,dtype=config.dtype)
    elif(cell_type == 'multi_irnn'):
        cell = tf.nn.rnn_cell.MultiRNNCell([IRNNCell(config.layer_dim,dtype=config.dtype) for _ in range(4)])
    elif(cell_type == 'fast_weights'):
        cell = FastWeightCell(num_units = config.layer_dim,
                              lam = config.fw_lambda,
                              eta = config.fw_eta, 
                              layer_norm = config.fw_layer_norm,
                              norm_gain = config.norm_gain,
                              norm_shift = config.norm_shift,
                              activation = config.fw_activation,
                              dtype=config.dtype)
    elif(cell_type == 'multi_fw'):
        cell = tf.nn.rnn_cell.MultiRNNCell([FastWeightCell(num_units = config.layer_dim,
                              lam = config.fw_lambda,
                              eta = config.fw_eta, 
                              layer_norm = config.fw_layer_norm,
                              norm_gain = config.norm_gain,
                              norm_shift = config.norm_shift,
                              activation = tf.nn.relu,
                              dtype=config.dtype,
                              kernel_initializer=init_ops.constant_initializer(
                value=np.concatenate((np.random.normal(loc=0.0, scale=0.001, size=(config.input_dim,config.layer_dim)),np.identity(config.layer_dim)),0),dtype=config.dtype)) for _ in range(config.layers)])
    elif(cell_type == 'identity_fw'):
        cell = FastWeightCell(num_units = config.layer_dim,
                              lam = config.fw_lambda,
                              eta = config.fw_eta, 
                              layer_norm = config.fw_layer_norm,
                              norm_gain = config.norm_gain,
                              norm_shift = config.norm_shift,
                              activation = tf.nn.tanh,
                              dtype=config.dtype,
                              kernel_initializer=init_ops.constant_initializer(
                value=np.concatenate((np.random.normal(loc=0.0, scale=0.001, size=(config.input_dim,config.layer_dim)),np.identity(config.layer_dim)),0),dtype=config.dtype))
    elif(cell_type == 'hybrid_front'):
        first_cell = FastWeightCell(num_units = config.layer_dim,
                              lam = config.fw_lambda,
                              eta = config.fw_eta, 
                              layer_norm = config.fw_layer_norm,
                              norm_gain = config.norm_gain,
                              norm_shift = config.norm_shift,
                              activation = tf.nn.relu,
                              dtype=config.dtype,
                              kernel_initializer=init_ops.constant_initializer(
                value=np.concatenate((np.random.normal(loc=0.0, scale=0.001, size=(config.input_dim,config.layer_dim)),np.identity(config.layer_dim)),0),dtype=config.dtype))
        cell = tf.nn.rnn_cell.MultiRNNCell([first_cell, IRNNCell(config.layer_dim), IRNNCell(config.layer_dim)])
    elif(cell_type == 'hybrid_back'):
        first_cell = FastWeightCell(num_units = config.layer_dim,
                              lam = config.fw_lambda,
                              eta = config.fw_eta, 
                              layer_norm = config.fw_layer_norm,
                              norm_gain = config.norm_gain,
                              norm_shift = config.norm_shift,
                              activation = tf.nn.relu,
                              dtype=config.dtype,
                              kernel_initializer=init_ops.constant_initializer(
                value=np.concatenate((np.random.normal(loc=0.0, scale=0.001, size=(config.input_dim,config.layer_dim)),np.identity(config.layer_dim)),0),dtype=config.dtype))
        cell = tf.nn.rnn_cell.MultiRNNCell([IRNNCell(config.layer_dim), IRNNCell(config.layer_dim), first_cell])
    elif(cell_type == 'dynamic_fast_weights'):
        cell = DynamicFastWeightCell(num_units = config.layer_dim, 
                                     sequence_length = config.input_length,
                                     lam = config.fw_lambda, 
                                     eta = config.fw_eta, 
                                     layer_norm = config.fw_layer_norm, 
                                     norm_gain = config.norm_gain,
                                     norm_shift = config.norm_shift,
                                     activation = config.fw_activation,
                                     batch_size = config.batchsize, 
                                     num_inner_loops = config.fw_inner_loops,
                                     dtype=config.dtype)
    elif(cell_type == 'autoconceptor'):
        cell = Autoconceptor(num_units = config.layer_dim, 
                             alpha = config.c_alpha, 
                             lam = config.c_lambda, 
                             batchsize = config.batchsize, 
                             activation=config.c_activation, 
                             layer_norm=config.c_layer_norm,
                             dtype=config.dtype)   
    else:
        raise ValueError("Cell type not understood.")
    
    return cell

def static_classification_model_fn(features, labels, mode, params):
    """Model Function"""

    config = params['config']
    inp = tf.unstack(tf.cast(features,config.dtype), axis=1)

    cell = get_rnn_cell(params['model'],config)
    outputs, _ = tf.nn.static_rnn(cell, inp, dtype=config.dtype)
    logits = tf.layers.dense(outputs[-1], config.output_dim, activation=None)

    # Compute predictions.
    predicted_classes = tf.argmax(logits, 1)
    if mode == tf.estimator.ModeKeys.PREDICT:
        predictions = {
            'class_ids': predicted_classes[:, tf.newaxis],
            'probabilities': tf.nn.softmax(logits),
            'logits': logits,
        }
        return tf.estimator.EstimatorSpec(mode, predictions=predictions)
    # Compute loss.
    loss = tf.losses.sparse_softmax_cross_entropy(labels=labels, logits=logits)

    # Compute evaluation metrics.
    accuracy = tf.metrics.accuracy(labels=labels,
                                   predictions=predicted_classes,
                                   name='acc_op')
    metrics = {'accuracy': accuracy}
    tf.summary.scalar('accuracy', accuracy[1])
    summary_op = tf.summary.merge_all()

    if mode == tf.estimator.ModeKeys.EVAL:
        return tf.estimator.EstimatorSpec(
            mode, loss=loss, eval_metric_ops=metrics)

    # Create training op.
    assert mode == tf.estimator.ModeKeys.TRAIN

    optimizer = config.optimizer
    if(config.clip_gradients):
        gvs = optimizer.compute_gradients(loss)
        capped_gvs = [(tf.clip_by_value(grad, config.clip_value_min, config.clip_value_max), var) for grad, var in gvs]
        train_op = optimizer.apply_gradients(capped_gvs, global_step=tf.train.get_global_step())
    else:
        train_op = optimizer.minimize(loss, global_step=tf.train.get_global_step())
    return tf.estimator.EstimatorSpec(mode, loss=loss, train_op=train_op)


def dynamic_classification_model_fn(features, labels, mode, params):
    """
    Model Function
    features should be [b_size,7,37] 
    """
    config = params['config']


    cell = get_rnn_cell(params['model'],config)

    outputs, _ = tf.nn.dynamic_rnn(cell, features, initial_state=cell.zero_state(config.batchsize, dtype=config.dtype),dtype=config.dtype)
    out = outputs[:,config.input_length-1,:]

    logits = tf.layers.dense(out, config.output_dim, activation=None)

    #logits += 1e-8 # to prevent NaN loss during training

    # Compute predictions.
    predicted_classes = tf.argmax(logits, 1)
    if mode == tf.estimator.ModeKeys.PREDICT:
        predictions = {
            'class_ids': predicted_classes[:, tf.newaxis],
            'probabilities': tf.nn.softmax(logits),
            'logits': logits,
        }
        return tf.estimator.EstimatorSpec(mode, predictions=predictions)
    # Compute loss.
    loss = tf.losses.sparse_softmax_cross_entropy(labels=labels, logits=logits)

    # Compute evaluation metrics.
    accuracy = tf.metrics.accuracy(labels=labels,
                                   predictions=predicted_classes,
                                   name='acc_op')
    metrics = {'accuracy': accuracy}
    tf.summary.scalar('accuracy', accuracy[1])

    if mode == tf.estimator.ModeKeys.EVAL:
        return tf.estimator.EstimatorSpec(
            mode, loss=loss, eval_metric_ops=metrics)

    # Create training op.
    assert mode == tf.estimator.ModeKeys.TRAIN

    optimizer = config.optimizer
    if(config.clip_gradients):
        gvs = optimizer.compute_gradients(loss)
        capped_gvs = [(tf.clip_by_value(grad, config.clip_value_min, config.clip_value_max), var) for grad, var in gvs]
        train_op = optimizer.apply_gradients(capped_gvs, global_step=tf.train.get_global_step())
    else:
        train_op = optimizer.minimize(loss, global_step=tf.train.get_global_step())
    return tf.estimator.EstimatorSpec(mode, loss=loss, train_op=train_op)



def scalar_model_fn(features, labels, mode, params):
    """Model Function"""

    config = params['config']

    inp = tf.unstack(tf.cast(features,config.dtype), axis=1)

    cell = get_rnn_cell(params['model'],config)

    outputs, _ = tf.nn.static_rnn(cell, inp, dtype=config.dtype)

    logits = tf.layers.dense(outputs[-1], config.output_dim, activation=None)

    #logits += 1e-8 # to prevent NaN loss during training

    if mode == tf.estimator.ModeKeys.PREDICT:
        predictions = logits
        return tf.estimator.EstimatorSpec(mode, predictions=predictions)
    # Compute loss.
    loss = tf.losses.mean_squared_error(labels=labels, predictions=logits)

    # Compute evaluation metrics.
    accuracy = tf.metrics.accuracy(labels=labels,
                                   predictions=tf.round(logits*10)/10,
                                   name='acc_op')
    metrics = {'accuracy': accuracy}
    tf.summary.scalar('accuracy', accuracy[1])

    if mode == tf.estimator.ModeKeys.EVAL:
        return tf.estimator.EstimatorSpec(
            mode, loss=loss, eval_metric_ops=metrics)

    # Create training op.
    assert mode == tf.estimator.ModeKeys.TRAIN

    optimizer = config.optimizer
    if(config.clip_gradients):
        gvs = optimizer.compute_gradients(loss)
        capped_gvs = [(tf.clip_by_value(grad, config.clip_value_min, config.clip_value_max), var) for grad, var in gvs]
        train_op = optimizer.apply_gradients(capped_gvs, global_step=tf.train.get_global_step())
    else:
        train_op = optimizer.minimize(loss, global_step=tf.train.get_global_step())
    return tf.estimator.EstimatorSpec(mode, loss=loss, train_op=train_op)

