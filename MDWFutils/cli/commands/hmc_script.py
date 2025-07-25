#!/usr/bin/env python3
"""
commands/hmc_script.py

Generate HMC XML and SLURM script for gauge configuration generation.
"""
import argparse
import os
import sys
from pathlib import Path
from MDWFutils.db import get_ensemble_details
from MDWFutils.jobs.hmc import generate_hmc_parameters, generate_hmc_slurm_gpu

def register(subparsers):
    p = subparsers.add_parser(
        'hmc-script',
        help='Generate HMC XML and SLURM script for gauge generation',
        description="""
Generate HMC XML parameters and SLURM batch script for gauge configuration generation.

WHAT THIS DOES:
• Creates HMC XML parameter file with physics parameters
• Generates SLURM batch script for GPU execution
• Sets up proper directory structure and file paths
• Configures job parameters for HPC submission

HMC MODES:
  tepid:    Initial thermalization run (TepidStart)
  continue: Continue from existing checkpoint (CheckpointStart)
  reseed:   Start new run with different seed (CheckpointStartReseed)

JOB PARAMETERS (via -j/--job-params):
Required parameters:
  cfg_max:     Maximum configuration number to generate

Optional parameters (with defaults):
  constraint: gpu           # Node constraint
  time_limit: 17:00:00      # Job time limit
  cpus_per_task: 32         # CPUs per task
  nodes: 1                  # Number of nodes
  gpus_per_task: 1          # GPUs per task
  gpu_bind: none            # GPU binding
  mail_user: (from env)     # Email notifications
  queue: regular            # SLURM partition
  exec_path: (auto)         # Path to HMC executable
  bind_script: (auto)       # CPU binding script

XML PARAMETERS (via -x/--xml-params):
Available HMC parameters:
  StartTrajectory:      Starting trajectory number (default: 0)
  Trajectories:         Number of trajectories to generate (default: 50)
  MetropolisTest:       Perform Metropolis test (true/false, default: true)
  NoMetropolisUntil:    Trajectory to start Metropolis (default: 0)
  PerformRandomShift:   Perform random shift (true/false, default: true)
  StartingType:         Start type (TepidStart/CheckpointStart/CheckpointStartReseed)
  Seed:                 Random seed (for reseed mode)
  MDsteps:              Number of MD steps (default: 2)
  trajL:                Trajectory length (default: 1.0)

EXAMPLES:
  # Basic HMC script for new ensemble
  mdwf_db hmc-script -e 1 -a m2986 -m tepid -j "cfg_max=100"

  # Continue existing run
  mdwf_db hmc-script -e 1 -a m2986 -m continue \\
    -j "cfg_max=200 time_limit=24:00:00" \\
    -x "StartTrajectory=100 Trajectories=100"

  # Custom parameters and output file
  mdwf_db hmc-script -e 1 -a m2986 -m tepid -o custom_hmc.sh \\
    -j "cfg_max=50 nodes=2 time_limit=12:00:00" \\
    -x "MDsteps=4 trajL=0.75 Seed=12345"
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument('-e', '--ensemble-id', type=int, required=True,
                   help='ID of the ensemble to generate HMC script for')
    p.add_argument('-a', '--account', required=True,
                   help='SLURM account name (e.g., m2986)')
    p.add_argument('-m', '--mode', required=True,
                   choices=['tepid', 'continue', 'reseed'],
                   help='HMC run mode: tepid (new), continue (existing), or reseed (new seed)')
    p.add_argument('--base-dir', default='.',
                   help='Root directory containing TUNING/ and ENSEMBLES/ (default: current directory)')
    p.add_argument('-x', '--xml-params', default='',
                   help='Space-separated key=val pairs for HMC XML parameters')
    p.add_argument('-j', '--job-params', default='',
                   help='Space-separated key=val pairs for SLURM job parameters. Required: cfg_max')
    p.add_argument('-o', '--output-file',
                   help='Output SBATCH script path (auto-generated if not specified)')
    p.set_defaults(func=do_hmc_script)

def do_hmc_script(args):
    # Get ensemble details
    ens = get_ensemble_details(args.db_file, args.ensemble_id)
    if not ens:
        print(f"ERROR: Ensemble {args.ensemble_id} not found", file=sys.stderr)
        return 1
    
    # Parse job parameters
    job_dict = {}
    if args.job_params:
        for param in args.job_params.split():
            if '=' in param:
                key, val = param.split('=', 1)
                job_dict[key] = val
    
    # Check required job parameters
    if 'cfg_max' not in job_dict:
        print("ERROR: cfg_max is required in job parameters", file=sys.stderr)
        return 1
    
    # Parse XML parameters
    xml_dict = {}
    if args.xml_params:
        for param in args.xml_params.split():
            if '=' in param:
                key, val = param.split('=', 1)
                xml_dict[key] = val
    
    # Get ensemble directory and details
    ens_dir = Path(ens['directory']).resolve()
    base = Path(args.base_dir).resolve()
    
    try:
        rel = ens_dir.relative_to(base)
    except ValueError:
        print(f"ERROR: {ens_dir} is not under base-dir {base}", file=sys.stderr)
        return 1
    
    root = rel.parts[0]  # "TUNING" or "ENSEMBLES"
    ens_rel = str(rel)   # e.g. "TUNING/b6.0/.../T32"
    ens_name = ens_rel.replace('TUNING/', '').replace('ENSEMBLES/', '').replace('/', '_')
    
    # Ensure slurm folder & output path
    slurm_dir = ens_dir / 'slurm'
    slurm_dir.mkdir(parents=True, exist_ok=True)
    out_file = args.output_file or slurm_dir / f"hmc_{args.ensemble_id}_{args.mode}.sbatch"
    
    # Generate HMC XML parameters
    try:
        generate_hmc_parameters(str(ens_dir), mode=args.mode, **xml_dict)
    except Exception as e:
        print(f"ERROR: Failed to generate HMC XML: {e}", file=sys.stderr)
        return 1
    
    # Set up job parameters with defaults
    job_params = {
        'constraint': 'gpu',
        'time_limit': '17:00:00',
        'cpus_per_task': '32',
        'nodes': '1',
        'gpus_per_task': '1',
        'gpu_bind': 'none',
        'mail_user': os.getenv('USER', ''),
        'mpi': '2.1.1.2',
    }
    job_params.update(job_dict)
    
    # Set ntasks_per_node if not provided
    if 'ntasks_per_node' not in job_params:
        job_params['ntasks_per_node'] = job_params['cpus_per_task']
    
    # Set resubmit flag
    if 'resubmit' not in job_params:
        job_params['resubmit'] = 'false' if args.mode == 'reseed' else 'true'
    
    # Generate SLURM script
    try:
        generate_hmc_slurm_gpu(
            out_path=str(out_file),
            db_file=args.db_file,
            ensemble_id=args.ensemble_id,
            base_dir=args.base_dir,
            type_=root,
            ens_relpath=ens_rel,
            ens_name=ens_name,
            account=args.account,
            mode=args.mode,
            **job_params
        )
        print(f"Generated HMC script: {out_file}")
        return 0
    except Exception as e:
        print(f"ERROR: Failed to generate HMC script: {e}", file=sys.stderr)
        return 1

# ----------------- Deprecated Click CLI removed -----------------