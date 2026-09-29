from __future__ import annotations

import json
import struct
from pathlib import Path


def read_glb_json(path: Path) -> dict:
    data = path.read_bytes()
    magic, version, _ = struct.unpack_from("<4sII", data, 0)
    assert magic == b"glTF" and version == 2
    offset = 12
    while offset < len(data):
        length, chunk_type = struct.unpack_from("<I4s", data, offset)
        chunk = data[offset + 8: offset + 8 + length]
        offset += 8 + length
        if chunk_type == b"JSON":
            return json.loads(chunk.rstrip(b" \x00").decode("utf-8"))
    raise AssertionError("GLB JSON chunk missing")


def test_catalyst_vrm_model_is_present_and_valid_shape():
    path = Path("frontend/assets/catalyst/catalyst.vrm")
    assert path.is_file()
    assert path.stat().st_size > 100_000
    gltf = read_glb_json(path)
    assert "VRMC_vrm" in gltf.get("extensionsUsed", [])
    ext = gltf["extensions"]["VRMC_vrm"]
    assert ext["specVersion"] == "1.0"
    assert ext["meta"]["name"] == "Catalyst"
    required = {
        "hips", "spine", "head", "leftUpperLeg", "leftLowerLeg", "leftFoot",
        "rightUpperLeg", "rightLowerLeg", "rightFoot", "leftUpperArm",
        "leftLowerArm", "leftHand", "rightUpperArm", "rightLowerArm", "rightHand",
    }
    assert required.issubset(ext["humanoid"]["humanBones"])
    assert "VRMC_springBone" in gltf.get("extensionsUsed", [])
    assert len(gltf.get("skins", [])) >= 1
    assert all("skin" in n for n in gltf.get("nodes", []) if "mesh" in n)
    expressions = ext.get("expressions", {})
    preset = expressions.get("preset", {})
    custom = expressions.get("custom", {})
    assert all(name in preset for name in ("blink", "blinkLeft", "blinkRight", "aa", "ih", "oh"))
    assert {"neutral", "focused", "thinking"}.issubset(custom)
    names = {n.get("name") for n in gltf.get("nodes", [])}
    for name in ("Head", "LeftEyeWhite", "RightEyeWhite", "Mouth", "Outfit_Signature_Top", "Outfit_Focus_Blazer"):
        assert name in names


def test_catalyst_vrm_has_weighted_skin_and_expressions():
    path = Path("frontend/assets/catalyst/catalyst.vrm")
    gltf = read_glb_json(path)
    assert len(gltf.get("skins", [])) == 1
    mesh_nodes = [n for n in gltf.get("nodes", []) if "mesh" in n]
    assert len(mesh_nodes) == 78
    assert all("skin" in n for n in mesh_nodes)
    for mesh in gltf.get("meshes", []):
        for primitive in mesh.get("primitives", []):
            attrs = primitive.get("attributes", {})
            assert {"POSITION", "NORMAL", "JOINTS_0", "WEIGHTS_0"}.issubset(attrs)
    ext = gltf["extensions"]["VRMC_vrm"]
    preset = ext["expressions"]["preset"]
    custom = ext["expressions"]["custom"]
    assert {"blink", "blinkLeft", "blinkRight", "aa", "ih", "oh"}.issubset(preset)
    assert {"neutral", "focused", "thinking", "warm"}.issubset(custom)
