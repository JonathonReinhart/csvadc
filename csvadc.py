#!/usr/bin/env python3
from __future__ import print_function
from collections import defaultdict
import argparse
import csv
import re
import sys

INITIAL_DELAY = 9e-9
CLOCK_PERIOD = 10e-9

BITORDER_LSB_FIRST = 'lsb'
BITORDER_MSB_FIRST = 'msb'

def printerr(*args, **kwargs):
    kwargs['file'] = sys.stderr
    return print(*args, **kwargs)
    
DEBUG = False

def printdbg(*args, **kwargs):
    if DEBUG:
        printerr(*args, **kwargs)

def map_value(x, low, high):
    if x >= high: return True
    if x < low:   return False
    return None

def bits_to_int(bits, order):
    r = 0
    for n,b in enumerate(bits):
        if order == BITORDER_LSB_FIRST:
            pass
        elif order == BITORDER_MSB_FIRST:
            n = len(bits) - 1 - n
        else:
            raise Exception("Invalid bitorder")

        if b is None:
            return None
        assert isinstance(b, bool)
        r |= (b << n)
    return r


DEFAULT_LOW_THRESHOLD  = 0.2
DEFAULT_HIGH_THRESHOLD = 1.5

class BusHandler:
    # E.g. "v(data01)"
    busnode_pat = re.compile('v\((\w+?)(\d+)\)')

    def __init__(self, low=None, high=None):
        # Mapping of bus name => (mapping of column index => bit number)
        self.busses = defaultdict(dict)

        self.set_thresholds(low, high)

    def set_thresholds(self, low=None, high=None):
        self.low  = low  if (low  is not None) else DEFAULT_LOW_THRESHOLD
        self.high = high if (high is not None) else DEFAULT_HIGH_THRESHOLD

    @classmethod
    def infer(cls, header):
        bh = cls()
        for colnum,nodename in enumerate(header):
            m = cls.busnode_pat.match(nodename)
            if not m:
                continue
            bus_name = m.group(1)
            bus_bit = int(m.group(2))
            bh.busses[bus_name][colnum] = bus_bit
        return bh

    @classmethod
    def default_lsb_first(cls, length):
        bh = cls()
        bh.busses['(default)'] = {i:i for i in range(length)}
        return bh

    @classmethod
    def default_msb_first(cls, length):
        bh = cls()
        bh.busses['(default)'] = {i:length-1-i for i in range(length)}
        return bh


    def print(self, file=None):
        print("Busses:", file=file)
        for busname, bitmap in self.busses.items():
            print("  {}:".format(busname), file=file)
            for colnum, bit in bitmap.items():
                print("     col {} => bit {}".format(colnum, bit), file=file)

    def extract_vals(self, row):
        result = {}
        for busname, bitmap in self.busses.items():
            result[busname] = 0

            for colnum, bit in bitmap.items():
                analog = row[colnum]
                digital = map_value(analog, self.low, self.high)

                if digital is None:
                    result[busname] = None
                    break

                result[busname] |= digital << bit


        return result

def peekline(f):
    pos = f.tell()
    try:
        return f.readline()
    finally:
        f.seek(pos)

def csv_peek(f, dialect=None):
    '''Return the first row of a CSV file'''
    pos = f.tell()
    try:
        return next(csv.reader(f, dialect))
    finally:
        f.seek(pos)


def parse_args():
    global DEBUG
    
    ap = argparse.ArgumentParser(
            formatter_class = argparse.ArgumentDefaultsHelpFormatter,
            )
    ap.add_argument('input', type=argparse.FileType('r'))

    ap.add_argument('--low', type=float, default=0.2,
        help='Logic low threshold; values below this voltage considered logic "0"')
    ap.add_argument('--high', type=float, default=1.5,
        help='Logic high threshold; values above this voltage considered logic "1"')

    ap.add_argument('--order', 
        choices=[BITORDER_LSB_FIRST, BITORDER_MSB_FIRST],
        help='Bit order (first) (default: lsb)')
    ap.add_argument('--skip', type=int, default=0,
        help='Number of lines to skip (after header, if present)')
    ap.add_argument('--format', choices=('dec', 'hex', 'bin'), default='dec')
    ap.add_argument('--debug', action='store_true')

    args = ap.parse_args()
    if args.debug:
        DEBUG = True

    if args.low >= args.high:
        ap.error("--low ({}) cannot be >= --high ({})".format(args.low, args.high))

    return args
    
def format_val(val, fmt, width):
    if fmt == 'dec':
        return '{}'.format(val)
    if fmt == 'hex':
        hexwidth = ((width-1) // 4) + 1
        return '0x{val:0{width}X}'.format(val=val, width=hexwidth)
    if fmt == 'bin':
        return '0b{val:0{width}b}'.format(val=val, width=width)

def main():
    args = parse_args()
    f = args.input
    
    # Sniff out the CSV format
    sniffer = csv.Sniffer()
    sample = peekline(f)
    dialect = sniffer.sniff(sample)
    has_header = sniffer.has_header(sample)
    printdbg("Has header:", has_header)

    num_cols = sum(bool(x) for x in csv_peek(f, dialect))

    r = csv.reader(f, dialect)
    if has_header:
        header = next(r)
        busses = BusHandler.infer(header)

        if args.order:
            printerr("WARNING: --order ignored when busses inferred from CSV header")

        # Determine column indices of non-bus columns (e.g. "time")
        bus_cols = set()
        for bus_name, bus in busses.busses.items():
            bus_cols.update(bus.keys())
        non_bus_cols = set(range(num_cols))- bus_cols

        # Create mapping of {name => column} for non-bus columns
        non_bus_cols = {header[i]:i for i in non_bus_cols}

    else:
        num_bits = num_cols
        if args.order in (None, BITORDER_LSB_FIRST):
            busses =  BusHandler.default_lsb_first(num_bits)
        elif args.order == BITORDER_MSB_FIRST:
            busses =  BusHandler.default_msb_first(num_bits)
        else:
            raise Exception("Invalid bitorder")

    busses.set_thresholds(low=args.low, high=args.high)
    if DEBUG:
        busses.print(file=sys.stderr)

    for _ in range(args.skip):
        next(r)


    next_sample_time = INITIAL_DELAY
    num_correct = 0

    for record in r:
        # Convert to float and discard empty columns
        record = [float(x) for x in record if len(x)]
        
        # Skip empty lines
        if not record: continue

        # Time to sample?
        t = record[non_bus_cols['time']]
        if t < next_sample_time:
            continue
        next_sample_time += CLOCK_PERIOD

        # Show non-bus values
        for name, col in non_bus_cols.items():
            val = record[col]
            if name == 'time':
                val = '{:.02f} ns  '.format(val * 1000 * 1000 * 1000)
            print('{}={} '.format(name, val), end='')

        # Extract bus values
        bus_vals = busses.extract_vals(record)
        for bus_name, val in bus_vals.items():
            bus_width = max(busses.busses[bus_name].values())+1
            print('{}={} '.format(bus_name, format_val(val, args.format, bus_width)), end='')


        m = bus_vals['m']
        n = bus_vals['n']
        p = bus_vals['p']

        if (m * n == p):
            num_correct += 1
            print('     ✔️ {}'.format(num_correct), end='')

        print()

    print("Num correct: {}".format(num_correct))

if __name__ == '__main__':
    main()
