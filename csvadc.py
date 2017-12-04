#!/usr/bin/env python3
from __future__ import print_function
import argparse
import csv

BITORDER_LSB_FIRST = 'lsb'
BITORDER_MSB_FIRST = 'msb'

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
    #print("Header:", header)

    for record in r:
        record = [float(x) for x in record]
        #print("  input", record)

        result = [map_value(x, args.low, args.high) for x in record]

        val = bits_to_int(result, args.order)
        #print("  result {}  =>  {}".format(result, val))
        print(val)

if __name__ == '__main__':
    main()
