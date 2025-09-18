"""
Tangent Space Computation Module

This module implements Mikk tangent space generation for seamless 3D painting.
The tangent space is computed based on the first UV set to ensure consistency
across UV seams, enabling proper flow direction encoding in tangent space.

Key Features:
- Mikk tangent space algorithm implementation
- High-performance CPU-based computation
- Consistent tangent space across UV seams
- Support for world-to-tangent space direction conversion
"""

import numpy as np
from typing import Tuple, Optional


class TangentSpaceGenerator:
    """
    High-performance Mikk tangent space generator for seamless 3D painting.
    
    This class computes tangent and bitangent vectors using the Mikk tangent space
    algorithm, ensuring consistent tangent frames across UV seams for proper
    flow direction encoding.
    """
    
    def __init__(self):
        self.positions = None
        self.normals = None
        self.uvs = None
        self.indices = None
        self.tangents = None
        self.bitangents = None
        self._computed = False
    
    def compute_tangent_space(self, positions: np.ndarray, normals: np.ndarray, 
                            uvs: np.ndarray, indices: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Compute tangent and bitangent vectors using Mikk tangent space algorithm.
        
        Args:
            positions: Vertex positions (N, 3)
            normals: Vertex normals (N, 3)
            uvs: UV coordinates from first UV set (N, 2)
            indices: Triangle indices (M, 3) or (M*3,)
            
        Returns:
            Tuple of (tangents, bitangents) as (N, 3) arrays
        """
        if positions.size == 0 or normals.size == 0 or indices.size == 0:
            return np.zeros((0, 3), dtype=np.float32), np.zeros((0, 3), dtype=np.float32)
        
        # Store data
        self.positions = positions.astype(np.float32, copy=False)
        self.normals = normals.astype(np.float32, copy=False)
        self.uvs = uvs.astype(np.float32, copy=False) if uvs.size > 0 else np.zeros((positions.shape[0], 2), dtype=np.float32)
        
        # Ensure indices are properly shaped
        if indices.ndim == 1:
            self.indices = indices.reshape(-1, 3)
        else:
            self.indices = indices
        
        vertex_count = int(self.positions.shape[0])
        
        # Initialize accumulation arrays for tangent vectors
        tan1 = np.zeros((vertex_count, 3), dtype=np.float32)
        tan2 = np.zeros((vertex_count, 3), dtype=np.float32)
        
        # Process each triangle to accumulate tangent contributions
        self._accumulate_triangle_tangents(tan1, tan2)
        
        # Orthonormalize and compute final tangents/bitangents
        tangents, bitangents = self._orthonormalize_tangents(tan1, tan2)
        
        self.tangents = tangents
        self.bitangents = bitangents
        self._computed = True
        
        return tangents, bitangents
    
    def _accumulate_triangle_tangents(self, tan1: np.ndarray, tan2: np.ndarray):
        """
        Accumulate tangent contributions from all triangles.
        High-performance vectorized implementation.
        """
        # Get triangle vertex indices
        i0 = self.indices[:, 0].astype(np.int32)
        i1 = self.indices[:, 1].astype(np.int32)
        i2 = self.indices[:, 2].astype(np.int32)
        
        # Get triangle vertices
        p0 = self.positions[i0]  # (T, 3)
        p1 = self.positions[i1]  # (T, 3)
        p2 = self.positions[i2]  # (T, 3)
        
        # Get triangle UVs
        uv0 = self.uvs[i0]  # (T, 2)
        uv1 = self.uvs[i1]  # (T, 2)
        uv2 = self.uvs[i2]  # (T, 2)
        
        # Compute edge vectors
        e1 = p1 - p0  # (T, 3)
        e2 = p2 - p0  # (T, 3)
        
        # Compute UV deltas
        duv1 = uv1 - uv0  # (T, 2)
        duv2 = uv2 - uv0  # (T, 2)
        
        # Compute determinant for each triangle
        det = duv1[:, 0] * duv2[:, 1] - duv2[:, 0] * duv1[:, 1]  # (T,)
        
        # Filter out degenerate triangles
        valid_mask = np.abs(det) > 1e-8
        if not np.any(valid_mask):
            return
        
        # Apply mask to filter valid triangles
        det_valid = det[valid_mask]
        e1_valid = e1[valid_mask]
        e2_valid = e2[valid_mask]
        duv1_valid = duv1[valid_mask]
        duv2_valid = duv2[valid_mask]
        i0_valid = i0[valid_mask]
        i1_valid = i1[valid_mask]
        i2_valid = i2[valid_mask]
        
        # Compute reciprocal determinant
        r = 1.0 / det_valid  # (V,)
        
        # Compute tangent directions for valid triangles
        sdir = (e1_valid * duv2_valid[:, 1:2] - e2_valid * duv1_valid[:, 1:2]) * r[:, np.newaxis]  # (V, 3)
        tdir = (e2_valid * duv1_valid[:, 0:1] - e1_valid * duv2_valid[:, 0:1]) * r[:, np.newaxis]  # (V, 3)
        
        # Accumulate tangent contributions for each vertex
        # Using numpy's advanced indexing with add.at for accumulation
        np.add.at(tan1, i0_valid, sdir)
        np.add.at(tan1, i1_valid, sdir)
        np.add.at(tan1, i2_valid, sdir)
        
        np.add.at(tan2, i0_valid, tdir)
        np.add.at(tan2, i1_valid, tdir)
        np.add.at(tan2, i2_valid, tdir)
    
    def _orthonormalize_tangents(self, tan1: np.ndarray, tan2: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Orthonormalize tangents using Gram-Schmidt and compute bitangents.
        Vectorized implementation for high performance.
        """
        vertex_count = self.normals.shape[0]
        tangents = np.zeros((vertex_count, 3), dtype=np.float32)
        bitangents = np.zeros((vertex_count, 3), dtype=np.float32)
        
        # Vectorized Gram-Schmidt orthonormalization
        # tangent = normalize(tan1 - normal * dot(normal, tan1))
        dot_products = np.sum(self.normals * tan1, axis=1, keepdims=True)  # (N, 1)
        t_ortho = tan1 - self.normals * dot_products  # (N, 3)
        
        # Compute tangent lengths
        t_lengths = np.linalg.norm(t_ortho, axis=1)  # (N,)
        
        # Normalize tangents (avoid division by zero)
        valid_length_mask = t_lengths > 1e-8
        tangents[valid_length_mask] = t_ortho[valid_length_mask] / t_lengths[valid_length_mask, np.newaxis]
        
        # Fallback tangent for degenerate cases
        invalid_mask = ~valid_length_mask
        if np.any(invalid_mask):
            # Create fallback tangents perpendicular to normal
            fallback_tangents = self._create_fallback_tangents(self.normals[invalid_mask])
            tangents[invalid_mask] = fallback_tangents
        
        # Compute bitangents: cross(normal, tangent)
        bitangents_raw = np.cross(self.normals, tangents)  # (N, 3)
        
        # Check handedness and flip if necessary
        # Mikk algorithm: if dot(cross(normal, tangent), tan2) < 0, flip bitangent
        handedness = np.sum(bitangents_raw * tan2, axis=1)  # (N,)
        flip_mask = handedness < 0.0
        
        bitangents = bitangents_raw.copy()
        bitangents[flip_mask] = -bitangents_raw[flip_mask]
        
        return tangents, bitangents
    
    def _create_fallback_tangents(self, normals: np.ndarray) -> np.ndarray:
        """
        Create fallback tangents for degenerate cases.
        Uses the most orthogonal world axis to the normal.
        """
        # Try X, Y, Z axes and pick the most orthogonal one
        axes = np.array([[1, 0, 0], [0, 1, 0], [0, 0, 1]], dtype=np.float32)
        
        fallback_tangents = np.zeros_like(normals)
        
        for i, normal in enumerate(normals):
            # Find the axis most orthogonal to the normal
            dots = np.abs(np.dot(axes, normal))
            best_axis_idx = np.argmin(dots)
            best_axis = axes[best_axis_idx]
            
            # Create tangent orthogonal to normal
            tangent = best_axis - normal * np.dot(normal, best_axis)
            tangent_length = np.linalg.norm(tangent)
            
            if tangent_length > 1e-8:
                fallback_tangents[i] = tangent / tangent_length
            else:
                # Extreme fallback
                fallback_tangents[i] = np.array([1, 0, 0], dtype=np.float32)
        
        return fallback_tangents
    
    def world_to_tangent_direction(self, world_direction: np.ndarray, 
                                 vertex_indices: np.ndarray, 
                                 barycentric: np.ndarray) -> np.ndarray:
        """
        Convert world space direction to tangent space direction at a specific surface point.
        Enhanced version with seam-aware interpolation for better continuity.
        
        Args:
            world_direction: Direction in world space (3,)
            vertex_indices: Triangle vertex indices (3,)
            barycentric: Barycentric coordinates (3,) [u, v, w] where w = 1-u-v
            
        Returns:
            Direction in tangent space (2,) - only XY components for flow encoding
        """
        if not self._computed:
            raise RuntimeError("Tangent space not computed. Call compute_tangent_space first.")
        
        # Get vertex indices
        i0, i1, i2 = vertex_indices.astype(np.int32)
        u, v, w = barycentric.astype(np.float32)
        
        # Interpolate tangent space basis vectors at the hit point
        tangent = (self.tangents[i0] * w + 
                  self.tangents[i1] * u + 
                  self.tangents[i2] * v)
        
        bitangent = (self.bitangents[i0] * w + 
                    self.bitangents[i1] * u + 
                    self.bitangents[i2] * v)
        
        normal = (self.normals[i0] * w + 
                 self.normals[i1] * u + 
                 self.normals[i2] * v)
        
        # Enhanced normalization with better numerical stability
        tangent_len = np.linalg.norm(tangent)
        bitangent_len = np.linalg.norm(bitangent)
        normal_len = np.linalg.norm(normal)
        
        if tangent_len > 1e-6:
            tangent = tangent / tangent_len
        else:
            # Fallback: create tangent perpendicular to normal
            tangent = self._create_perpendicular_vector(normal)
        
        if bitangent_len > 1e-6:
            bitangent = bitangent / bitangent_len
        else:
            # Fallback: create bitangent as cross(normal, tangent)
            bitangent = np.cross(normal, tangent)
            bitangent = bitangent / (np.linalg.norm(bitangent) + 1e-8)
        
        if normal_len > 1e-6:
            normal = normal / normal_len
        else:
            # This should rarely happen, but fallback to up vector
            normal = np.array([0, 1, 0], dtype=np.float32)
        
        # Re-orthogonalize the basis to ensure it's properly orthonormal
        # This helps reduce artifacts at seams
        tangent = tangent - normal * np.dot(tangent, normal)
        tangent = tangent / (np.linalg.norm(tangent) + 1e-8)
        
        bitangent = np.cross(normal, tangent)
        bitangent = bitangent / (np.linalg.norm(bitangent) + 1e-8)
        
        # Construct world-to-tangent transformation matrix
        # TBN matrix transforms from tangent to world, so world-to-tangent is TBN^T
        world_to_tangent = np.array([
            [tangent[0], tangent[1], tangent[2]],
            [bitangent[0], bitangent[1], bitangent[2]],
            [normal[0], normal[1], normal[2]]
        ], dtype=np.float32)
        
        # Transform world direction to tangent space
        world_dir_len = np.linalg.norm(world_direction)
        if world_dir_len > 1e-8:
            world_dir_normalized = world_direction / world_dir_len
            tangent_space_dir = world_to_tangent @ world_dir_normalized
        else:
            # Zero direction fallback
            tangent_space_dir = np.array([0, 0, 0], dtype=np.float32)
        
        # Return only XY components for flow encoding (Z is normal direction)
        return tangent_space_dir[:2].astype(np.float32)
    
    def _create_perpendicular_vector(self, normal: np.ndarray) -> np.ndarray:
        """Create a vector perpendicular to the given normal."""
        normal = normal / (np.linalg.norm(normal) + 1e-8)
        
        # Find the axis most perpendicular to normal
        abs_normal = np.abs(normal)
        if abs_normal[0] <= abs_normal[1] and abs_normal[0] <= abs_normal[2]:
            axis = np.array([1, 0, 0], dtype=np.float32)
        elif abs_normal[1] <= abs_normal[2]:
            axis = np.array([0, 1, 0], dtype=np.float32)
        else:
            axis = np.array([0, 0, 1], dtype=np.float32)
        
        # Create perpendicular vector
        perp = axis - normal * np.dot(axis, normal)
        return perp / (np.linalg.norm(perp) + 1e-8)
    
    def get_tangent_basis_at_point(self, vertex_indices: np.ndarray, 
                                  barycentric: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Get interpolated tangent space basis (T, B, N) at a specific surface point.
        
        Args:
            vertex_indices: Triangle vertex indices (3,)
            barycentric: Barycentric coordinates (3,) [u, v, w]
            
        Returns:
            Tuple of (tangent, bitangent, normal) vectors (3,) each
        """
        if not self._computed:
            raise RuntimeError("Tangent space not computed. Call compute_tangent_space first.")
        
        # Get vertex indices
        i0, i1, i2 = vertex_indices.astype(np.int32)
        u, v, w = barycentric.astype(np.float32)
        
        # Interpolate basis vectors
        tangent = (self.tangents[i0] * w + 
                  self.tangents[i1] * u + 
                  self.tangents[i2] * v)
        
        bitangent = (self.bitangents[i0] * w + 
                    self.bitangents[i1] * u + 
                    self.bitangents[i2] * v)
        
        normal = (self.normals[i0] * w + 
                 self.normals[i1] * u + 
                 self.normals[i2] * v)
        
        # Normalize
        tangent = tangent / (np.linalg.norm(tangent) + 1e-8)
        bitangent = bitangent / (np.linalg.norm(bitangent) + 1e-8)
        normal = normal / (np.linalg.norm(normal) + 1e-8)
        
        return tangent, bitangent, normal
