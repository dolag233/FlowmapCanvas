import os
import sys
import numpy as np
from typing import Optional

try:
    import pygltflib  # type: ignore
    from pygltflib import GLTF2  # type: ignore
    _PYGLTFLIB_IMPORTED = True
    _PYGLTFLIB_ERROR = None
except Exception as e:  # pragma: no cover - diagnostic fallback
    GLTF2 = None  # type: ignore
    _PYGLTFLIB_IMPORTED = False
    _PYGLTFLIB_ERROR = e

from mesh_loader import MeshData

def _mat4_identity() -> np.ndarray:
    return np.identity(4, dtype=np.float32)

def _compose_trs(translation, rotation, scale) -> np.ndarray:
    T = _mat4_identity()
    if translation is not None:
        T[0,3] = float(translation[0])
        T[1,3] = float(translation[1])
        T[2,3] = float(translation[2])
    # rotation is quaternion [x,y,z,w]
    R = _mat4_identity()
    if rotation is not None:
        x,y,z,w = map(float, rotation)
        xx,yy,zz = x*x, y*y, z*z
        xy,xz,yz = x*y, x*z, y*z
        wx,wy,wz = w*x, w*y, w*z
        R[0,0] = 1.0 - 2.0*(yy+zz)
        R[0,1] = 2.0*(xy - wz)
        R[0,2] = 2.0*(xz + wy)
        R[1,0] = 2.0*(xy + wz)
        R[1,1] = 1.0 - 2.0*(xx+zz)
        R[1,2] = 2.0*(yz - wx)
        R[2,0] = 2.0*(xz - wy)
        R[2,1] = 2.0*(yz + wx)
        R[2,2] = 1.0 - 2.0*(xx+yy)
    S = _mat4_identity()
    if scale is not None:
        S[0,0] = float(scale[0])
        S[1,1] = float(scale[1])
        S[2,2] = float(scale[2])
    return T @ R @ S

def _node_world_matrix(gltf: 'GLTF2', node_index: int, cache: dict) -> np.ndarray:
    if node_index in cache:
        return cache[node_index]
    node = gltf.nodes[node_index]
    if getattr(node, 'matrix', None):
        M = np.array(node.matrix, dtype=np.float32).reshape(4,4)
    else:
        M = _compose_trs(getattr(node, 'translation', None), getattr(node, 'rotation', None), getattr(node, 'scale', None))
    # parent chain
    parent_M = _mat4_identity()
    for p_idx, p in enumerate(gltf.nodes):
        # pygltflib doesn't provide parent links; build by search
        if hasattr(p, 'children') and p.children:
            if node_index in p.children:
                parent_M = _node_world_matrix(gltf, p_idx, cache)
                break
    WM = parent_M @ M
    cache[node_index] = WM
    return WM


def _read_buffer(gltf: 'GLTF2', buffer_index: int, base_dir: str) -> bytes:
    buf = gltf.buffers[buffer_index]
    if buf.uri is None:
        # GLB binary chunk
        try:
            return gltf.binary_blob() or b""
        except Exception:
            # Older pygltflib versions
            return gltf._glb_data or b""  # type: ignore
    uri = buf.uri
    if uri.startswith("data:"):
        # embedded base64
        try:
            return gltf.get_data_from_buffer_uri(uri)
        except Exception:
            # Fallback name in older versions
            return pygltflib.utility.uri_to_bytes(uri)  # type: ignore
    # external file
    path = os.path.join(base_dir, uri)
    with open(path, "rb") as f:
        return f.read()


_DTYPE_BY_COMPONENT = {
    5120: np.int8,
    5121: np.uint8,
    5122: np.int16,
    5123: np.uint16,
    5125: np.uint32,
    5126: np.float32,
}

_NUM_COMPONENTS = {
    "SCALAR": 1,
    "VEC2": 2,
    "VEC3": 3,
    "VEC4": 4,
    "MAT2": 4,
    "MAT3": 9,
    "MAT4": 16,
}


def _read_accessor(gltf: 'GLTF2', accessor_index: int, base_dir: str) -> np.ndarray:
    accessor = gltf.accessors[accessor_index]
    if accessor.bufferView is None:
        raise RuntimeError(f"Accessor {accessor_index} has no bufferView")
    # pygltflib uses camelCase: bufferViews
    bv_list = getattr(gltf, 'bufferViews', None)
    if bv_list is None:
        raise RuntimeError("Loaded glTF has no bufferViews; check pygltflib version and file integrity")
    bv = bv_list[accessor.bufferView]
    buffer_bytes = _read_buffer(gltf, bv.buffer, base_dir)
    byte_offset = (bv.byteOffset or 0) + (accessor.byteOffset or 0)
    byte_stride = bv.byteStride or 0
    component_dtype = _DTYPE_BY_COMPONENT[accessor.componentType]
    num_comp = _NUM_COMPONENTS[accessor.type]
    count = accessor.count
    if byte_stride and byte_stride != num_comp * np.dtype(component_dtype).itemsize:
        # Interleaved
        arr = np.frombuffer(buffer_bytes, dtype=np.uint8, offset=byte_offset, count=count * byte_stride)
        arr = arr.reshape(count, byte_stride)
        comp_view = np.empty((count, num_comp), dtype=component_dtype)
        elem_size = np.dtype(component_dtype).itemsize
        for i in range(num_comp):
            comp_view[:, i] = np.frombuffer(arr[:, i * elem_size:(i + 1) * elem_size].tobytes(), dtype=component_dtype)
        return comp_view
    # Tightly packed
    total_elems = count * num_comp
    arr = np.frombuffer(buffer_bytes, dtype=component_dtype, offset=byte_offset, count=total_elems)
    return arr.reshape(count, num_comp)


