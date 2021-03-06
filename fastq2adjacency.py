"""
Copyright 2017 EMBL-European Bioinformatics Institute

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

import os, os.path, shutil, urllib2

from pycompss.api.task import task
from pycompss.api.constraint import constraint

import pytadbit
from pytadbit.mapping               import get_intersection
from pytadbit.mapping.filter        import apply_filter
from pytadbit.mapping.filter        import filter_reads
from pytadbit.mapping.mapper        import full_mapping
from pytadbit.parsers.map_parser    import parse_map
from pytadbit.parsers.hic_parser    import load_hic_data_from_reads
from pytadbit.parsers.hic_parser    import read_matrix
from pytadbit.parsers.genome_parser import parse_fasta
from pytadbit.utils.file_handling   import mkdir
import numpy as np
import h5py


class fastq2adjacency:
    """
    These are the parts of the TADbit library that are required for processing
    FASTQ data. They have been packaged into chunks that can be easily handled
    by the COMPS infrastructure.
    
    At the moment this assumes 1 SRA generates a single adjacency matrix. Often
    there are multiple SRA files that get merged for a final result. This needs
    to be integrated into this pipeline.
    """
    
    def __init__(self):
        """
        Initialise the module and 
        """
        #self.genome_accession = '' # GCA_000001405.22 - GRChg38, current
        self.species     = '' # 'homo_sapiens'
        self.assembly    = '' # 'GRCh38'
        self.dataset     = '' # 'GSE63525'
        self.sra_id      = '' # 'SRR1658632'
        self.library     = '' # 'HiC036'
        self.enzyme_name = '' # 'NcoI'
        self.resolution  = 1000000

        self.temp_root = '/' # '/<tmp_area>/'
        self.data_root = '/' # '/<data_dir>/'
        
        self.gem_file     = ''
        self.genome_file  = ''
        self.fastq_file_1  = ''
        self.fastq_file_2  = ''
        self.map_dir      = ''
        self.tmp_dir      = ''
        
        self.windows1 = ((1,25), (1,50), (1,75),(1,100))
        self.windows2 = ((101,125), (101,150), (101,175),(101,200))
        
        self.mapped_r1 = None
        self.mapped_r2 = None
        
        self.genome_seq = None
        
        self.hic_data = None

    
    def set_params(self, species, assembly, dataset, sra_id, library, enzyme_name, resolution, tmp_dir, data_dir, expt_name = None, same_fastq=True, windows1=None, windows2=None):
        #self.genome_accession = genome_accession
        self.species     = species
        self.assembly    = assembly
        self.dataset     = dataset
        self.sra_id      = sra_id
        self.library     = library
        self.enzyme_name = enzyme_name
        self.resolution  = resolution

        self.temp_root = tmp_dir
        self.data_root = data_dir
        
        #self.gem_file = self.data_root + self.genome_accession + "/" + self.genome_accession + ".gem"
        #self.genome_file = self.data_root + self.genome_accession + "/chroms/" + self.genome_accession + ".fa"
        self.gem_file = self.data_root + self.species + '_' + self.assembly + '/' + self.species + '.' + self.assembly + ".gem"
        self.genome_file = self.data_root + self.species + '_' + self.assembly + '/' + self.species + '.' + self.assembly + ".fa"
        
        if expt_name != None:
            self.expt_name = expt_name + '/'
        else:
            self.expt_name = ''
        
        self.library_dir = self.data_root + self.expt_name + self.dataset + '/' + self.library + '/'
        if same_fastq == True:
            self.fastq_file_1  = self.library_dir + self.sra_id + '.fastq'
            self.fastq_file_2  = self.library_dir + self.sra_id + '.fastq'
        else:
            self.fastq_file_1  = self.library_dir + self.sra_id + '_1.fastq'
            self.fastq_file_2  = self.library_dir + self.sra_id + '_2.fastq'
        
        self.map_dir     = self.library_dir + '01_it-mapped_read'
        self.tmp_dir     = self.temp_root + self.expt_name + self.dataset + '/' + self.library
        self.parsed_reads_dir = self.tmp_dir + '/parsed_reads'
        
        try:
            os.makedirs(self.map_dir)
        except:
            pass
        
        try:
            os.makedirs(self.tmp_dir)
        except:
            pass
        
        try:
            os.makedirs(self.parsed_reads_dir)
        except:
            pass
        
        if windows1 != None:
            self.windows1 = windows1
        if windows2 != None:
            self.windows2 = windows2
    
    
    def mapWindows(self, side=1):
        """
        Map the reads to the genome
        """
        
        if side == 1:
            mapped_r1 = full_mapping(self.gem_file, self.fastq_file_1, self.map_dir + str(1), windows=self.windows1, frag_map=False, nthreads=8, clean=True, temp_dir=self.tmp_dir)
        elif side == 2:
            mapped_r2 = full_mapping(self.gem_file, self.fastq_file_2, self.map_dir + str(2), windows=self.windows2, frag_map=False, nthreads=8, clean=True, temp_dir=self.tmp_dir)
    
    
    def getMappedWindows(self):
        """
        Populate the mapped_rN values so that it is not reliant on a single
        process
        """
        
        mapped_r1 = []
        mapped_r2 = []

        r1_dir = self.map_dir + str(1)
        r2_dir = self.map_dir + str(2)

        for mapped in os.listdir(r1_dir):
            mapped_r1.append(os.path.join(r1_dir, mapped))
        for mapped in os.listdir(r2_dir):
            mapped_r2.append(os.path.join(r2_dir, mapped))
        
        return {'mapped_r1': mapped_r1, 'mapped_r2': mapped_r2}
    
    
    def parseGenomeSeq(self):
        """
        Loads the genome
        """
        self.genome_seq = parse_fasta(self.genome_file)
    
    
    @constraint(ProcessorCoreCount=8)
    @task(num_cpus = IN)
    def parseMaps(self, num_cpus=8):
        """
        Merge the 2 read maps together 
        Requires 8 CPU
        """
        # new file with info of each "read1" and its placement with respect to RE sites
        reads1 = self.parsed_reads_dir + '/read1.tsv'
        # new file with info of each "read2" and its placement with respect to RE sites
        reads2 = self.parsed_reads_dir + '/read2.tsv'
        
        mapped_rN = self.getMappedWindows()

        print 'Parse MAP files...'
        parse_map(mapped_rN["mapped_r1"], mapped_rN["mapped_r2"], out_file1=reads1, out_file2=reads2, genome_seq=self.genome_seq, re_name=self.enzyme_name, verbose=True, ncpus=num_cpus)
    
    def mergeMaps(self):
        """
        Merging mapped "read1" and "read2"
        """
        # Output file
        reads  = self.parsed_reads_dir + '/both_map.tsv'
        # new file with info of each "read1" and its placement with respect to RE sites
        reads1 = self.parsed_reads_dir + '/read1.tsv'
        # new file with info of each "read2" and its placement with respect to RE sites
        reads2 = self.parsed_reads_dir + '/read2.tsv'
        get_intersection(reads1, reads2, reads, verbose=True)
    
    
    @constraint(ProcessorCoreCount=4)
    @task(conservative = IN)
    def filterReads(self, conservative = True):
        """
        Filter the reads to remove duplicates and experimental abnormalities
        Requires 4 CPU
        """
        
        reads      = self.parsed_reads_dir + '/both_map.tsv'
        filt_reads = self.parsed_reads_dir + '/filtered_map.tsv'
        
        masked = filter_reads(reads, max_molecule_length=610, min_dist_to_re=915, over_represented=0.005, max_frag_size=100000, min_frag_size=100, re_proximity=4)

        if conservative == True:
            # Ignore filter 5 (based on docs) as not very helpful
            apply_filter(reads, filt_reads, masked, filters=[1,2,3,4,6,7,8,9,10])
        else:
            # Less conservative option
            apply_filter(reads, filt_reads, masked, filters=[1,2,3,9,10])
    
    #def merge_adjacency_data(self, adjacency_matrixes):
    #    """
    #    TODO: Work on the merging and finalise the procedure.
    #    
    #    The recommended route is to merge the normalised data is to sum the
    #    normalised values from previous steps. This should be the final step of
    #    the initial phase for main function should have finished by normalising
    #    each of the individual adjacency files.
    #    """
    #    exptName = self.library + "_" + str(self.resolution)
    #    
    #    merged_matrix = Chromosome(name=exptName, centromere_search=True)
    #    merged_matrix.add_experiment(exptName, resolution=self.resolution)
    #    merged_exp = merged_matrix.experiment[exptName]
    #    print adjacency_data
    #    
    #    for m in adjacency_matrixes:
    #        new_chrom = Chromosome(name=exptName, centromere_search=True)
    #        new_chrom.add_experiment(exptName, hic_data=m, resolution=self.resolution)
    #        merged_exp = merged_exp + new_chrom.experiments[exptName]
    
    
    @constraint(ProcessorCoreCount=8, MemoryPhysicalSize=80)
    @task(chrom = IN)
    def generate_tads(self, chrom):
        """
        Uses TADbit to generate the TAD borders based on the computed hic_data
        """
        from pytadbit import Chromosome
        
        exptName = self.library + "_" + str(self.resolution) + "_" + str(chrom) + "-" + str(chrom)
        fname = self.parsed_reads_dir + '/adjlist_map_' + str(chrom) + '-' + str(chrom) + '_' + str(self.resolution) + '.tsv'
        chr_hic_data = read_matrix(fname, resolution=int(self.resolution))
        
        my_chrom = Chromosome(name=exptName, centromere_search=True)
        my_chrom.add_experiment(exptName, hic_data=chr_hic_data, resolution=int(self.resolution))
        
        # Run core TADbit function to find TADs on each expt.
        # For the current dataset required 61GB of RAM
        my_chrom.find_tad(exptName, n_cpus=15)
        
        exp = my_chrom.experiments[exptName]
        tad_file = self.library_dir + exptName + '_tads.tsv'
        exp.write_tad_borders(savedata=tad_file)
    
    
    def load_hic_read_data(self):
        """
        Load the interactions into the HiC-Data data type
        
        This should be used as the primary way of loading the HiC-data as the 
        data is loaded in the right form for later functions. Options like the
        TAD calling also require non-normalised data.
        """
        filter_reads = self.parsed_reads_dir + '/filtered_map.tsv'
        
        print "\nfilter_reads: " + filter_reads
        self.hic_data = load_hic_data_from_reads(filter_reads, resolution=int(self.resolution))
    
    
    def load_hic_matrix_data(self, norm=True):
        """
        Load the interactions from Hi-C adjacency matrix into the HiC-Data data
        type
        """
        if norm == True:
            # Dump the data pre-normalized
            adj_list = self.parsed_reads_dir + '/adjlist_map.tsv'
        else:
            adj_list = self.parsed_reads_dir + '/adjlist_map_norm.tsv'
        
        self.hic_data = read_matrix(adj_list, resolution=self.resolution)
    
    
    def normalise_hic_data(self, iterations=0):
        """
        Normalise the Hi-C data
        Example has the iterations set to 9, but setting to 0 to match that
        done by Rao et al 2014
        """
        self.hic_data.normalize_hic(iterations=iterations, max_dev=0.1)
    
    
    def get_chromosomes(self):
        return self.hic_data.chromosomes.keys()
    
    
    def save_hic_split_data(self, normalized=False):
        """
        Saves the data from the filtering step split by "chrA x chrB" to allow
        for easy loading and TAD calling.
        """
        chroms = self.get_chromosomes()
        for chrA in range(len(chroms)):
            adj_list = self.parsed_reads_dir + '/adjlist_map_' + chroms[chrA] + '-' + chroms[chrA] + '_' + self.resolution + '.tsv'
            if normalized == True:
                adj_list = self.parsed_reads_dir + '/adjlist_map_' + chroms[chrA] + '-' + chroms[chrA] + '_' + self.resolution + '.norm.tsv'
            
            self.hic_data.write_matrix(adj_list, (chroms[chrA], chroms[chrA]), normalized=normalized)
        
    
    def save_hic_data(self, normalized=False):
        """
        Save the hic_data object to a file. This is saved as an NxN array with
        the values for all positions being set.
        """
        if normalized == False:
            # Dump the data pre-normalized
            adj_list = self.parsed_reads_dir + '/adjlist_map.tsv'
            self.hic_data.write_matrix(adj_list, normalized=False)
        else:
            adj_list = self.parsed_reads_dir + '/adjlist_map_norm.tsv'
            self.hic_data.write_matrix(adj_list, normalized=True)
    
    
    def save_hic_hdf5(self, normalized=False):
        """
        Save the hic_data object to HDF5 file. This is saved as an NxN array
        with the values for all positions being set.
        
        This needs to include attributes for the chromosomes for each resolution
         - See the mg-rest-adjacency hdf5_reader for further details about the
           requirement. This prevents the need for secondary storage details
           outside of the HDF5 file.
        """
        dSize = len(self.hic_data)
        d = np.zeros([dSize, dSize], dtype='int32')
        d += f2a.hic_data.get_matrix()
        
        filename = self.data_root + self.species + '_' + self.assembly + "_" + self.dataset + "_" + str(self.resolution) + ".hdf5"
        f = h5py.File(filename, "a")
        dset = f.create_dataset(str(self.resolution), (dSize, dSize), dtype='int32', chunks=True, compression="gzip")
        dset[0:dSize,0:dSize] += d
        f.close()
    
    
    def clean_up(self):
        """
        Clears up the tmp folders
        """
        os.chdir(self.temp_root)
        
        try:
            shutil.rmtree(self.expt_name)
        except:
            pass
        
        try:
            shutil.rmtree(self.dataset)
        except:
            pass
        
        

