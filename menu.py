# menu.py - Creates RelightKit toolbar menu in Nuke

import nuke
import os
import sys

toolbar = nuke.menu("Nodes")

plugin_dir = os.path.dirname(__file__)
icons_dir = os.path.join(plugin_dir, "icons").replace("\\", "/")

# Add plugin dir to Python path so rk_loader can be imported
if plugin_dir not in sys.path:
    sys.path.insert(0, plugin_dir)

# Register the icons folder on Nuke's plugin path so menu command icons
# resolve by bare filename (absolute paths are unreliable for addCommand).
nuke.pluginAddPath(icons_dir)


def _icon(name):
    """Return bare icon filename if it exists in icons_dir, else ''.

    Nuke resolves it via the plugin path registered above. Returning a bare
    filename (not an absolute path) is what makes addCommand icons show up.
    """
    p = os.path.join(icons_dir, name + ".png")
    return name + ".png" if os.path.exists(p) else ""


# Main menu with toolbar icon
rk_menu = toolbar.addMenu("RelightKit", icon=_icon("RelightKit"))

# --- Load ---
rk_menu.addCommand("Load PBR Passes", "import rk_loader; rk_loader.load_pbr_passes()", icon=_icon("RK_Load"))

rk_menu.addSeparator()

# --- Helpers ---
helpers_menu = rk_menu.addMenu("Helpers")
helpers_menu.addCommand("PBR Packer", "nuke.createNode('RK_PBRPacker')", icon=_icon("RK_PBRPacker"))
helpers_menu.addCommand("PBR Controller", "nuke.createNode('RK_PBRController')", icon=_icon("RK_PBRController"))

rk_menu.addSeparator()

# --- Lights ---
lights_menu = rk_menu.addMenu("Lights")
lights_menu.addCommand("Point Light", "nuke.createNode('RK_PointLight')", icon=_icon("RK_PointLight"))
lights_menu.addCommand("Point Light (Depth)", "nuke.createNode('RK_PointLightDepth')", icon=_icon("RK_PointLightDepth"))
lights_menu.addCommand("Directional Light", "nuke.createNode('RK_DirectionalLight')", icon=_icon("RK_DirectionalLight"))
lights_menu.addCommand("Area Light", "nuke.createNode('RK_AreaLight')", icon=_icon("RK_AreaLight"))
lights_menu.addCommand("Environment Light", "nuke.createNode('RK_EnvironmentLight')", icon=_icon("RK_EnvironmentLight"))


rk_menu.addSeparator()

# --- Merge ---
rk_menu.addCommand("Light Merge", "nuke.createNode('RK_LightMerge')", icon=_icon("RK_LightMerge"))
