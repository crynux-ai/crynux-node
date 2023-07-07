import yaml
import sys

with open("data/config.yml", 'r') as file:
    config = yaml.safe_load(file)

if config is None:
    sys.exit("error loading config file")
