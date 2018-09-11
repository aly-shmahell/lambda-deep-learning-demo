"""
Copyright 2018 Lambda Labs. All Rights Reserved.
Licensed under
==========================================================================

"""
import argparse

import app


def main():
  parser = argparse.ArgumentParser(
    formatter_class=argparse.ArgumentDefaultsHelpFormatter)

  parser.add_argument("--inputter",
                      type=str,
                      help="Name of the inputter",
                      default="inputter")

  parser.add_argument("--modeler",
                      type=str,
                      help="Name of the modeler",
                      default="modeler")

  parser.add_argument("--runner",
                      type=str,
                      help="Name of the runner",
                      default="runner")

  args = parser.parse_args()

  demo = app.APP(args)

  demo.run()


if __name__ == "__main__":
  main()
