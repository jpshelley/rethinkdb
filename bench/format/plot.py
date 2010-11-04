import numpy as np
import matplotlib.pyplot as plt
import matplotlib.mlab as mlab
from mpl_toolkits.mplot3d import Axes3D
from matplotlib.collections import PolyCollection
from colors import *
import json
import time
from line import *
from statlib import stats

def cull_outliers(data, n_sigma):
    mean = stats.mean(map(lambda x: x, data))
    sigma  = stats.stdev(map(lambda x: x, data))
    return filter(lambda x: abs(x - mean) < n_sigma * sigma, data)

def clip(data, min, max):
    return map(lambda x: min<x<max, data)

def normalize(array):
    denom = max(map(lambda x: abs(x), array))
    if denom == 0:
        return array
    else:
        return map(lambda x: float(x) / denom, array)

class TimeSeries(list):
    def __init__(self, units):
        self.units = units

class default_empty_timeseries_dict(dict):
    units_line = line("([A-Za-z_]+)(\[[A-Za-z_]\]+)", [('key', 's'), ('units', 's')])
    def __getitem__(self, key):
        m = self.units_line.parse_line(key)
        if m:
            key = m['key']
            units = m['units']
        else:
            units = ''
        if key in self:
            return self.get(key)
        else:
            return TimeSeries(units)
    def copy(self):
        copy = default_empty_timeseries_dict()
        copy.update(self)
        return copy

class TimeSeriesCollection():
    def __init__(self):
        self.data = default_empty_timeseries_dict()

    def read(self, file_name):
        try:
            data = open(file_name).readlines()
            self.data = self.parse(data)
            self.process()
        except IOError:
            print 'Missing file: %s data from it will not be reported' % file_name
        return self #this just lets you do initialization in one line

    def copy(self):
        copy = self.__class__()
        copy.data = self.data.copy()
        return copy

    def __add__(self, other):
        res = self.copy()
        for val in other.data.iteritems():
            assert not val[0] in res.data
            res.data[val[0]] = val[1]
        return res

#limit the data to just the keys in keys
    def select(self, keys):
        copy = self.copy()
        for key in copy.data.keys():
            if not key in keys:
                copy.data.pop(key)

        return copy

    def drop(self, keys):
        copy = self.copy()
        for key in copy.data.keys():
            if key in keys:
                copy.data.pop(key)

        return copy

    def remap(self, orig_name, new_name):
        copy = self.drop(orig_name)
        copy.data[new_name] = self.data[orig_name]
        return copy

    def parse(self, data):
        pass

#do post processing things on the data (ratios and derivatives and stuff)
    def process(self):
        pass

    def json(self, out_fname, meta_data):
        top_level = {}
        top_level['date'] = time.asctime() 
        top_level['meta'] = meta_data
        top_level['data'] = {}
        top_level['data']['rethinkdb'] = {}
        for series in self.data.iteritems():
            top_level['data']['rethinkdb'][series[0]] = {}
            top_level['data']['rethinkdb'][series[0]]['data'] = map(lambda x: list(x), zip(range(len(series[1])), series[1]))
            top_level['data']['rethinkdb'][series[0]]['unit'] = series[1].units

        f = open(out_fname + '.js', 'w')
        print >>f, json.dumps(top_level)
        f.close()

    def histogram(self, out_fname):
        assert self.data

        fig = plt.figure()
        ax = fig.add_subplot(111)

        data = map(lambda x: x[1], self.data.iteritems())
        for series, color in zip(self.data.iteritems(), colors):
            ax.hist(cull_outliers(series[1], 1.3), 40, histtype='step', facecolor = color, alpha = .4, label = series[0])
            ax.set_xlabel(series[0])
            ax.set_ylabel('Count')
