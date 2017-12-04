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




class BusHandler:
    # E.g. "v(data0)"
    busnode_pat = re.compile('v\((\w+)(\d+)\)')

    def __init__(self, low, high):
        # Mapping of bus name => (mapping of column index => bit number)
        self.busses = defaultdict(dict)

        self.low = low
        self.high = high

    def infer(self, header):
        for colnum,nodename in enumerate(header):
            m = self.busnode_pat.match(nodename)
            bus_name = m.group(1)
            bus_bit = int(m.group(2))
            self.busses[bus_name][colnum] = bus_bit

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



def parse_args():
    ap = argparse.ArgumentParser(
            formatter_class = argparse.ArgumentDefaultsHelpFormatter,
            )
    ap.add_argument('input', type=argparse.FileType('r'))

    ap.add_argument('--low', type=float, default=0.2,
        help='Logic low threshold; values below this voltage considered logic "0"')
    ap.add_argument('--high', type=float, default=1.5,
        help='Logic high threshold; values above this voltage considered logic "1"')

    ap.add_argument('--order', default=BITORDER_LSB_FIRST,
        choices=[BITORDER_LSB_FIRST, BITORDER_MSB_FIRST],
        help='Bit order (first)')

    args = ap.parse_args()

    if args.low >= args.high:
        ap.error("--low ({}) cannot be >= --high ({})".format(args.low, args.high))

    return args

def main():
    args = parse_args()

    r = csv.reader(args.input)

    header = next(r)
    busses = BusHandler(low=args.low, high=args.high)
    busses.infer(header)
    busses.print(file=sys.stderr)


    for record in r:
        record = [float(x) for x in record]
        #print("  input", record)

        # Extract bus values
        bus_vals = busses.extract_vals(record)
        print(bus_vals)

if __name__ == '__main__':
    main()
