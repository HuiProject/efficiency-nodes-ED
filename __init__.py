"""
@author: NyaamZ
@title: Efficiency Nodes ExtendeD
@nickname: Efficiency Nodes ED
@description: Expansion of Efficiency Nodes for ComfyUI. Significant UX improvements.
"""

import os
import subprocess
import importlib.util
import folder_paths
import shutil
import sys
import traceback

from .ed_server import *

from  .efficiency_nodes_ED import NODE_CLASS_MAPPINGS

WEB_DIRECTORY = "js"

CC_VERSION = 2.0
# Keep the ComfyUI custom-node export contract explicit.  Older revisions
# listed this name in __all__ without defining it, which breaks star imports.
NODE_DISPLAY_NAME_MAPPINGS = {}

__all__ = ['NODE_CLASS_MAPPINGS', 'NODE_DISPLAY_NAME_MAPPINGS', 'CC_VERSION']
NOT_NODES = ['ed_server']
