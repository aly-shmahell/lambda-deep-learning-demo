"""
Copyright 2018 Lambda Labs. All Rights Reserved.
Licensed under
==========================================================================

"""
import importlib

import tensorflow as tf

from modeler import Modeler


class ImageClassificationModeler(Modeler):
  def __init__(self, args):
    super(ImageClassificationModeler, self).__init__(args)
    self.net = getattr(importlib.import_module("network." + self.args.network),
                       "net")
    self.style_layers = ('vgg_19/conv1/conv1_1', 'vgg_19/conv2/conv2_1',
                         'vgg_19/conv3/conv3_1', 'vgg_19/conv4/conv4_1',
                         'vgg_19/conv5/conv5_1')
    self.content_layers = 'vgg_19/conv4/conv4_2'

  def create_precomputation(self):
    self.global_step = tf.train.get_or_create_global_step()
    self.learning_rate = self.create_learning_rate_fn(self.global_step)

    self.style_features_target = {}
    for layer in self.style_layers:
      self.style_features_target[layer] = tf.placeholder(tf.float32)
    self.style_features_target_op = self.compute_style_feature()
    self.pre_compute_ops = {self.style_features_target[key]:
                            self.style_features_target_op[key]
                            for key in self.style_features_target}

  def model_fn(self, x):
    images = x[0]
    labels = x[1]
    logits, predictions = self.create_graph_fn(images)

    if self.args.mode == "train":
      loss = self.create_loss_fn(logits, labels)
      grads = self.create_grad_fn(loss)

    return {"loss": loss,
            "grads": grads}

  def create_graph_fn(self, input):
    is_training = (self.args.mode == "train")
    return self.net(input, self.args.num_classes,
                    is_training=is_training, data_format=self.args.data_format)

  def create_learning_rate_fn(self, global_step):
    """Create learning rate
    Returns:
      A learning rate calcualtor used by TF"s optimizer.
    """
    initial_learning_rate = self.args.learning_rate
    bs_per_gpu = self.args.batch_size_per_gpu
    num_gpu = self.args.num_gpu
    batches_per_epoch = (self.num_samples / (bs_per_gpu * num_gpu))
    boundaries = list(map(float,
                      self.args.piecewise_boundaries.split(",")))
    boundaries = [int(batches_per_epoch * boundary) for boundary in boundaries]

    decays = list(map(float,
                  self.args.piecewise_learning_rate_decay.split(",")))
    values = [initial_learning_rate * decay for decay in decays]

    learning_rate = tf.train.piecewise_constant(
      tf.cast(global_step, tf.int32), boundaries, values)

    tf.identity(learning_rate, name="learning_rate")
    tf.summary.scalar("learning_rate", learning_rate)

    return learning_rate

  def create_eval_metrics_fn(self, predictions, labels):
    pass

  def create_loss_fn(self, logits, labels):
    loss_cross_entropy = tf.losses.softmax_cross_entropy(
      logits=logits, onehot_labels=labels)

    l2_var_list = [v for v in tf.trainable_variables()
                   if not any(x in v.name for
                              x in ["BatchNorm", "preact", "postnorm"])]

    loss_l2 = self.args.l2_weight_decay * tf.add_n(
      [tf.nn.l2_loss(v) for v in l2_var_list])

    loss = tf.identity(loss_cross_entropy + loss_l2, "total_loss")

    return loss

  def create_grad_fn(self, loss):
    self.optimizer = self.create_optimizer(self.learning_rate)
    grads = self.optimizer.compute_gradients(loss)

    return grads


def build(args):
  return ImageClassificationModeler(args)
