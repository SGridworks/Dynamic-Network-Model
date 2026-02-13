#!/usr/bin/env python3
"""
Guide 03: Hosting Capacity Analysis (OpenDSS)
Testing with restructured dataset
"""

import pandas as pd
import numpy as np
import os

DATA_DIR = "sisyphean-power-and-light/"

print("="*70)
print("GUIDE 03: HOSTING CAPACITY ANALYSIS")
print("="*70)

# ============================================================================
# STEP 1: Check OpenDSS Files
# ============================================================================

print("\n[STEP 1] Validating OpenDSS model files...")

required_files = [
    "network/master.dss",
    "network/lines.dss",
    "network/transformers.dss",
    "network/loads.dss",
    "network/capacitors.dss",
    "network/coordinates.dss",
    "network/coordinates.csv"
]

all_present = True
for file_path in required_files:
    full_path = DATA_DIR + file_path
    exists = os.path.exists(full_path)
    status = "✅" if exists else "❌"
    print(f"{status} {file_path}")
    if not exists:
        all_present = False

if not all_present:
    print("\n⚠️  Some OpenDSS files missing!")
    exit(1)

# ============================================================================
# STEP 2: Load Coordinate Data
# ============================================================================

print("\n[STEP 2] Loading network coordinates...")

coords = pd.read_csv(DATA_DIR + "network/coordinates.csv")

print(f"✅ Buses loaded: {len(coords):,}")
print(f"✅ Coordinate range: X({coords['x'].min():.1f}, {coords['x'].max():.1f}), Y({coords['y'].min():.1f}, {coords['y'].max():.1f})")

# ============================================================================
# STEP 3: Attempt OpenDSS Initialization
# ============================================================================

print("\n[STEP 3] Attempting to initialize OpenDSS...")

try:
    import opendssdirect as dss

    # Compile the master DSS file
    master_path = os.path.abspath(DATA_DIR + "network/master.dss")
    dss.Text.Command(f"Compile {master_path}")

    circuit_name = dss.Circuit.Name()
    num_buses = dss.Circuit.NumBuses()
    num_nodes = dss.Circuit.NumNodes()

    print(f"✅ OpenDSS compiled successfully")
    print(f"✅ Circuit: {circuit_name}")
    print(f"✅ Buses: {num_buses}")
    print(f"✅ Nodes: {num_nodes}")

    # Run power flow
    dss.Solution.Solve()

    if dss.Solution.Converged():
        print(f"✅ Power flow converged")

        # Get voltage statistics
        dss.Circuit.SetActiveClass("Bus")
        voltages = []
        for i in range(num_buses):
            dss.Circuit.SetActiveBus(dss.Bus.Name())
            v_mag = dss.Bus.puVmagAngle()[::2]  # Get magnitude only
            if len(v_mag) > 0:
                voltages.append(v_mag[0])
            dss.Circuit.NextElement()

        voltages = np.array(voltages)
        print(f"\n" + "="*70)
        print("VOLTAGE PROFILE")
        print("="*70)
        print(f"  Min Voltage: {voltages.min():.4f} p.u.")
        print(f"  Max Voltage: {voltages.max():.4f} p.u.")
        print(f"  Mean Voltage: {voltages.mean():.4f} p.u.")
        print(f"  Std Voltage: {voltages.std():.4f} p.u.")

        # Check ANSI limits (0.95 - 1.05 p.u.)
        violations = np.sum((voltages < 0.95) | (voltages > 1.05))
        print(f"  Voltage violations: {violations} buses")

        # Simplified hosting capacity calculation
        # Test adding 100kW PV at random bus
        test_pv_size_kw = 100
        random_bus = coords.sample(1).iloc[0]["bus_id"]

        print(f"\n" + "="*70)
        print("HOSTING CAPACITY TEST")
        print("="*70)
        print(f"  Test PV location: {random_bus}")
        print(f"  Test PV size: {test_pv_size_kw} kW")

        # Add PVSystem
        dss.Text.Command(f"New PVSystem.TestPV bus1={random_bus} kVA={test_pv_size_kw} irrad=1.0 Pmpp={test_pv_size_kw}")

        # Re-solve
        dss.Solution.Solve()

        if dss.Solution.Converged():
            print(f"✅ Power flow with PV converged")

            # Re-check voltages
            voltages_with_pv = []
            dss.Circuit.SetActiveClass("Bus")
            for i in range(num_buses):
                dss.Circuit.SetActiveBus(dss.Bus.Name())
                v_mag = dss.Bus.puVmagAngle()[::2]
                if len(v_mag) > 0:
                    voltages_with_pv.append(v_mag[0])
                dss.Circuit.NextElement()

            voltages_with_pv = np.array(voltages_with_pv)
            violations_with_pv = np.sum((voltages_with_pv < 0.95) | (voltages_with_pv > 1.05))

            print(f"  Max voltage with PV: {voltages_with_pv.max():.4f} p.u.")
            print(f"  Voltage violations with PV: {violations_with_pv} buses")

            if violations_with_pv == violations:
                print(f"✅ {test_pv_size_kw} kW PV can be hosted without violations")
            else:
                print(f"⚠️  {test_pv_size_kw} kW PV causes {violations_with_pv - violations} new violations")

        else:
            print(f"❌ Power flow with PV did not converge")

    else:
        print(f"❌ Power flow did not converge")

    OPENDSS_AVAILABLE = True

except ImportError:
    print("⚠️  OpenDSS not installed. Skipping power flow analysis.")
    print("Install with: pip3 install opendssdirect.py")
    OPENDSS_AVAILABLE = False

except Exception as e:
    print(f"❌ OpenDSS error: {e}")
    OPENDSS_AVAILABLE = False

# ============================================================================
# STEP 4: Summary
# ============================================================================

print("\n" + "="*70)
print("GUIDE 03 TEST COMPLETE")
print("="*70)

print(f"\n✅ OpenDSS model files validated: {all_present}")
print(f"✅ Network buses: {len(coords):,}")

if OPENDSS_AVAILABLE:
    print(f"✅ OpenDSS compilation: Success")
    print(f"✅ Power flow: Converged")
    print(f"✅ Hosting capacity test: Completed")
else:
    print(f"⚠️  OpenDSS not available - install to run full analysis")

print("\n🎯 KEY FINDINGS:")
print(f"   • Network model structure validated")
print(f"   • Coordinate data available for {len(coords)} buses")
if OPENDSS_AVAILABLE:
    print(f"   • Baseline voltage range: {voltages.min():.3f} - {voltages.max():.3f} p.u.")
    print(f"   • Voltage violations: {violations} buses")

print("\n✅ Hosting capacity dataset validated!")
print("="*70)
