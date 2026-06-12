# init.py - Runs on Nuke startup before menu.py
# Adds gizmos and icons to Nuke's plugin path

import nuke
import os

plugin_dir = os.path.dirname(__file__)

gizmos_dir = os.path.join(plugin_dir, "gizmos")
nuke.pluginAddPath(gizmos_dir)

icons_dir = os.path.join(plugin_dir, "icons")
nuke.pluginAddPath(icons_dir)
