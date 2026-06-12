# rk_loader.py — RelightKit PBR Pass Loader
"""
Scans a folder for UniVidX + DVD output passes and builds:
  Read nodes → RK_PBRPacker → RK_PBRController

Respects project OCIO config for colorspace assignment.
Uses nuke.root() OCIO roles to pick correct colorspaces.
"""

import nuke
import os
import re


# Pass type determines colorspace role:
#   "texture"  = sRGB-encoded texture (source plate, rgb preview)
#   "linear"   = linear working space (albedo, irradiance — need sRGB→linear decode)
#   "data"     = non-color data (normal, depth, alpha — no transform)
PASS_CONFIG = {
    "albedo":     {"input": 0, "role": "texture", "label": "Albedo"},
    "normal":     {"input": 1, "role": "data",    "label": "Normal"},
    "irradiance": {"input": 2, "role": "data",    "label": "Irradiance"},
    "alpha":      {"input": 3, "role": "data",    "label": "Alpha"},
    "depth":      {"input": 4, "role": "data",    "label": "Depth"},
    "source":     {"input": 5, "role": "texture", "label": "Source"},
    "rgb":        {"input": 5, "role": "texture", "label": "Source"},
}

REQUIRED_PASSES = ["albedo", "normal"]


def _get_colorspace_for_role(role):
    """
    Get the correct colorspace name from the project's OCIO config.
    
    Uses Nuke's root knobs to resolve OCIO roles:
      - "linear"  → project's compositing/working colorspace
      - "texture" → project's texture/matte paint colorspace  
      - "data"    → raw/data (no transform)
    """
    root = nuke.root()
    
    try:
        color_mgmt = root["colorManagement"].value()
    except Exception:
        color_mgmt = ""
    
    using_ocio = "OCIO" in color_mgmt.upper() if color_mgmt else False
    
    if not using_ocio:
        # Nuke native color management
        if role == "data":
            return "raw"
        elif role == "linear":
            return "linear"
        else:
            return "sRGB"
    
    # OCIO — use project role knobs
    if role == "data":
        # Data/raw — no color transform
        try:
            # Some OCIO configs have a "data" role
            return "raw"
        except Exception:
            return "raw"
    
    elif role == "linear":
        # Working/compositing space — read from project settings
        try:
            # Nuke 14+ exposes workingSpaceLUT
            ws = root["workingSpaceLUT"].value()
            if ws:
                return ws
        except Exception:
            pass
        try:
            # Fallback: monitorLut often points to the compositing space
            return root["monitorLut"].value()
        except Exception:
            pass
        return "compositing_linear"
    
    elif role == "texture":
        # sRGB texture — for viewing/source plates
        try:
            # Nuke 14+ int8Lut is typically the sRGB texture space
            lut = root["int8Lut"].value()
            if lut:
                return lut
        except Exception:
            pass
        return "color_picking"
    
    return "default"


def _find_sequence(folder, pass_name):
    """
    Look for an image sequence matching pass_name in folder.
    Returns (sequence_path, first_frame, last_frame, file_ext) or None.
    """
    search_dirs = [folder]
    subfolder = os.path.join(folder, pass_name)
    if os.path.isdir(subfolder):
        search_dirs.insert(0, subfolder)

    for search_dir in search_dirs:
        for ext in ["png", "exr", "jpg", "tiff"]:
            pattern = re.compile(
                r"^(" + re.escape(pass_name) + r".*?)(\d+)\." + re.escape(ext) + r"$",
                re.IGNORECASE,
            )

            files = []
            try:
                for f in os.listdir(search_dir):
                    m = pattern.match(f)
                    if m:
                        prefix = m.group(1)
                        frame_str = m.group(2)
                        files.append((f, prefix, int(frame_str), len(frame_str)))
            except OSError:
                continue

            if not files:
                continue

            prefix = files[0][1]
            files = [f for f in files if f[1] == prefix]
            if not files:
                continue

            files.sort(key=lambda x: x[2])
            first_frame = files[0][2]
            last_frame = files[-1][2]
            padding = files[0][3]

            seq_name = prefix + "%0{}d.{}".format(padding, ext)
            seq_path = os.path.join(search_dir, seq_name).replace("\\", "/")
            return seq_path, first_frame, last_frame, ext

    return None


