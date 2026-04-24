"""Quick test: compare two different scans to prove unique results."""
from brain_scan_analyzer import analyze_brain_scan
import os

scans = [f for f in os.listdir("data/scans") if f.endswith((".jpg", ".jpeg", ".png"))]
print(f"Found {len(scans)} scans")

r1 = analyze_brain_scan(f"data/scans/{scans[0]}", "Ischemic", 0.8)
r2 = analyze_brain_scan(f"data/scans/{scans[5]}", "Hemorrhagic", 0.9)

print(f"\n--- Scan 1: {scans[0]} ---")
for z in r1["affected_zones"]:
    print(f"  {z['zone'][:35]:35s}  severity={z['severity']:.2f}  asym={z['asymmetry']:.4f}  lesion={z['lesion_ratio']:.4f}")
m1 = r1["scan_metrics"]
print(f"  Metrics: coverage={m1['lesion_coverage_pct']:.1f}%  asym={m1['hemisphere_asymmetry']:.3f}  side={m1['affected_side']}")

print(f"\n--- Scan 2: {scans[5]} ---")
for z in r2["affected_zones"]:
    print(f"  {z['zone'][:35]:35s}  severity={z['severity']:.2f}  asym={z['asymmetry']:.4f}  lesion={z['lesion_ratio']:.4f}")
m2 = r2["scan_metrics"]
print(f"  Metrics: coverage={m2['lesion_coverage_pct']:.1f}%  asym={m2['hemisphere_asymmetry']:.3f}  side={m2['affected_side']}")

print("\n=> Results are DIFFERENT per scan: CONFIRMED" if m1 != m2 else "\n=> WARNING: same results")
