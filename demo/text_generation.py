"""
Copyright 2018 Lambda Labs. All Rights Reserved.
Licensed under
==========================================================================
Train:
python demo/text_generation.py --mode=train \
--num_gpu=1 --batch_size_per_gpu=128 --epochs=100 \
--piecewise_boundaries=50,75,90 --piecewise_learning_rate_decay=1.0,0.1,0.01,0.001 \
--dataset_url=https://s3-us-west-2.amazonaws.com/lambdalabs-files/shakespeare.tar.gz \
--dataset_meta=~/demo/data/shakespeare/shakespeare_input.txt \
--model_dir=~/demo/model/text_gen_shakespeare
"""
import os
import argparse

import app
from tool import downloader
from tool import tuner
from tool import args_parser


def main():
  parser = argparse.ArgumentParser(
    formatter_class=argparse.ArgumentDefaultsHelpFormatter)

  parser.add_argument("--inputter",
                      type=str,
                      help="Name of the inputter",
                      default="text_generation_txt_inputter")
  parser.add_argument("--modeler",
                      type=str,
                      help="Name of the modeler",
                      default="text_generation_modeler")
  parser.add_argument("--runner",
                      type=str,
                      help="Name of the runner",
                      default="parameter_server_runner")
  parser.add_argument("--augmenter",
                      type=str,
                      help="Name of the augmenter",
                      default="")
  parser.add_argument("--augmenter_speed_mode",
                      action='store_true',
                      help="Flag to use speed mode in augmentation")
  parser.add_argument("--network", choices=["fns"],
                      type=str,
                      help="Choose a network architecture",
                      default="char_rnn")
  parser.add_argument("--mode", choices=["train", "eval", "infer", "tune"],
                      type=str,
                      help="Choose a job mode from train, eval, and infer.",
                      default="train")
  parser.add_argument("--dataset_meta", type=str,
                      help="Path to dataset's csv meta file",
                      default=os.path.join(os.environ['HOME'],
                                           "demo/data/shakespeare/shakespeare_input.txt"))
  parser.add_argument("--batch_size_per_gpu",
                      help="Number of images on each GPU.",
                      type=int,
                      default=128)
  parser.add_argument("--num_gpu",
                      help="Number of GPUs.",
                      type=int,
                      default=4)
  parser.add_argument("--shuffle_buffer_size",
                      help="Buffer size for shuffling training images.",
                      type=int,
                      default=1000)
  parser.add_argument("--model_dir",
                      help="Directory to save mode",
                      type=str,
                      default=os.path.join(os.environ['HOME'],
                                           "demo/model/text_gen_shakespeare"))
  parser.add_argument("--l2_weight_decay",
                      help="Weight decay for L2 regularization in training",
                      type=float,
                      default=0.0002)
  parser.add_argument("--learning_rate",
                      help="Initial learning rate in training.",
                      type=float,
                      default=0.002)
  parser.add_argument("--epochs",
                      help="Number of epochs.",
                      type=int,
                      default=10)
  parser.add_argument("--piecewise_boundaries",
                      help="Epochs to decay learning rate",
                      default="5")
  parser.add_argument("--piecewise_learning_rate_decay",
                      help="Decay ratio for learning rate",
                      default="1.0,0.1")
  parser.add_argument("--optimizer",
                      help="Name of optimizer",
                      choices=["adadelta", "adagrad", "adam", "ftrl",
                               "momentum", "rmsprop", "sgd"],
                      default="adam")
  parser.add_argument("--log_every_n_iter",
                      help="Number of steps to log",
                      type=int,
                      default=2)
  parser.add_argument("--save_summary_steps",
                      help="Number of steps to save summary.",
                      type=int,
                      default=10)
  parser.add_argument("--save_checkpoints_steps",
                      help="Number of steps to save checkpoints",
                      type=int,
                      default=100)
  parser.add_argument("--keep_checkpoint_max",
                      help="Maximum number of checkpoints to save.",
                      type=int,
                      default=1)
  parser.add_argument("--test_samples",
                      help="A string of comma seperated testing data. "
                      "Must be provided for infer mode.",
                      type=str)
  parser.add_argument("--summary_names",
                      help="A string of comma seperated names for summary",
                      type=str,
                      default="loss,learning_rate")
  parser.add_argument("--dataset_url",
                      help="URL for downloading data",
                      default="https://s3-us-west-2.amazonaws.com/lambdalabs-files/shakespeare.tar.gz")
  parser.add_argument("--pretrained_dir",
                      help="Path to pretrained network (for transfer learning).",
                      type=str,
                      default="")  
  parser.add_argument("--skip_pretrained_var_list",
                      help="Variables to skip in restoring from pretrained model (for transfer learning).",
                      type=str,
                      default="")
  parser.add_argument("--trainable_var_list",
                      help="List of trainable Variables. \
                           If None all variables in tf.GraphKeys.TRAINABLE_VARIABLES \
                           will be trained, subjected to the ones blacklisted by skip_trainable_var_list.",
                      type=str,
                      default="")
  parser.add_argument("--skip_trainable_var_list",
                      help="List of blacklisted trainable Variables.",
                      type=str,
                      default="")
  parser.add_argument("--skip_l2_loss_vars",
                      help="List of blacklisted trainable Variables for L2 regularization.",
                      type=str,
                      default="")

  args = parser.parse_args()

  args = args_parser.prepare(args)

  # Download data if necessary
  if not os.path.exists(args.dataset_meta):
    downloader.download_and_extract(args.dataset_meta,
                                    args.dataset_url, False)
  else:
    print("Found " + args.dataset_meta + ".")

  if args.mode == "tune":
    tuner.tune(args)
  else:
    demo = app.APP(args)
    demo.run()


if __name__ == "__main__":
  main()