def _create_read_node(seq_path, first_frame, last_frame, file_ext, pass_name, config, xpos, ypos):
    """Create a Read node with OCIO-aware colorspace."""
    read = nuke.createNode("Read", inpanel=False)
    read["file"].setValue(seq_path)
    read["first"].setValue(first_frame)
    read["last"].setValue(last_frame)
    read["origfirst"].setValue(first_frame)
    read["origlast"].setValue(last_frame)

    # Colorspace from project OCIO roles
    cs = _get_colorspace_for_role(config["role"])
    try:
        read["colorspace"].setValue(cs)
    except Exception:
        pass

    # Unique name
    base_name = "Read_{}".format(config["label"])
    name = base_name
    i = 1
    while nuke.exists(name):
        name = "{}_{}".format(base_name, i)
        i += 1
    read["name"].setValue(name)
    read["label"].setValue(config["label"])
    read.setXYpos(xpos, ypos)
    return read


def load_pbr_passes():
    """Opens folder picker, finds passes, builds the node graph."""
    selected = nuke.getFilename("Select PBR Pass Folder", "", "")
    if not selected:
        return

    selected = selected.replace("\\", "/")
    if os.path.isfile(selected):
        folder = os.path.dirname(selected)
    else:
        folder = selected

    if not os.path.isdir(folder):
        nuke.message("Error: '{}' is not a valid directory.".format(folder))
        return

    # Find sequences for each pass
    found = {}
    for pass_name, config in PASS_CONFIG.items():
        result = _find_sequence(folder, pass_name)
        if result:
            found[pass_name] = result

    if not found:
        nuke.message(
            "No passes found in:\n{}\n\n"
            "Expected files like:\n"
            "  albedo_00001.001.png\n"
            "  normal_00001.001.png\n"
            "  rgb_00001.001.png\n\n"
            "Or subfolders: albedo/, normal/, etc.".format(folder)
        )
        return

    missing = [p for p in REQUIRED_PASSES if p not in found]
    if missing:
        nuke.message(
            "Missing required passes: {}\n\n"
            "At minimum, albedo and normal are needed.".format(", ".join(missing))
        )
        return

    # Layout
    all_nodes = nuke.allNodes()
    if all_nodes:
        start_x = max(n.xpos() for n in all_nodes) + 300
    else:
        start_x = 0
    start_y = 0
    spacing_x = 150

    # Create Read nodes
    read_nodes = {}
    x = start_x
    for pass_name in ["source", "rgb", "albedo", "normal", "irradiance", "alpha", "depth"]:
        if pass_name not in found:
            continue
        if pass_name == "rgb" and "source" in read_nodes:
            continue
        if pass_name == "source" and "rgb" in read_nodes:
            continue

        seq_path, first, last, file_ext = found[pass_name]
        config = PASS_CONFIG[pass_name]
        read = _create_read_node(seq_path, first, last, file_ext, pass_name, config, x, start_y)
        read_nodes[pass_name] = read
        x += spacing_x

    # Backdrop
    if read_nodes:
        min_x = min(n.xpos() for n in read_nodes.values())
        max_x = max(n.xpos() + n.screenWidth() for n in read_nodes.values())
        nuke.nodes.BackdropNode(
            xpos=min_x - 20,
            ypos=start_y - 60,
            bdwidth=max_x - min_x + 40,
            bdheight=120,
            tile_color=0x4B7F52FF,
            label="RelightKit Passes\n{}".format(os.path.basename(folder)),
            note_font_size=14,
        )

    # PBRPacker
    packer_x = start_x + (len(read_nodes) * spacing_x) // 2 - 60
    packer_y = start_y + 150
    packer = nuke.createNode("RK_PBRPacker", inpanel=False)
    packer.setXYpos(packer_x, packer_y)

    for pass_name, read in read_nodes.items():
        input_idx = PASS_CONFIG[pass_name]["input"]
        packer.setInput(input_idx, read)

    # PBRController
    ctrl_y = packer_y + 100
    ctrl = nuke.createNode("RK_PBRController", inpanel=False)
    ctrl.setXYpos(packer_x, ctrl_y)
    ctrl.setInput(0, packer)

    pass_list = ", ".join(sorted(found.keys()))
    nuke.message(
        "RelightKit: Loaded {} passes\n\n"
        "Passes: {}\n"
        "Frames: {} - {}\n"
        "Folder: {}".format(
            len(found),
            pass_list,
            min(f[1] for f in found.values()),
            max(f[2] for f in found.values()),
            folder,
        )
    )
