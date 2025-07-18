import os
import copy
from pathlib import Path
from MDWFutils.db import get_ensemble_details

DEFAULT_WIT_PARAMS = {
    "Run name": {
        "name": "u_stout8"
    },
    "Directories": {
        "cnfg_dir": "../cnfg_stout8/"
    },
    "Configurations": {
        "first": "CFGNO",
        "last": "CFGNO",
        "step": "4"
    },
    "Random number generator": {
        "level": "0",
        "seed": "3993"
    },
    "Lattice parameters": {
        "Ls": "10",
        "M5": "1.0",
        "b": "1.75",
        "c": "0.75"
    },
    "Boundary conditions": {
        "type": "APeri"
    },
    "Witness": {
        "no_prop": "3",
        "no_solver": "2"
    },
    "Solver 0": {
        "solver": "CG",
        "nkv": "24",
        "isolv": "1",
        "nmr": "3",
        "ncy": "3",
        "nmx": "8000",
        "exact_deflation": "true"
    },
    "Solver 1": {
        "solver": "CG",
        "nkv": "24",
        "isolv": "1",
        "nmr": "3",
        "ncy": "3",
        "nmx": "8000",
        "exact_deflation": "false"
    },
    "Exact Deflation": {
        "Cheby_fine": "0.01,-1,24",
        "Cheby_smooth": "0,0,0",
        "Cheby_coarse": "0,0,0",
        "kappa": "0.125",
        "res": "1E-5",
        "nmx": "64",
        "Ns": "64"
    },
    "Propagator 0": {
        "Noise": "Z2xZ2",
        "Source": "Wall",
        "Dilution": "PS",
        "pos": "0 0 0 -1",
        "mom": "0 0 0 0",
        "twist": "0 0 0",
        "kappa": "KAPPA_L",
        "mu": "0.",
        "Seed": "12345",
        "idx_solver": "0",
        "res": "1E-12",
        "sloppy_res": "1E-4"
    },
    "Propagator 1": {
        "Noise": "Z2xZ2",
        "Source": "Wall",
        "Dilution": "PS",
        "pos": "0 0 0 -1",
        "mom": "0 0 0 0",
        "twist": "0 0 0",
        "kappa": "KAPPA_S",
        "mu": "0.",
        "Seed": "12345",
        "idx_solver": "1",
        "res": "1E-12",
        "sloppy_res": "1E-6"
    },
    "Propagator 2": {
        "Noise": "Z2xZ2",
        "Source": "Wall",
        "Dilution": "PS",
        "pos": "0 0 0 -1",
        "mom": "0 0 0 0",
        "twist": "0 0 0",
        "kappa": "KAPPA_C",
        "mu": "0.",
        "Seed": "12345",
        "idx_solver": "1",
        "res": "5E-15",
        "sloppy_res": "5E-15"
    },
    "AMA": {
        "NEXACT": "2",
        "SLOPPY_PREC": "1E-5",
        "NHITS": "1",
        "NT": "48"
    }
}

DEFAULT_WIT_ENV = 'source /global/cfs/cdirs/m2986/cosmon/mdwf/software/scripts/env_gpu.sh'
DEFAULT_WIT_BIND = '/global/cfs/cdirs/m2986/cosmon/mdwf/ANALYSIS/WIT/bind.sh'
DEFAULT_WIT_EXEC = '/global/cfs/cdirs/m2986/cosmon/mdwf/software/install_gpu/wit/bin/Meson'

def update_nested_dict(d, updates):
    """
    Recursively merge updates into d.
    """
    for key, val in updates.items():
        if isinstance(val, dict) and key in d and isinstance(d[key], dict):
            update_nested_dict(d[key], val)
        else:
            d[key] = val
    return d


