#!/usr/bin/env python3
"""
commands/wit_input.py

Generate WIT input files for meson correlator measurements.
"""
import argparse, ast, sys, os
from pathlib import Path
from MDWFutils.db import get_ensemble_details
from MDWFutils.jobs.wit import generate_wit_input

def register(subparsers):
    p = subparsers.add_parser(
        'wit-input', 
        help='Generate WIT input file for correlator measurements',
        description="""
Generate a WIT input file (DWF.in) for meson correlator measurements.

WHAT THIS DOES:
• Creates a properly formatted WIT input file
• Uses ensemble parameters to set lattice and physics parameters
• Provides sensible defaults for all WIT parameters
• Allows customization of any parameter

WIT PROGRAM:
WIT (Wilson Improved Twisted mass) computes meson 2-point correlators
from Domain Wall Fermion propagators on gauge configurations.

PARAMETER CUSTOMIZATION:
WIT parameters use dot notation (SECTION.KEY=value) and can be overridden:

Run configuration:
  name: u_stout8                    # Run name
  cnfg_dir: ../cnfg_stout8/         # Configuration directory

Configuration range:
  Configurations.first: 0           # First configuration number
  Configurations.last: 100          # Last configuration number  
  Configurations.step: 4            # Step between configurations

Lattice parameters (auto-set from ensemble):
  Ls: (from ensemble)               # Domain wall extent
  M5: 1.0                          # Domain wall mass
  b: (from ensemble)                # Domain wall height
  c: (from ensemble)                # Domain wall parameter

Measurement setup:
  Witness.no_prop: 3                # Number of propagators (light, strange, charm)
  Witness.no_solver: 2              # Number of solvers

Solver parameters:
  Solver 0.solver: CG               # Conjugate gradient solver
  Solver 0.nmx: 8000                # Maximum iterations
  Solver 0.exact_deflation: true    # Use exact deflation
  Solver 1.exact_deflation: false   # Second solver settings

Propagator parameters:
  Propagator 0.Source: Wall         # Source type (Wall, Point)
  Propagator 0.Dilution: PS         # Dilution scheme
  Propagator 0.kappa: (auto from ml) # Light quark kappa
  Propagator 1.kappa: (auto from ms) # Strange quark kappa
  Propagator 2.kappa: (auto from mc) # Charm quark kappa

Note: Kappa values are automatically calculated from quark masses
stored in the ensemble parameters. Do not set these manually.

EXAMPLES:
  # Basic WIT input with defaults
  mdwf_db wit-input -e 1 -o DWF.in

  # Custom configuration range
  mdwf_db wit-input -e 1 -o DWF.in -w "Configurations.first=100 Configurations.last=200"

  # Point source measurement
  mdwf_db wit-input -e 1 -o DWF.in -w "Propagator 0.Source=Point Propagator 0.pos=0 0 0 0"

  # Custom solver settings
  mdwf_db wit-input -e 1 -o DWF.in -w "Solver 0.nmx=10000 Solver 0.res=1E-12"

For complete parameter documentation, see the WIT manual.
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument('--ensemble-id', '-e', type=int, required=True,
                   help='ID of the ensemble to generate WIT input for')
    p.add_argument('--output-file', '-o', required=True,
                   help='Path to output WIT input file (e.g., DWF.in)')
    p.add_argument('--wit-params', '-w', default='',
                   help='Space-separated key=val pairs for WIT parameters using dot notation. Example: "Configurations.first=100 Configurations.last=200"')
    p.set_defaults(func=do_wit_input)

def do_wit_input(args):
    # Get ensemble details
    ens = get_ensemble_details(args.db_file, args.ensemble_id)
    if not ens:
        print(f"ERROR: Ensemble {args.ensemble_id} not found", file=sys.stderr)
        return 1

    # Parse WIT parameters into nested dict
    wdict = {}
    if args.wit_params:
        for tok in args.wit_params.split():
            if '=' not in tok:
                print(f"ERROR: Invalid parameter format '{tok}'. Use SECTION.KEY=VALUE", file=sys.stderr)
                return 1
            key, raw = tok.split('=', 1)
            try:
                val = ast.literal_eval(raw)
            except:
                val = raw
            
            # Build nested dictionary structure
            parts = key.split('.')
            d = wdict
            for p in parts[:-1]:
                if p not in d or not isinstance(d[p], dict):
                    d[p] = {}
                d = d[p]
            d[parts[-1]] = val

    # Generate WIT input
    try:
        output_path = Path(args.output_file)
        generate_wit_input(
            ensemble_params=ens['parameters'],
            output_file=output_path,
            custom_params=wdict
        )
        print(f"Generated WIT input file: {output_path.resolve()}")
        return 0
        
    except Exception as e:
        print(f"ERROR: Failed to generate WIT input: {e}", file=sys.stderr)
        return 1