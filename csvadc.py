#!/usr/bin/env python3
from __future__ import print_function
from collections import defaultdict
import argparse
import csv
import re
import sys

BITORDER_LSB_FIRST = 'lsb'
BITORDER_MSB_FIRST = 'msb'

def printerr(*args, **kwargs):
    kwargs['file'] = sys.stderr
    return print(*args, **kwargs)

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

def csv_peek(f):
    '''Return the first row of a CSV file'''
    pos = f.tell()
    try:
        return next(csv.reader(f))
    finally:
        f.seek(pos)


def parse_args():
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

    args = ap.parse_args()

    if args.low >= args.high:
        ap.error("--low ({}) cannot be >= --high ({})".format(args.low, args.high))

    return args

def main():
    args = parse_args()
    f = args.input
    
    # Sniff out the CSV format
    sniffer = csv.Sniffer()
    sample = peekline(f)
    dialect = sniffer.sniff(sample)
    printerr("Dialect:", dialect)
    has_header = sniffer.has_header(sample)
    printerr("Has header:", has_header)


    r = csv.reader(f)
    if has_header:
        header = next(r)
        busses = BusHandler.infer(header)

        if args.order:
            printerr("WARNING: --order ignored when busses inferred from CSV header")

    else:
        num_bits = len(csv_peek(f))

        if args.order in (None, BITORDER_LSB_FIRST):
            busses =  BusHandler.default_lsb_first(num_bits)
        elif args.order == BITORDER_MSB_FIRST:
            busses =  BusHandler.default_msb_first(num_bits)
        else:
            raise Exception("Invalid bitorder")

    busses.set_thresholds(low=args.low, high=args.high)
    busses.print(file=sys.stderr)


    for record in r:
        record = [float(x) for x in record]
        #print("  input", record)

        # Extract bus values
        bus_vals = busses.extract_vals(record)
        print(bus_vals)

if __name__ == '__main__':
    main()
