import numpy as np
from dataclasses import dataclass


@dataclass
class MeshData:
    positions: np.ndarray  # (N,3) float32
    uvs: np.ndarray        # (N,2) float32 - primary UV set (for backward compatibility)
    normals: np.ndarray    # (N,3) float32
    indices: np.ndarray    # (M,)  uint32 (triangles)
    uv_sets: list[np.ndarray] = None  # List of UV sets [(N,2) float32, ...]
    uv_set_names: list[str] = None    # Names for UV sets ["UV0", "UV1", ...]


def load_obj(path: str) -> MeshData:
    positions = []
    texcoords = []
    normals = []
    faces = []  # list[list[tuple(pi,ti,ni)]]

    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith('#'):
                continue
            if line.startswith('v '):
                parts = line.split()
                positions.append([float(parts[1]), float(parts[2]), float(parts[3])])
            elif line.startswith('vt '):
                parts = line.split()
                if len(parts) >= 3:
                    texcoords.append([float(parts[1]), float(parts[2])])
            elif line.startswith('vn '):
                parts = line.split()
                normals.append([float(parts[1]), float(parts[2]), float(parts[3])])
            elif line.startswith('f '):
                items = line.split()[1:]
                face = []
                for v in items:
                    comps = v.split('/')
                    pi = int(comps[0]) - 1 if comps[0] else -1
                    ti = int(comps[1]) - 1 if len(comps) > 1 and comps[1] else -1
                    ni = int(comps[2]) - 1 if len(comps) > 2 and comps[2] else -1
                    face.append((pi, ti, ni))
                if len(face) >= 3:
                    faces.append(face)

    pos = np.array(positions, dtype=np.float32) if positions else np.zeros((0,3), dtype=np.float32)
    uvs = np.array(texcoords, dtype=np.float32) if texcoords else np.zeros((0,2), dtype=np.float32)
    nors = np.array(normals, dtype=np.float32) if normals else np.zeros((0,3), dtype=np.float32)

    vert_map = {}
    out_pos = []
    out_uv = []
    out_nor = []
    indices = []

    def get_index(pi, ti, ni):
        key = (pi, ti, ni)
        if key in vert_map:
            return vert_map[key]
        vi = len(out_pos)
        p = pos[pi] if 0 <= pi < len(pos) else np.array([0.0,0.0,0.0], dtype=np.float32)
        t = uvs[ti] if 0 <= ti < len(uvs) else np.array([0.0,0.0], dtype=np.float32)
        n = nors[ni] if 0 <= ni < len(nors) else np.array([0.0,0.0,1.0], dtype=np.float32)
        out_pos.append(p)
        out_uv.append(t)
        out_nor.append(n)
        vert_map[key] = vi
        return vi

    for face in faces:
        for i in range(1, len(face) - 1):
            i0 = get_index(*face[0])
            i1 = get_index(*face[i])
            i2 = get_index(*face[i+1])
            indices.extend([i0, i1, i2])

    final_uvs = np.array(out_uv, dtype=np.float32)
    return MeshData(
        positions=np.array(out_pos, dtype=np.float32),
        uvs=final_uvs,  # primary UV set for backward compatibility
        normals=np.array(out_nor, dtype=np.float32),
        indices=np.array(indices, dtype=np.uint32),
        uv_sets=[final_uvs] if final_uvs.size > 0 else [],
        uv_set_names=["UV0"] if final_uvs.size > 0 else [],
    )