#ax.set_xlim(0, max(map(max, data)))
#ax.set_ylim(0, max(map(len, data)))
            ax.grid(True)
            plt.savefig(out_fname, dpi=300)

    def plot(self, out_fname, normalize = False):
        assert self.data
        fig = plt.figure()
        ax = fig.add_subplot(111)
        labels = []
        color_index = 0
        for series in self.data.iteritems():
            if normalize:
                data_to_use = normalize(series[1])
            else:
                data_to_use = series[1]
            labels.append((ax.plot(range(len(series[1])), data_to_use, colors[color_index]), series[0]))
            color_index += 1

        ax.set_xlabel('Time (seconds)')
        ax.set_xlim(0, len(self.data[self.data.keys()[0]]) - 1)
        if normalize:
            ax.set_ylim(0, 1.0)
        else:
            ax.set_ylim(0, max(self.data[self.data.keys()[0]]))
        ax.grid(True)
        plt.legend(tuple(map(lambda x: x[0], labels)), tuple(map(lambda x: x[1], labels)), loc=1)
        plt.savefig(out_fname, dpi=300)

    def stats(self):
        res = {}
        for val in self.data.iteritems():
            stat_report = {}
            stat_report['mean'] = stats.mean(map(lambda x: x, val[1]))
            stat_report['stdev'] = stats.stdev(map(lambda x: x, val[1]))
            res[val[0]] = stat_report

        return res

#function : (serieses)*len(arg_keys) -> series
#TODO this should return a copy with the changes
    def derive(self, name, arg_keys, function):
        args = []
        for key in arg_keys:
            assert key in self.data
            args.append(self.data[key])

        self.data[name] = function(tuple(args))
        return self

def multi_plot(timeseries, out_fname):
    fig = plt.figure()
    ax = fig.add_subplot(111)
    verts = []

    xs = range(min(map(lambda x: min(map(lambda y: len(y[1]), x.data.iteritems())), timeseries)))

    for z in range(len(timeseries)):
        for series in timeseries[z].data.iteritems():
            verts.append(zip(xs, series[1]))

    poly = PolyCollection(verts, facecolors = colors[0:len(verts)])
    poly.set_alpha(0.7)
    ax.add_collection3d(poly, range(len(timeseries)), zdir='y')

    ax.set_xlabel('X')
    ax.set_xlim3d(0, len(xs))
    ax.set_ylabel('Y')
    ax.set_ylim3d(-1, len(timeseries))
    ax.set_zlabel('Z')
    ax.set_zlim3d(0, max(map(lambda x: max(x), timeseries)))
    plt.savefig(out_fname, dpi=300)

#take discret derivative of a series (shortens series by 1)
def differentiate(series):
#series will be a tuple
    series = series[0]
    res = []
    for f_t, f_t_plus_one in zip(series[:len(series) - 1], series[1:]):
        res.append(f_t_plus_one - f_t)

    return res

def difference(serieses):
    assert serieses[0].units == serieses[1].units
    res = TimeSeries(serieses[0].units)
    for x,y in zip(serieses[0], serieses[1]):
        res.append(x - y)

    return res

class IOStat(TimeSeriesCollection):
    file_hdr_line   = line("Linux.*", [])
    avg_cpu_hdr_line= line("^avg-cpu:  %user   %nice %system %iowait  %steal   %idle$", [])
    avg_cpu_line    = line("^" + "\s+([\d\.]+)" * 6 + "$", [('user', 'f'), ('nice', 'f'), ('system', 'f'), ('iowait', 'f'),  ('steal', 'f'),   ('idle', 'f')])
    dev_hdr_line    = line("^Device:            tps   Blk_read/s   Blk_wrtn/s   Blk_read   Blk_wrtn$", [])
    dev_line        = line("^(\w+)\s+([\d\.]+)\s+([\d\.]+)\s+([\d\.]+)\s+(\d+)\s+(\d+)$", [('device', 's'), ('tps', 'f'), (' Blk_read', 'f'), (' Blk_wrtn', 'f'), (' Blk_read', 'd'), (' Blk_wrtn', 'd')])

    def parse(self, data):
        res = default_empty_timeseries_dict()
        data.reverse()
        m = until(self.file_hdr_line, data)
        assert m != False
        while True:
            m = until(self.avg_cpu_hdr_line, data)
            if m == False:
                break

            m = take(self.avg_cpu_line, data)
            assert m
            for val in m.iteritems():
                res['cpu_' + val[0]] += [val[1]]

            m = until(self.dev_hdr_line, data)
            assert m != False

            m = take_while([self.dev_line], data)
            for device in m:
                dev_name = device.pop('device')
                for val in device.iteritems():
                    res['dev:' + dev_name + '_' + val[0]] += [val[1]]

        return res

