"""Generator for branch infrastructure topology and baseline profiles."""
import random
from typing import List, Dict, Any


REGIONS = ["Northern Zone", "Southern Zone", "Eastern Zone", "Western Zone", "Metropolitan Capital", "Central Hub"]
WAN_TYPES = ["MPLS Primary", "SD-WAN Dual-Homed", "Broadband VPN", "Direct Fiber 100M", "Hybrid MPLS+4G Backup"]


def generate_branch_inventory(num_branches: int = 50, seed: int = 42) -> List[Dict[str, Any]]:
    """
    Generate deterministic branch definitions with realistic baselines and topologies.
    Ensures natural variation between branches while remaining reproducible.
    """
    rng = random.Random(seed)
    branches = []

    for i in range(1, num_branches + 1):
        branch_id = f"B{i:03d}"
        region = rng.choice(REGIONS)
        wan_type = rng.choice(WAN_TYPES)
        name = f"Branch {branch_id} - {region.split()[0]} {i}"

        # Per-branch intrinsic baseline offsets (simulate physical distance / hardware variety)
        baseline_latency_offset = rng.uniform(-10.0, 15.0)
        baseline_rssi_offset = rng.uniform(-5.0, 5.0)
        baseline_app_offset = rng.uniform(-40.0, 60.0)

        branches.append({
            "branch_id": branch_id,
            "name": name,
            "region": region,
            "wan_type": wan_type,
            "baseline_latency_offset": baseline_latency_offset,
            "baseline_rssi_offset": baseline_rssi_offset,
            "baseline_app_offset": baseline_app_offset
        })

    return branches
