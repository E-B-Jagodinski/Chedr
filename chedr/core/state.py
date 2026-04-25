from core.chedr import Chedr
import os

CONFIG_PATH = "chedr/config/config.json"

fin = Chedr(CONFIG_PATH)
fin.setup()