def generate_wit_input(
    output_file,
    custom_changes=None
):
    """
    Write a WIT .ini‐style input file.
      - output_file: path to write DWF.in
      - custom_changes: nested dict { section: { key: value, … }, … }
    """
    params = copy.deepcopy(DEFAULT_WIT_PARAMS)
    if custom_changes:
        update_nested_dict(params, custom_changes)

    outf = Path(output_file)
    outf.parent.mkdir(parents=True, exist_ok=True)

    with open(outf, 'w') as f:
        for section, block in params.items():
            f.write(f"[{section}]\n")
            for key, val in block.items():
                f.write(f"{key:<12} {val}\n")
            f.write("\n")

    print(f"Generated WIT input file: {outf}")
    return str(outf)


def generate_wit_sbatch(
    output_file=None,
    db_file=None,
    ensemble_id=None,
    ensemble_dir=None,
    custom_changes=None,
    wit_exec_path=None,
    bind_script=None,
    # SBATCH arguments
    account='m2986_g',
    constraint='gpu',
    queue='regular',
    time_limit='06:00:00',
    nodes=1,
    cpus_per_task=16,
    gpus=4,
    gpu_bind='none',
    mail_user=None,
    ranks=4,
    step=4,
    first=444,
    last=444
):
    """
    Create a SBATCH script under ensemble_dir/meson2pt/.
    """
    if mail_user is None:
        raise ValueError("mail_user is required")

    ensemble_dir = os.path.abspath(ensemble_dir)
    db_file      = os.path.abspath(db_file)

    # Get ensemble details
    ens = get_ensemble_details(db_file, ensemble_id)
    if not ens:
        raise RuntimeError(f"Ensemble {ensemble_id} not found")
    
    # Get lattice dimensions and kappa values from ensemble parameters
    p = ens['parameters']
    try:
        L = int(p['L'])
        T = int(p['T'])
        if L <= 0 or T <= 0:
            raise ValueError(f"Invalid lattice dimensions L={L}, T={T}")
    except (KeyError, ValueError) as e:
        raise RuntimeError(f"Failed to get lattice dimensions: {e}")

    kappaL = 1 / (2 * float(p.get('ml', 0.0195)) + 8)
    kappaS = 1 / (2 * float(p.get('ms', 0.0725)) + 8)
    kappaC = 1 / (2 * float(p.get('mc', 0.8555)) + 8)

    # Validate ogeom and calculate lgeom
    ogeom = [1, 1, 1, 4]  # Default values
    lgeom = [L//ogeom[0], L//ogeom[1], L//ogeom[2], T//ogeom[3]]
    
    # Check if divisions result in integers
    if any(x * y != L for x, y in zip(ogeom[:3], lgeom[:3])) or ogeom[3] * lgeom[3] != T:
        raise ValueError(f"Invalid ogeom {ogeom} for lattice {L}x{L}x{L}x{T}")
    
    # Check if lgeom values are even
    if any(x % 2 != 0 for x in lgeom):
        raise ValueError(f"lgeom values must be even, got {lgeom}")

    # Set up environment, bind, and exec defaults
    env_setup = DEFAULT_WIT_ENV
    bind_sh = bind_script or DEFAULT_WIT_BIND
    exec_path = wit_exec_path or DEFAULT_WIT_EXEC

    workdir = Path(ensemble_dir) / "meson2pt"
    workdir.mkdir(parents=True, exist_ok=True)

    if not output_file:
        # Get first/last from custom_changes
        first = custom_changes.get('Configurations', {}).get('first', '444') if custom_changes else '444'
        last = custom_changes.get('Configurations', {}).get('last', '444') if custom_changes else '444'
        output_file = str(workdir / f"meson2pt_{first}_{last}.sh")

    # Generate WIT input file with kappa values
    wit_input_file = Path(ensemble_dir) / "meson2pt" / "DWF.in"
    wit_params = {
        'Propagator 0': {'kappa': str(kappaL)},
        'Propagator 1': {'kappa': str(kappaS)},
        'Propagator 2': {'kappa': str(kappaC)}
    }
    if custom_changes:
        wit_params.update(custom_changes)
    generate_wit_input(str(wit_input_file), custom_changes=wit_params)

    # pack all WIT-specific params into one --params string
    params_str = " ".join(f"{k}={v}" for k,v in (custom_changes or {}).items())

    script = f"""#!/bin/bash
#SBATCH -A {account}
#SBATCH --nodes={nodes}
#SBATCH -C {constraint}
#SBATCH --gpus={gpus}
#SBATCH --time={time_limit}
#SBATCH --qos={queue}
#SBATCH --mail-user={mail_user}
#SBATCH --mail-type=ALL
#SBATCH -o {workdir}/jlog/%j.log

set -euo pipefail
cd {workdir}

#record RUNNING (one shot for the entire meson2pt job)
mdwf_db update \\
  --db-file="{db_file}" \\
  --ensemble-id={ensemble_id} \\
  --operation-type="WIT_MESON2PT" \\
  --status="RUNNING" \\
  --params="{params_str}"

# On exit/failure, update status + code + runtime
update_status() {{
  local EC=$?
  local ST="COMPLETED"
  [[ $EC -ne 0 ]] && ST="FAILED"

  mdwf_db update \\
    --db-file="{db_file}" \\
    --ensemble-id={ensemble_id} \\
    --operation-type="WIT_MESON2PT" \\
    --status="$ST" \\
    --exit-code=$EC \\
    --runtime=$SECONDS \\
    --params="slurm_job=$SLURM_JOB_ID host=$(hostname)"

  echo "Meson2pt job $ST ($EC)"
}}
trap update_status EXIT TERM INT HUP QUIT

SECONDS=0

{env_setup}
export LD_LIBRARY_PATH=/global/cfs/cdirs/m2986/cosmon/mdwf/software/install_gpu/quda/lib:$LD_LIBRARY_PATH

### MPI flags
export MPICH_RDMA_ENABLED_CUDA=1
export MPICH_GPU_SUPPORT_ENABLED=1
export MPICH_NEMESIS_ASYNC_PROGRESS=1

### Cray/Slurm flags
export OMP_NUM_THREADS={cpus_per_task}
export SLURM_CPU_BIND=cores
export CRAY_ACCEL_TARGET=nvidia80

### QUDA specific flags
export QUDA_RESOURCE_PATH=`pwd`/quda_resource
[[ -d $QUDA_RESOURCE_PATH ]] || mkdir -p $QUDA_RESOURCE_PATH
export QUDA_ENABLE_GDR=1

### MPICH debugging flags
export MPICH_VERSION_DISPLAY=1
export MPICH_OFI_NIC_VERBOSE=2
export MPICH_OFI_NIC_POLICY="USER"
export MPICH_OFI_NIC_MAPPING="0:3;1:2;2:1;3:0"
echo "MPICH_OFI_NIC_POLICY=${{MPICH_OFI_NIC_POLICY}}"
echo "MPICH_OFI_NIC_MAPPING=${{MPICH_OFI_NIC_MAPPING}}"

# Generate random seed for each config
generate_seed() {{
    local cfg=$1
    # Use config number as part of seed to ensure uniqueness
    echo $(( (RANDOM + cfg) % 10000 ))
}}

# loop over cfg numbers
for cfg in $(seq {first} {step} {last}); do
    if [[ ! -e DATA/Meson_2pt_00u_stout8n${{cfg}}.bin ]]; then
        # Generate new seed for this config
        seed=$(generate_seed $cfg)
        
        # Generate WIT input for this config, only changing seed and config numbers
        mdwf_db wit-input -e {ensemble_id} -o DWF.in \\
            -w "Configurations.first=$cfg Configurations.last=$cfg \\
                Random number generator.seed=$seed \\
                Propagator 0.Seed=$seed Propagator 1.Seed=$seed Propagator 2.Seed=$seed"
        
        echo "Running cfg $cfg with seed $seed"
        srun -n {ranks} {bind_sh} {exec_path} \\
             -i DWF.in -ogeom {ogeom[0]} {ogeom[1]} {ogeom[2]} {ogeom[3]} \\
             -lgeom {lgeom[0]} {lgeom[1]} {lgeom[2]} {lgeom[3]}
    fi
done

echo "All done in $SECONDS seconds"
"""

    Path(output_file).write_text(script)
    os.chmod(output_file, 0o755)
    print(f"Generated WIT SBATCH script: {output_file}")
    return str(output_file)