class VMStat(TimeSeriesCollection):
    file_hdr_line   = line("^procs -----------memory---------- ---swap-- -----io---- -system-- ----cpu----$", [])
    stats_hdr_line  = line("^ r  b   swpd   free   buff  cache   si   so    bi    bo   in   cs us sy id wa$", [])
    stats_line      = line("\s+(\d+)" * 16, [('r', 'd'),  ('b', 'd'),   ('swpd', 'd'),   ('free', 'd'),   ('buff', 'd'),  ('cache', 'd'),   ('si', 'd'),   ('so', 'd'),    ('bi', 'd'),    ('bo', 'd'),   ('in', 'd'),   ('cs', 'd'), ('us', 'd'), ('sy', 'd'), ('id', 'd'), ('wa', 'd')])

    def parse(self, data):
        res = default_empty_timeseries_dict()
        data.reverse()
        while True:
            m = until(self.file_hdr_line, data)
            if m == False:
                break
            m = take(self.stats_hdr_line, data)
            assert m != False
            m = take_while([self.stats_line], data)
            for stat_line in m:
                for val in stat_line.iteritems():
                    res[val[0]]+= [val[1]]
        return res

class Latency(TimeSeriesCollection):
    line = line("(\d+)\s+([\d.]+)\n", [('tick', 'd'), ('latency', 'f')])

    def parse(self, data):
        res = default_empty_timeseries_dict()
        for line in data:
            res['latency'] += [self.line.parse_line(line)['latency']]
        return res

class QPS(TimeSeriesCollection):
    line = line("(\d+)\s+([\d]+)\n", [('tick', 'd'), ('qps', 'f')])

    def parse(self, data):
        res = default_empty_timeseries_dict()
        for line in data:
            res['qps'] += [self.line.parse_line(line)['qps']]
        return res

class RDBStats(TimeSeriesCollection):
    int_line  = line("STAT\s+(\w+)\s+(\d+)[^\.](?:\s+\(average of \d+\))?", [('name', 's'), ('value', 'd')])
    flt_line  = line("STAT\s+(\w+)\s+([\d.]+)\s+\([\d/]+\)", [('name', 's'), ('value', 'f')])
    end_line  = line("END", [])
    
    def parse(self, data):
        res = default_empty_timeseries_dict()
        data.reverse()
        
        while True:
            m = take_while([self.int_line, self.flt_line], data)
            if not m:
                break
            for match in m:
                res[match['name']] += [match['value']]

            m = take(self.end_line, data)
            assert m != False

            if res:
                lens = map(lambda x: len(x[1]), res.iteritems())
                assert max(lens) == min(lens)
        return res

    def process(self):
        differences = [('io_reads_completed', 'io_reads_started'), 
                       ('io_writes_started', 'io_writes_completed'), 
                       ('transactions_started', 'transactions_ready'), 
                       ('transactions_ready', 'transactions_completed'),
                       ('bufs_acquired', 'bufs_ready'),
                       ('bufs_ready', 'bufs_released')]
        keys_to_drop = set()
        for dif in differences:
            self.derive(dif[0] + ' - ' + dif[1], dif, difference)
            keys_to_drop.add(dif[0])
            keys_to_drop.add(dif[1])
        self.drop(keys_to_drop)
