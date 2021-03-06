#!/usr/bin/env python
# -*- coding: utf-8 -*-#
#
#
# Copyright (C) 2015, S3IT, University of Zurich. All rights reserved.
#
#
# This program is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation; either version 2 of the License, or (at your
# option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place, Suite 330, Boston, MA 02111-1307 USA

__docformat__ = 'reStructuredText'
__author__ = 'Antonio Messina <antonio.s.messina@gmail.com>'

from cStringIO import StringIO
from collections import defaultdict
from matplotlib import colors as mplcolors
from matplotlib import pylab as plt
from matplotlib.dates import DateFormatter

import argparse
import csv
import glob
import gzip
import math
import os
import pandas as pd
import re
import subprocess
import sys

# re_host = re.compile('(.*/)?fio-test(-[0-9\.]*)?.(?P<hostname>(osd|node|vhp)-[kl][0-9]-(01-)?[0-9]+).*')
re_collectl = re.compile('fio-test.(p:(?P<pool>[^.]+).)?'
                        'bs:(?P<bs>[0-9]+[a-z]).'
                        'iodepth:(?P<iodepth>[0-9]+).'
                        '(?P<test>read|randread|write|randwrite).'
                         '(?P<cache>cache|nocache).collectl[.-]*(?P<hostname>(osd|node|vhp)-[kl][0-9]-(01-)?[0-9]+).*')

DATASETS = {
    # name: {'opts': <collectl options>,
    #        'ds': <pandas dataset>,
    #        'ignore': [<list of regexp of column names to ignore>],
    #        }
    # name will be used as extension for the plot.
    'cpu': {'opts': 'C',
            'ds': None,
            'ignore': [r'\[CPU:[0-9]+\](Nice|GuestN?|Steal)%'],
            'ext': 'cpu',
            },
    'cpuaggr': {'opts': 'c',
            'ds': None,
            'ignore': [r'\[CPU\](Soft|Steal|Idle|Nice)%'],
            'ext': 'tab',
            },
    'net': {'opts': 'N',
            'ds': None,
            'ignore': [r'\[NET:(eth|bond).*'],
            'ext': 'net',
        },
    'disk': {'opts': 'D',
            'ds': None,
            'ignore': [r'\[DSK:dm.*'],
            'ext': 'dsk',
        },
}

def strtok(s):
    if s[-1] == 'k':
        return int(s[:-1])
    elif s[-1] == 'm':
        return int(s[:-1])*1024

def parse_file(fname):
    fmatch = re_collectl.search(fname)
    if not fmatch:
        print("Ignoring file %s as it doesn't match regexp %s" % (
            fname, re_collectl.pattern))
        return None
    print("Parsing file %s" % fname)
    # out = StringIO(subprocess.check_output(
    #     ['collectl',
    #      '--sep', ',',           # comma separator
    #      '-P',                   # plot
    #      '-s', dataset['opts'],  # What to plot
    #      '-p', fname,            # source file
    #      '--hr', '0'],           # Header on 1st row only.
    # ))
    # ds = pd.read_csv(out, parse_dates=[[0,1]])
    try:
        with gzip.open(fname, 'r') as input:
            out = StringIO(input.read())
    except Exception as ex:
        print("Skipping file %s because of error %s" % (fname,ex))
        return
    try:
        ds = pd.read_csv(out, parse_dates=[[0,1]], skiprows=15)
    except Exception as ex:
        print("Skipping file %s because of error %s" % (fname,ex))
        return

    # Fix column names
    ds = ds.rename(columns={'#Date_Time': 'DateTime'}, copy=False)

    # Add extra fields
    ds['hostname'] = fmatch.group('hostname')
    ds['pool'] = fmatch.group('pool')
    ds['bs'] = strtok(fmatch.group('bs'))
    ds['iodepth'] = fmatch.group('iodepth')
    ds['test'] = fmatch.group('test')
    return ds

def parse_directory(path, dataset, dsname):
    """Walk into directory `path` and look for collectl `*.raw.gz`
    files. Then, converts them by calling collectl -p -P and returns a
    pandas.DataSet.

    """
    for root, dirs, files in os.walk(path):
        for fname in files:
            if not fname.endswith(dataset['ext'] + '.gz'):
                print("Skipping file %s as it doesn't end in %s" % (
                    fname, dataset['ext'] + '.gz'))
                continue
            path = os.path.join(root, fname)
            ds = parse_file(path)
            if ds is None:
                continue
            for pattern in dataset['ignore']:
                for col in ds.columns:
                    if re.match(pattern, col):
                        del ds[col]
            if dataset['ds'] is not None:
                dataset['ds'] = pd.concat((dataset['ds'], ds))
            else:
                dataset['ds'] = ds
             
    
# def plot_data(columns, plottype, labelfmt):
#     # cm = plt.get_cmap('Set3')
#     cm = plt.get_cmap('jet')
#     cmnorm = mplcolors.Normalize(vmin=0,vmax=len(columns))
#     maxhosts = max(len(v.keys()) for v in tests.values())
#     yplots = int(math.sqrt(maxhosts))
#     xplots = int(math.ceil(float(maxhosts)/yplots))
#     print("%d x %d" % (xplots, yplots))
#     for test in tests.keys():
#         print("Processing test %s, type %s" % ((test,), plottype))
#         pool, bs, iodepth, rw = test
#         plotfname = '%s.pool=%s.bs=%s.io=%d.%s.svg' % (plottype, pool, bs, iodepth, rw)

#         fig, axes = plt.subplots(xplots, yplots, sharex='all', sharey='all')
#         for n, (host, datasets) in enumerate(tests[test].items()):
#             for data in datasets:
#                 if not set(columns).issubset(data.columns):
#                     continue
#                 data['time'] = data.Date_Time.apply(lambda x: x.time())
#                 x = (n % xplots)
#                 y = (n / xplots)
#                 ax = axes[x, y]
#                 ax.set_title('%s Usage for host %s' % (plottype, host))
#                 #data.plot(data.Date_Time, cpucols_pct, lw=2, colormap='jet', ax=ax, rot=90)
#                 for idx, col in enumerate(columns):
#                     ax.plot(data.time, data[col], label=labelfmt(col), color=cm(cmnorm(idx)))
#                 if n == 0:
#                     ax.legend(loc='upper left')
#         fig.autofmt_xdate()
#         fig.set_size_inches(14*3, 10*3)

#         plt.savefig(plotfname)
#         plt.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser('parse collectl output files and produce plots')
    parser.add_argument("dirs", nargs='+', help='Directories containing collectl RAW files.')
    parser.add_argument('-o', '--output', default='collectl', help='Base name of csv file.')

    cfg = parser.parse_args()

    # * Define the datasets to be used. Dataset will be empty, and
    #   created the first time an host file is parsed.
    # * scan the directories, and for each .raw.gz file:
    #   - for each type, run collectl to get the requested data
    #   - parse the output file
    #   - create a dataset and add it to the correct main dataset
    # * save the datasets
    for name, dataset in DATASETS.items():
        print("PARSING dataset of type %s" % name)
        for path in cfg.dirs:
            parse_directory(path, dataset, name)

        if dataset['ds'] is not None:
            print("Saving dataset for %s" % name)
            dataset['ds'].to_csv('%s.%s.csv' % (cfg.output, name), index=False)
            # Try to free some memory
            dataset['ds'] = None
