"""
Copyright 2018 Lambda Labs. All Rights Reserved.
Licensed under
==========================================================================

"""
from __future__ import print_function
import abc
import six

@six.add_metaclass(abc.ABCMeta)
class Modeler(object):
  def __init__(self, args):
    self.args = args

  @abc.abstractmethod
  def create_precomputation(self):
    raise NotImplementedError()


def build(args):
  return Modeler(args)
