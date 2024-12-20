"""
Modifications copyright (C) 2020 Michael Strobl
"""

import time
import numpy as np
import tensorflow as tf

from entity_linker.models.base import Model

class CoherenceModel(Model):
    '''
    Input is sparse tensor of mention strings in mention's document.
    Pass through feed forward and get a coherence representation
    (keep same as context_encoded_dim)
    '''

    def __init__(self, num_layers, batch_size, input_size,
                 coherence_indices, coherence_values, coherence_matshape,
                 context_encoded_dim, scope_name, device,
                 dropout_keep_prob=1.0):

        # Num of layers in the encoder and decoder network
        self.num_layers = num_layers
        self.input_size = input_size
        self.context_encoded_dim = context_encoded_dim
        self.dropout_keep_prob = dropout_keep_prob
        self.batch_size = batch_size

        with tf.compat.v1.variable_scope(scope_name) as s, tf.device(device) as d:
            coherence_inp_tensor = tf.SparseTensor(coherence_indices,
                                                   coherence_values,
                                                   coherence_matshape)

            # Feed-forward Net for coherence_representation
            # Layer 1
            self.trans_weights = tf.compat.v1.get_variable(
              name="coherence_layer_0",
              shape=[self.input_size, self.context_encoded_dim],
              initializer=tf.random_normal_initializer(
                mean=0.0,
                stddev=1.0/(100.0)))

            # [B, context_encoded_dim]
            coherence_encoded = tf.compat.v1.sparse_tensor_dense_matmul(
              coherence_inp_tensor, self.trans_weights)
            coherence_encoded = tf.nn.relu(coherence_encoded)

            # Hidden Layers. NumLayers >= 2
            self.hidden_layers = []
            for i in range(1, self.num_layers):
                weight_matrix = tf.compat.v1.get_variable(
                  name="coherence_layer_"+str(i),
                  shape=[self.context_encoded_dim, self.context_encoded_dim],
                  initializer=tf.random_normal_initializer(
                    mean=0.0,
                    stddev=1.0/(100.0)))
                self.hidden_layers.append(weight_matrix)

            for i in range(1, self.num_layers):
                coherence_encoded = tf.nn.dropout(
                    coherence_encoded, keep_prob=self.dropout_keep_prob)
                coherence_encoded = tf.matmul(coherence_encoded,
                                              self.hidden_layers[i-1])
                coherence_encoded = tf.nn.relu(coherence_encoded)

            self.coherence_encoded = tf.compat.v1.nn.dropout(
                coherence_encoded, keep_prob=self.dropout_keep_prob)
