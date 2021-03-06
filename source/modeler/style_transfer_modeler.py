"""
Copyright 2018 Lambda Labs. All Rights Reserved.
Licensed under
==========================================================================

"""
import importlib

import tensorflow as tf

from .modeler import Modeler
from source.augmenter.external import vgg_preprocessing


class StyleTransferModeler(Modeler):
  def __init__(self, config, net):
    super(StyleTransferModeler, self).__init__(config, net)

    self.feature_net = getattr(
      importlib.import_module("source.network." + self.config.feature_net),
      "net")
    self.style_layers = ('vgg_19/conv1/conv1_1', 'vgg_19/conv2/conv2_1',
                         'vgg_19/conv3/conv3_1', 'vgg_19/conv4/conv4_1',
                         'vgg_19/conv5/conv5_1')
    self.content_layers = 'vgg_19/conv4/conv4_2'

    if self.config.mode == "infer":
      self.feature_net_init_flag = False
    else:
      self.feature_net_init_flag = True

  def tensor_size(self, tensor):
    s = tf.shape(tensor)
    return tf.reduce_prod(s[1:])

  def compute_gram(self, feature, data_format):
    layer_shape = tf.shape(feature)
    bs = layer_shape[0]
    height = (layer_shape[1] if data_format == 'channels_last'
              else layer_shape[2])
    width = (layer_shape[2] if data_format == 'channels_last'
             else layer_shape[3])
    filters = (layer_shape[3] if data_format == 'channels_last'
               else layer_shape[1])
    size = height * width * filters
    feats = (tf.reshape(feature, (bs, height * width, filters))
             if data_format == 'channels_last'
             else tf.reshape(feature, (bs, filters, height * width)))
    feats_T = tf.transpose(feats, perm=[0, 2, 1])
    gram = (tf.matmul(feats_T, feats) / tf.cast(size, tf.float32)
            if data_format == 'channels_last'
            else tf.matmul(feats, feats_T) / tf.cast(size, tf.float32))
    return gram

  def compute_style_feature(self):
    style_image = tf.read_file(self.config.style_image_path)
    style_image = \
        tf.image.decode_jpeg(style_image,
                             channels=self.config.image_depth,
                             dct_method="INTEGER_ACCURATE")
    style_image = tf.to_float(style_image)
    style_image = vgg_preprocessing._mean_image_subtraction(style_image)
    style_image = tf.expand_dims(style_image, 0)

    (logits, features), self.feature_net_init_flag = self.feature_net(
      style_image, self.config.data_format,
      is_training=False, init_flag=self.feature_net_init_flag,
      ckpt_path=self.config.feature_net_path)

    self.style_features_target_op = {}
    for style_layer in self.style_layers:
      layer = features[style_layer]
      self.style_features_target_op[style_layer] = \
          self.compute_gram(layer, self.config.data_format)

    return self.style_features_target_op

  def get_dataset_info(self, inputter):
    self.num_samples = inputter.get_num_samples()

  def create_nonreplicated_fn(self):
    self.global_step = tf.train.get_or_create_global_step()
    if self.config.mode == "train":
      self.learning_rate = self.create_learning_rate_fn(self.global_step)

    if self.config.mode == "train" or self.config.mode == "eval":
      self.style_features_target = {}
      for layer in self.style_layers:
        self.style_features_target[layer] = tf.placeholder(
          tf.float32, name="style_feature_target_" + layer)
      self.style_features_target_op = self.compute_style_feature()
      self.feed_dict_pre = {self.style_features_target[key]:
                            self.style_features_target_op[key]
                            for key in self.style_features_target}

  def create_graph_fn(self, input):
    return self.net(input, data_format=self.config.data_format)

  def create_eval_metrics_fn(self, predictions, labels):
    pass

  def compute_tv_loss(self, outputs, data_format, tv_weight, batch_size):
    if data_format == 'channels_last':
      tv_y_size = tf.to_float(self.tensor_size(outputs[:, 1:, :, :]))
      tv_x_size = tf.to_float(self.tensor_size(outputs[:, :, 1:, :]))
      shape = tf.shape(outputs)
      y_tv = tf.nn.l2_loss(outputs[:, 1:, :, :] -
                           outputs[:, :shape[1] - 1, :, :])
      x_tv = tf.nn.l2_loss(outputs[:, :, 1:, :] -
                           outputs[:, :, :shape[2] - 1, :])
    else:
      tv_y_size = tf.to_float(self.tensor_size(outputs[:, :, 1:, :]))
      tv_x_size = tf.to_float(self.tensor_size(outputs[:, :, :, 1:]))
      shape = tf.shape(outputs)
      y_tv = tf.nn.l2_loss(outputs[:, :, 1:, :] -
                           outputs[:, :, :shape[2] - 1, :])
      x_tv = tf.nn.l2_loss(outputs[:, :, :, 1:] -
                           outputs[:, :, :, :shape[3] - 1])
    tv_loss = (tv_weight * 2 *
               (x_tv / tv_x_size + y_tv / tv_y_size) /
               batch_size)
    return tv_loss

  def create_loss_fn(self, outputs, inputs):
    """Create loss operator
    Returns:
      loss
    """
    self.gether_train_vars()

    (logits, vgg_net_target), self.feature_net_init_flag = self.feature_net(
      inputs, self.config.data_format, is_training=False,
      init_flag=self.feature_net_init_flag,
      ckpt_path=self.config.feature_net_path)
    content_features_target = {}
    content_features_target[self.content_layers] = (
      vgg_net_target[self.content_layers])

    outputs_mean_subtracted = vgg_preprocessing._mean_image_subtraction(
      outputs)

    (logits, vgg_net_source), self.feature_net_init_flag = self.feature_net(
      outputs_mean_subtracted,
      self.config.data_format,
      is_training=False,
      init_flag=self.feature_net_init_flag,
      ckpt_path=self.config.feature_net_path)

    content_features_source = {}
    content_features_source[self.content_layers] = (
      vgg_net_source[self.content_layers])

    style_features_source = {}
    for style_layer in self.style_layers:
      layer = vgg_net_source[style_layer]
      style_features_source[style_layer] = \
          self.compute_gram(layer, self.config.data_format)

    # Content loss
    content_size = tf.to_float(
      (self.tensor_size(content_features_source[self.content_layers]) *
       self.config.batch_size_per_gpu))

    loss_content = (self.config.content_weight *
                    (2 * tf.nn.l2_loss(
                        content_features_source[self.content_layers] -
                        content_features_target[self.content_layers]) /
                     content_size))

    # Style loss
    style_loss = []
    for style_layer in self.style_layers:
      style_size = tf.to_float(
        self.tensor_size(self.style_features_target[style_layer]))
      style_loss.append(2 * tf.nn.l2_loss(
                        style_features_source[style_layer] -
                        self.style_features_target[style_layer]) /
                        style_size)
    loss_style = (self.config.style_weight *
                  tf.reduce_sum(style_loss) /
                  self.config.batch_size_per_gpu)

    # TV loss
    loss_tv = self.compute_tv_loss(outputs,
                                   self.config.data_format,
                                   self.config.tv_weight,
                                   self.config.batch_size_per_gpu)

    # L2 loss
    loss_l2 = self.l2_regularization()

    loss = tf.identity(loss_l2 + loss_content +
                       loss_style + loss_tv, name="loss")
    return loss

  def model_fn(self, x, device_id=None):
    if self.config.mode == "export":
      images = x
    else:
      images = x[0]

    stylized_images = self.create_graph_fn(images)

    if self.config.mode == "train":

      loss = self.create_loss_fn(stylized_images, images)
      grads = self.create_grad_fn(loss)
      return {"loss": loss,
              "grads": grads,
              "learning_rate": self.learning_rate}
    elif self.config.mode == "eval":

      loss = self.create_loss_fn(stylized_images, images)
      return {"loss": loss}
    elif self.config.mode == "infer":
      return {"output": stylized_images,
              "input": images}
    elif self.config.mode == "export":
      output_image = tf.identity(stylized_images, name="output_image")
      return output_image

def build(config, net):
  return StyleTransferModeler(config, net)
