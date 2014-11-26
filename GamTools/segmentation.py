import numpy as np
import pandas as pd
import itertools
import os
from .cosegregation import Dprime

class InvalidChromError(Exception):
    """Exception to be raised when an invalid chromosome is specified"""
    pass

def open_segmentation(path_or_buffer):

    return pd.read_csv(path_or_buffer, 
                       index_col=[0,1,2], 
                       delim_whitespace=True)

def cosegregation_frequency(samples):
    """Take a table of n columns and return the co-segregation frequencies"""

    if samples.shape[0] == 2:
        return fast_cosegregation_frequency(samples)

    counts_shape = (2,) * samples.shape[0] 

    counts = np.zeros(counts_shape)

    for s in samples.T:

        counts[tuple(s)] += 1

    return counts


def fast_cosegregation_frequency(samples):
    """Take a table of 2 columns and return the co-segregation frequencies"""

    coseg = np.product(samples, axis=0).sum()
    marga, margb = np.sum(samples, axis=1)

    return np.array([[len(samples[0]) - marga - margb + coseg,
                      margb - coseg],[
                      marga - coseg, 
                      coseg]])


def get_index_combinations(regions):

    indexes = []
    start = 0

    assert len(regions) > 1

    for region in regions:

        indexes.append(range(start, start + len(region)))
        start = max(indexes[-1]) + 1

    return itertools.product(*indexes)

def get_cosegregation_freqs(*regions):

    if len(regions) == 1:

        regions = regions * 2

    combinations = get_index_combinations(regions)

    full_data = np.concatenate(regions, axis=0)
    
    def get_frequency(indices):

        return cosegregation_frequency(full_data[indices, :])

    result = map(get_frequency, combinations)

    result_shape = tuple([ len(region) for region in regions ]) + (2, ) * len(regions)

    freqs = np.array(result).reshape(result_shape)

    return freqs


def map_freqs(func, fqs):
    old_shape = fqs.shape
    half_point = len(old_shape) / 2
    flat_shape = tuple([ np.prod(old_shape[:half_point]) ]) + old_shape[half_point:]
    return np.array(map(func, fqs.reshape(flat_shape))).reshape(old_shape[:half_point])


def index_from_interval(segmentation_data, interval):

    chrom, start, stop = interval

    if not start < stop:
        raise ValueError('Interval start {0} larger than interval end {1}'.format(*interval))

    window_in_region = np.logical_and(
                            np.logical_and(
                                segmentation_data.index.get_level_values('stop') > start,
                                segmentation_data.index.get_level_values('start') < stop),
                                segmentation_data.index.get_level_values('chrom') == chrom)

    covered_windows = np.nonzero(window_in_region)[0]

    if not len(covered_windows):
        if not chrom in segmentation_data.index.levels[0]:
            raise InvalidChromError('{0} not found in the list of windows'.format(chrom))

    start_index = covered_windows[0]
    stop_index = covered_windows[-1] + 1

    return start_index, stop_index


def parse_location_string(loc_string):

    chrom_fields = loc_string.split(':')

    chrom = chrom_fields[0]

    if len(chrom_fields) == 1:

        start, stop = 0, np.Inf

    else:

        pos_fields = chrom_fields[1].split('-')

        start, stop = map(int, pos_fields)

    return chrom, start, stop


def index_from_location_string(segmentation_data, loc_string):

    interval = parse_location_string(loc_string)

    return index_from_interval(segmentation_data, interval)


def region_from_location_string(segmentation_data, loc_string):

    ix_start, ix_stop = index_from_location_string(segmentation_data, loc_string)

    return segmentation_data.iloc[ix_start:ix_stop,]


def get_matrix(segmentation_data, *location_strings, **kwargs):

    def get_region(loc_string):

        return region_from_location_string(segmentation_data, loc_string)

    regions = map(get_region, location_strings)

    return get_matrix_from_regions(*regions, **kwargs)


def get_matrix_from_regions(*regions, **kwargs):

    defaults = {'method' : Dprime,
               }

    defaults.update(kwargs)
    
    method = defaults['method']

    freqs = get_cosegregation_freqs(*regions)

    matrix = map_freqs(method, freqs)

    return matrix


def get_marginals(region):
    return region.sum(axis=1).astype(float) / region.count(axis=1).astype(float)


def map_sample_name_to_column(segmentation_data):

    name_mapping = { }

    for c in segmentation_data.columns:

        name_mapping[os.path.basename(c).split('.')[0]] = c  

    return name_mapping

class GamSegmentationFile(object):
    """Panel for displaying a continuous signal (e.g. ChIP-seq) across a genomic region"""
    def __init__(self, segmentation_path, method=Dprime):
        super(GamSegmentationFile, self).__init__()

        self.data = open_segmentation(segmentation_path)
        self.method = method
    
    def interactions(self, feature):
        
        interval = feature.chrom, feature.start, feature.stop
        ix_start, ix_stop = index_from_interval(self.data, interval)
        region = self.data.iloc[ix_start:ix_stop,]
                
        return get_matrix_from_regions(region, method=self.method), feature

