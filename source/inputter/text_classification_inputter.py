"""
Copyright 2018 Lambda Labs. All Rights Reserved.
Licensed under
==========================================================================

"""
from __future__ import print_function
import os
import csv

import tensorflow as tf

from .inputter import Inputter
from source.network.encoder import sentence

def loadSentences(dataset_meta):
  # Read sentences and labels from csv files
  sentences = []
  labels = []
  for meta in dataset_meta:
    dirname = os.path.dirname(meta)
    with open(meta) as f:
      parsed = csv.reader(f, delimiter="\t")
      for row in parsed:
        sentences.append(row[0].split(" "))
        labels.append([int(row[1])])
  return sentences, labels 


class TextClassificationInputter(Inputter):
  def __init__(self, config, augmenter):
    super(TextClassificationInputter, self).__init__(config, augmenter)

    self.max_length = 128

    # Load data
    if self.config.mode == "train" or self.config.mode == "eval":
      for meta in self.config.dataset_meta:
        assert os.path.exists(meta), ("Cannot find dataset_meta file {}.".format(meta))
      self.sentences, self.labels = loadSentences(self.config.dataset_meta)
    elif self.config.mode == "infer":
      pass

    # Load vacabulary
    f = open(self.config.vocab_file, "r")
    words = f.read().splitlines()
    self.vocab = { w : i for i, w in enumerate(words)}
    f.close()

    # encode data
    self.encode_sentences, self.encode_masks = sentence.basic(self.sentences, self.vocab, self.max_length)

    self.num_samples = len(self.encode_sentences)

  def create_nonreplicated_fn(self):
    batch_size = (self.config.batch_size_per_gpu *
                  self.config.gpu_count)
    max_step = (self.get_num_samples() * self.config.epochs // batch_size)
    tf.constant(max_step, name="max_step")

  def get_num_samples(self):
    return self.num_samples

  def get_vocab_size(self):
    return len(self.vocab)

  def get_samples_fn(self):
    for encode_sentence, label, mask in zip(self.encode_sentences, self.labels, self.encode_masks):
      yield encode_sentence, label, mask

  def input_fn(self, test_samples=[]):
    batch_size = (self.config.batch_size_per_gpu *
                  self.config.gpu_count) 
    if self.config.mode == "export":
      pass
    else:
      if self.config.mode == "train" or self.config.mode == "eval" or self.config.mode == 'infer':

        dataset = tf.data.Dataset.from_generator(
          generator=lambda: self.get_samples_fn(),
          output_types=(tf.int32, tf.int32, tf.int32))

        if self.config.mode == "train":
          dataset = dataset.shuffle(self.get_num_samples())

        dataset = dataset.repeat(self.config.epochs)

        dataset = dataset.apply(
            tf.contrib.data.batch_and_drop_remainder(batch_size))

        dataset = dataset.prefetch(2)

        iterator = dataset.make_one_shot_iterator()
        return iterator.get_next()


def build(config, augmenter):
  return TextClassificationInputter(config, augmenter)
