# agent-1/src/collectors/grid_search.py

import math
def generate_grid_points(lat, lng, radius_miles):

    offset = radius_miles / 69.0
    return [
        (lat, lng),                  # center
        (lat + offset, lng),         # north
        (lat - offset, lng),         # south
        (lat, lng + offset),         # east
        (lat, lng - offset),         # west
    ]