def load_gltf(path: str) -> Optional[MeshData]:
    if GLTF2 is None:
        # Provide detailed context to help users whose site-packages are not on current interpreter
        detail = f"(sys.executable={sys.executable}, sys.path[0]={sys.path[0] if sys.path else ''}, err={_PYGLTFLIB_ERROR})"
        raise RuntimeError("pygltflib is required but not importable. Ensure it's installed for the running Python interpreter. " + detail)
    base_dir = os.path.dirname(os.path.abspath(path))
    gltf = GLTF2().load(path)
    if not gltf.meshes:
        return None
    # Take the first mesh / first primitive
    # Traverse default scene, merge all primitives with node transforms
    scene_index = getattr(gltf, 'scene', 0) or 0
    scene = gltf.scenes[scene_index]
    node_indices = scene.nodes or []
    world_cache: dict = {}
    all_pos: list = []
    all_nrm: list = []
    all_uv: list = []  # primary UV set for backward compatibility
    all_uv_sets: dict = {}  # UV set index -> list of UV arrays
    all_indices: list = []
    vert_offset = 0

    def visit(node_idx: int):
        nonlocal vert_offset
        M = _node_world_matrix(gltf, node_idx, world_cache)
        N = np.linalg.inv(M[:3,:3]).T  # normal matrix
        node = gltf.nodes[node_idx]
        if getattr(node, 'mesh', None) is not None:
            m = gltf.meshes[node.mesh]
            for prim in (m.primitives or []):
                if prim.indices is None:
                    continue
                idx = _read_accessor(gltf, prim.indices, base_dir).astype(np.uint32, copy=False).reshape(-1)
                attrs = prim.attributes
                pos_acc = getattr(attrs, 'POSITION', None)
                nrm_acc = getattr(attrs, 'NORMAL', None)
                if pos_acc is None:
                    continue
                P = _read_accessor(gltf, pos_acc, base_dir).astype(np.float32, copy=False)
                if P.shape[1] != 3:
                    P = P.reshape(-1, 3)
                # Apply node/world transform
                P_h = np.concatenate([P, np.ones((P.shape[0],1), dtype=np.float32)], axis=1)
                P_w = (P_h @ M.T)[:, :3]
                all_pos.append(P_w)

                if nrm_acc is not None:
                    NR = _read_accessor(gltf, nrm_acc, base_dir).astype(np.float32, copy=False)
                    if NR.shape[1] != 3:
                        NR = NR.reshape(-1, 3)
                    NR = (NR @ N.T)
                    # normalize
                    lens = np.linalg.norm(NR, axis=1) + 1e-8
                    NR = (NR.T / lens).T
                else:
                    NR = np.zeros_like(P)
                all_nrm.append(NR)

                # Collect all UV sets (TEXCOORD_0, TEXCOORD_1, etc.)
                primary_uv = None
                for attr_name in dir(attrs):
                    if attr_name.startswith('TEXCOORD_'):
                        try:
                            uv_index = int(attr_name.split('_')[1])
                            uv_acc = getattr(attrs, attr_name, None)
                            if uv_acc is not None:
                                UV = _read_accessor(gltf, uv_acc, base_dir).astype(np.float32, copy=False)
                                if UV.shape[1] != 2:
                                    UV = UV.reshape(-1, 2)
                                # Flip V to match our OBJ/OpenGL pipeline (v origin at bottom)
                                if not UV.flags.writeable:
                                    UV = UV.copy()
                                UV[:,1] = 1.0 - UV[:,1]
                                
                                # Store in UV sets dictionary
                                if uv_index not in all_uv_sets:
                                    all_uv_sets[uv_index] = []
                                all_uv_sets[uv_index].append(UV)
                                
                                # Use TEXCOORD_0 as primary UV for backward compatibility
                                if uv_index == 0:
                                    primary_uv = UV
                        except (ValueError, AttributeError):
                            continue
                
                # If no UV sets found, create zero UV
                if primary_uv is None:
                    primary_uv = np.zeros((P.shape[0], 2), dtype=np.float32)
                all_uv.append(primary_uv)

                all_indices.append(idx.astype(np.uint32, copy=False) + np.uint32(vert_offset))
                vert_offset += P.shape[0]
        # visit children
        for c in (node.children or []):
            visit(c)

    for n in node_indices:
        visit(n)

    if not all_pos or not all_indices:
        return None
    positions = np.vstack(all_pos)
    normals = np.vstack(all_nrm)
    uvs = np.vstack(all_uv)  # primary UV set
    indices = np.concatenate(all_indices).astype(np.uint32, copy=False)
    
    # Build UV sets list
    uv_sets = []
    uv_set_names = []
    if all_uv_sets:
        # Sort UV sets by index
        sorted_uv_indices = sorted(all_uv_sets.keys())
        for uv_idx in sorted_uv_indices:
            if all_uv_sets[uv_idx]:
                combined_uv = np.vstack(all_uv_sets[uv_idx])
                uv_sets.append(combined_uv)
                uv_set_names.append(f"UV{uv_idx}")
    
    # Fallback: if no UV sets collected, use primary UV
    if not uv_sets and uvs.size > 0:
        uv_sets = [uvs]
        uv_set_names = ["UV0"]
    
    return MeshData(
        positions=positions,
        uvs=uvs,
        normals=normals,
        indices=indices,
        uv_sets=uv_sets,
        uv_set_names=uv_set_names
    )


