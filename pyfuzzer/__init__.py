import sys
import os
import argparse
import subprocess
import sysconfig
import shutil
import glob

from .version import __version__


SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))

CFLAGS = os.getenv('CFLAGS', None)
LDFLAGS = os.getenv('LDFLAGS', None)
CC = os.getenv('CC', 'clang')
LIB_FUZZING_ENGINE = os.getenv('LIB_FUZZING_ENGINE', '-fsanitize=fuzzer')

def mkdir_p(name):
    if not os.path.exists(name):
        os.makedirs(name)


def includes():
    include = sysconfig.get_path('include')

    return [f'-I{include}']


def ldflags():
    ldflags = sysconfig.get_config_var('LDFLAGS')
    ldversion = sysconfig.get_config_var('LDVERSION')
    ldflags += f' -lpython{ldversion}'
    ldflags += f' -L{sysconfig.get_config_var("LIBDIR")}'
    ldflags += f' {sysconfig.get_config_var("LIBS")}'
    if LDFLAGS:
        ldflags += f' {LDFLAGS}'
    return ldflags.split()


def run_command(command, env=None):
    print(' '.join(command))

    subprocess.check_call(command, env=env)


def generate(mutator):
    if mutator is not None:
        shutil.copyfile(mutator, 'mutator.py')

def build(csources, modinit_func, output):
    command = [ CC ]
    command += [
        LIB_FUZZING_ENGINE,
        f'-DMODINIT_FUNC={modinit_func}'
    ]

    if CFLAGS:
        command += CFLAGS.split()
    else:
        command += [
            '-fprofile-instr-generate',
            '-fcoverage-mapping',
            '-g',
            '-fsanitize=undefined',
            '-fsanitize=signed-integer-overflow',
            '-fsanitize=alignment',
            '-fsanitize=bool',
            '-fsanitize=builtin',
            '-fsanitize=bounds',
            '-fsanitize=enum',
            '-fno-sanitize-recover=all'
        ]

    command += includes()
    command += csources
    command += [
        os.path.join(SCRIPT_DIR, 'pyfuzzer_common.c'),
        os.path.join(SCRIPT_DIR, 'pyfuzzer.c')
    ]
    command += ldflags()
    command += [
        '-o', output
    ]

    run_command(command)


def build_print(csources, modinit_func, output):
    command = [ CC ]
    command += [
        f'-DMODINIT_FUNC={modinit_func}',
    ]
    if CFLAGS:
        command += CFLAGS.split()
    command += includes()
    command += csources
    command += [
        os.path.join(SCRIPT_DIR, 'pyfuzzer_common.c'),
        os.path.join(SCRIPT_DIR, 'pyfuzzer_print.c')
    ]
    command += ldflags()
    command += [
        '-o', f'{output}_print'
    ]

    run_command(command)


def run(libfuzzer_arguments, bin):
    run_command(['rm', '-f', f'{bin}.profraw'])
    mkdir_p('corpus')
    command = [
        bin,
        'corpus',
        '-print_final_stats=1'
    ]
    command += libfuzzer_arguments
    env = os.environ.copy()
    env['LLVM_PROFILE_FILE'] = f'{bin}.profraw'
    run_command(command, env=env)


def print_coverage(bin):
    run_command([
        'llvm-profdata',
        'merge',
        '-sparse', f'{bin}.profraw',
        '-o', f'{bin}.profdata'
    ])
    run_command([
        'llvm-cov',
        'show',
        bin,
        f'-instr-profile={bin}.profdata',
        '-ignore-filename-regex=/usr/|pyfuzzer.c'
    ])


def do_run(args):
    generate(args.mutator)
    run(args.libfuzzer_argument, args.bin)


def do_build(args):
    if args.modinit_func is None:
        filename = os.path.basename(args.csources[0])
        filename_base = os.path.splitext(filename)[0]
        modinit_func = f'PyInit_{filename_base}'
    else:
        modinit_func = args.modinit_func
    build(args.csources, modinit_func, args.output)
    if not args.fuzzer_only:
        build_print(args.csources, modinit_func, args.output)


