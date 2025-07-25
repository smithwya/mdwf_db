#!/usr/bin/env python3
"""
commands/hmc_xml.py

Sub‐command "hmc-xml": generate the HMCparameters XML (tepid, continue or reseed)
for a given ensemble.
"""
import sys
from pathlib import Path
import argparse

from MDWFutils.db import get_ensemble_details
from MDWFutils.jobs.hmc import generate_hmc_parameters

def register(subparsers: argparse._SubParsersAction):
    p = subparsers.add_parser(
        'hmc-xml',
        help='Generate HMC parameters XML file',
        description="""
Generate HMC parameters XML file for an ensemble. This command:
1. Creates HMCparameters.<mode>.xml with default parameters
2. Allows customization of any parameter
3. Supports different run modes

Available run modes:
- tepid: Initial thermalization run
- continue: Continue from existing configuration
- reseed: Start new run with different seed

Common XML parameters:
- n_therm: Number of thermalization steps
- n_traj: Number of trajectories
- dt: Molecular dynamics step size
- n_steps: Steps per trajectory
- seed: Random number seed

Example:
  mdwf_db hmc-xml -e 1 -m tepid -x "n_therm=100 n_traj=50 dt=0.01"
"""
    )
    p.add_argument(
        '-e','--ensemble-id',
        type=int,
        required=True,
        help='ID of the ensemble to generate XML for'
    )
    p.add_argument(
        '-m','--mode',
        choices=['tepid','continue','reseed'],
        required=True,
        help='Run mode: tepid (new), continue (existing), or reseed (new seed)'
    )
    p.add_argument(
        '-b','--base-dir',
        default='.',
        help='Root directory containing TUNING/ & ENSEMBLES/ (default: current directory)'
    )
    p.add_argument(
        '-x','--xml-params',
        default='',
        help=('Space-separated key=val pairs to override XML defaults. '
              'Example: "n_therm=100 n_traj=50 dt=0.01"')
    )
    p.set_defaults(func=do_hmc_xml)


def do_hmc_xml(args):
    # fetch the ensemble
    ens = get_ensemble_details(args.db_file, args.ensemble_id)
    if not ens:
        print(f"ERROR: ensemble {args.ensemble_id} not found", file=sys.stderr)
        return 1

    # resolve its on‐disk path
    ens_dir = Path(ens['directory']).resolve()

    # parse the xml‐params string into a dict
    xdict = {}
    for tok in args.xml_params.split():
        if '=' not in tok:
            print(f"ERROR: bad xml param '{tok}'", file=sys.stderr)
            return 1
        k, v = tok.split('=', 1)
        xdict[k] = v

    # generate the XML
    # This will produce HMCparameters.<mode>.xml under ens_dir
    generate_hmc_parameters(
        ensemble_dir = str(ens_dir),
        mode         = args.mode,
        **xdict
    )

    print(f"Wrote HMCparameters.{args.mode}.xml to {ens_dir}")
    return 0