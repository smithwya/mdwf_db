import argparse
import pkgutil
import importlib
import os
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(
        prog="mdwf_db",
        description="MDWF Database Management Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Available commands are grouped by function:

Database Management:
  init-db          Initialize a new database and directory structure
  add-ensemble     Add a new ensemble to the database
  remove-ensemble  Remove an ensemble from the database
  promote-ensemble Move a tuning ensemble to production
  query           List ensembles or show details for one

Job Script Generation:
  hmc-script      Generate HMC XML and SLURM script
  hmc-xml         Generate HMC parameters XML
  smear-script    Generate GLU smearing SLURM script
  meson-2pt       Generate WIT meson 2pt SLURM script
  wit-input       Generate WIT input file
  glu-input       Generate GLU input file

Database Operations:
  update          Create or update an operation in the database

For detailed help on any command, use: mdwf_db <command> --help
"""
    )

    DEFAULT_DB = os.getenv('MDWF_DB',
                           str(Path('.').resolve()/'mdwf_ensembles.db'))
    db_parent = argparse.ArgumentParser(add_help=False)
    db_parent.add_argument(
        '--db-file',
        default=DEFAULT_DB,
        help='Path to the SQLite DB (or set MDWF_DB env).'
    )

    subs   = parser.add_subparsers(dest='cmd')

    orig_add = subs.add_parser
    def add_parser(name, **kwargs):
        # collect any existing parents, make them into a list
        parents = kwargs.get('parents', [])
        if not isinstance(parents, list):
            parents = [parents]
        # ensure our db_parent is always there
        parents.append(db_parent)
        kwargs['parents'] = parents
        return orig_add(name, **kwargs)
    
    subs.add_parser = add_parser

    # Dynamically import every module in cli/commands and call its register()
    pkg = importlib.import_module('MDWFutils.cli.commands')
    for finder, name, ispkg in pkgutil.iter_modules(pkg.__path__):
        mod = importlib.import_module(f"MDWFutils.cli.commands.{name}")
        # each module must define register(subparsers)
        if hasattr(mod, 'register'):
            mod.register(subs)

    args = parser.parse_args()
    if not args.cmd:
        parser.print_help()
        return 1

    # every module must set args.func to its handler in register()
    return args.func(args)

if __name__=='__main__':
    sys.exit(main())