def do_print_corpus(args):
    if args.units:
        filenames = args.units
    else:
        filenames = glob.glob('corpus/*')

    paths = '\n'.join(filenames)

    subprocess.run([args.bin_print], input=paths.encode('utf-8'), check=True)


def do_print_crashes(args):
    if args.units:
        filenames = args.units
    else:
        filenames = glob.glob('crash-*')

    for filename in filenames:
        proc = subprocess.run([args.bin_print], input=filename.encode('utf-8'))
        print()

        try:
            proc.check_returncode()
        except Exception as e:
            print(e)


def do_print_coverage(args):
    print_coverage(args.bin)


def do_clean(_args):
    shutil.rmtree('corpus', ignore_errors=True)

    for filename in glob.glob('crash-*'):
        os.remove(filename)

    for filename in glob.glob('oom-*'):
        os.remove(filename)

    for filename in glob.glob('slow-unit-*'):
        os.remove(filename)


def main():
    parser = argparse.ArgumentParser(
        description='Use libFuzzer to fuzz test Python 3.6+ C extension modules.')

    parser.add_argument('-d', '--debug', action='store_true')
    parser.add_argument('--version',
                        action='version',
                        version=__version__,
                        help='Print version information and exit.')

    # Workaround to make the subparser required in Python 3.
    subparsers = parser.add_subparsers(title='subcommands',
                                       dest='subcommand')
    subparsers.required = True

    # The run subparser.
    subparser = subparsers.add_parser(
        'run',
        description='Run the fuzz tester.')
    subparser.add_argument('-m', '--mutator', help='Mutator module.')
    subparser.add_argument(
        '-l', '--libfuzzer-argument',
        action='append',
        default=[],
        help="Add a libFuzzer command line argument.")
    subparser.add_argument('bin', nargs='?', help='fuzzer binary', default='./pyfuzzer')
    subparser.set_defaults(func=do_run)

    # The build subparser.
    subparser = subparsers.add_parser(
        'build',
        description='Build the fuzz tester.')
    subparser.add_argument(
        '-M', '--modinit_func',
        help=('C extension module PyMODINIT_FUNC function, or first C source PyInit_{filename} without '
              'extension if not given.'))
    subparser.add_argument(
        '-o', '--output',
        help=('Output executable'), default='./pyfuzzer')
    subparser.add_argument(
        '-F', '--fuzzer-only', action='store_true',
        help=('Build without print'))
    subparser.add_argument('csources', nargs='+', help='C extension source files.')
    subparser.set_defaults(func=do_build)

    # The print_coverage subparser.
    subparser = subparsers.add_parser('print_coverage',
                                      description='Print code coverage.')
    subparser.add_argument('bin', nargs='?', help='fuzzer binary', default='./pyfuzzer')
    subparser.set_defaults(func=do_print_coverage)

    # The print_corpus subparser.
    subparser = subparsers.add_parser(
        'print_corpus',
        description=('Print corpus units as Python functions with arguments and '
                     'return value or exception.'))
    subparser.add_argument('bin_print', nargs='?', help='fuzzer print binary', default='./pyfuzzer_print')
    subparser.add_argument('units',
                           nargs='*',
                           help='Units to print, or whole corpus if none given.')
    subparser.set_defaults(func=do_print_corpus)

    # The print_crashes subparser.
    subparser = subparsers.add_parser('print_crashes',
                                      description='Print all crashes.')
    subparser.add_argument('bin_print', nargs='?', help='fuzzer print binary', default='./pyfuzzer_print')
    subparser.add_argument('units',
                           nargs='*',
                           help='Crashes to print, or all if none given.')
    subparser.set_defaults(func=do_print_crashes)

    # The clean subparser.
    subparser = subparsers.add_parser(
        'clean',
        description='Remove the corpus and all crashes to start over.')
    subparser.set_defaults(func=do_clean)

    args = parser.parse_args()

    if args.debug:
        args.func(args)
    else:
        try:
            args.func(args)
        except BaseException as e:
            sys.exit('error: ' + str(e))
