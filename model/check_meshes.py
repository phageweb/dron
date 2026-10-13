#!/usr/bin/env python3
"""Check ASCII STL exports and calculate volume/centroid; Python standard library."""
from collections import Counter, defaultdict
from pathlib import Path
import json


def inspect(path):
    vertices = [tuple(map(float, line.split()[1:]))
                for line in path.read_text().splitlines()
                if line.strip().startswith('vertex ')]
    assert vertices and len(vertices) % 3 == 0, f'{path}: invalid STL'
    edges = Counter()
    directed = Counter()
    adjacency = defaultdict(set)
    volume = 0.0
    first_moment = [0.0, 0.0, 0.0]
    for i in range(0, len(vertices), 3):
        a, b, c = vertices[i:i+3]
        for u, v in ((a, b), (b, c), (c, a)):
            edges[tuple(sorted((u, v)))] += 1
            directed[(u, v)] += 1
            adjacency[u].add(v)
            adjacency[v].add(u)
        dv = (a[0]*(b[1]*c[2]-b[2]*c[1])
              + a[1]*(b[2]*c[0]-b[0]*c[2])
              + a[2]*(b[0]*c[1]-b[1]*c[0])) / 6
        volume += dv
        for axis in range(3):
            first_moment[axis] += dv*(a[axis]+b[axis]+c[axis])/4
    unseen = set(vertices)
    components = 0
    while unseen:
        components += 1
        pending = [unseen.pop()]
        while pending:
            new = adjacency[pending.pop()] & unseen
            unseen -= new
            pending.extend(new)
    assert all(n == 2 for n in edges.values()), f'{path}: non-manifold edges'
    assert all(directed[(u, v)] == directed[(v, u)] for u, v in edges), f'{path}: inconsistent winding'
    assert components == 1, f'{path}: disconnected solids'
    assert volume > 0, f'{path}: inverted volume'
    return dict(file=str(path), triangles=len(vertices)//3, closed=True,
                components=components, volume_mm3=round(volume, 4),
                centroid_mm=[round(m/volume, 5) for m in first_moment],
                bounds_mm=[[min(v[i] for v in vertices), max(v[i] for v in vertices)] for i in range(3)])


if __name__ == '__main__':
    root = Path(__file__).resolve().parent
    report = [inspect(root / name) for name in ('1-base.stl', '2-camera_insert.stl', '3-d500_module.stl')]
    print(json.dumps(report, indent=2))
    (root / 'mesh_report.json').write_text(json.dumps(report, indent=2) + '\n')
