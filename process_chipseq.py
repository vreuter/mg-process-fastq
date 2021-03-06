#!/usr/bin/python

"""
.. Copyright 2017 EMBL-European Bioinformatics Institute
 
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

import argparse, urllib2, gzip, shutil, shlex, subprocess, os.path, json

from .. import Tool, Workflow, Metadata

from common import common
from dmp import dmp

import tool

import os

try
    from pycompss.api.parameter import FILE_IN, FILE_OUT
    from pycompss.api.task import task
    from pycompss.api.constraint import constraint
except ImportError :
    print "[Warning] Cannot import \"pycompss\" API packages."
    print "          Using mock decorators."
    
    from dummy_pycompss import *

try :
    import pysam
except ImportError :
    print "[Error] Cannot import \"pysam\" package. Have you installed it?"
    exit(-1)

# ------------------------------------------------------------------------------

class process_chipseq(Workflow):
    """
    Functions for processing Chip-seq FastQ files. Files are the aligned,
    filtered and analysed for peak calling
    """
    
    def run(self, file_ids, metadata):
        """
        Main run function for processing ChIP-seq FastQ data. Pipeline aligns
        the FASTQ files to the genome using BWA. MACS 2 is then used for peak
        calling.
        
        Parameters
        ----------
        files_ids : list
            List of file locations
        metadata : list
        
        Returns
        -------
        outputfiles : list
            List of locations for the output bam, bed and tsv files
        """
        
        # TODO - Handle multiple file and background files
        genome_fa = file_ids[0]
        file_loc = file_ids[1]
        file_bgd_loc = file_ids[2]
        
        cf = common()
        
        out_bam = file_loc.replace('.fastq', '.bam')
        
        bwa = tool.bwaAlignerTool(self.configuration)
        out_bam = bwa.run((genome_fa, file_loc), ())
        #cf.bwa_align_reads(genome_fa, file_loc)
        out_bam, out_bam_meta = file_loc.replace('.fastq', '.bam')
        
        #cf.bwa_align_reads(genome_fa, file_bgd_loc)
        out_bgd_bam = file_bgd_loc.replace('.fastq', '.bam')
        out_bgd_bam, out_bgd_bam_meta = bwa.run((genome_fa, file_bgd_loc), ())
        
        # TODO - Multiple files need merging into a single bam file
        
        # Filter the bams
        b3f = tool.biobambam(self.configuration)
        b3f_file_out = b3f.run((out_bam[0]), ())
        b3f_file_bgd_out = b3f.run((out_bgd_bam[0]), ())
        
        # MACS2 to call peaks
        macs2 = tool.macs2(self.configuration)
        peak_bed, summits_bed, narrowPeak, broadPeak, gappedPeak = macs2.run((b3f_file_out,  b3f_file_bgd_out), ())
        
        return (b3f_file_out, b3f_file_bgd_out, peak_bed, summits_bed, narrowPeak, broadPeak, gappedPeak)

# ------------------------------------------------------------------------------
    
if __name__ == "__main__":
    import sys
    import os
    
    # Set up the command line parameters
    parser = argparse.ArgumentParser(description="ChIP-seq peak calling")
    parser.add_argument("--species", help="Species (homo_sapiens)")
    parser.add_argument("--genome", help="Genome FASTA file")
    parser.add_argument("--file", help="Project ID of the dataset")
    parser.add_argument("--bgd_file", help="Project ID of the dataset")
    
    # Get the matching parameters from the command line
    args = parser.parse_args()
    
    species     = args.species
    genome_fa   = args.genome
    file_loc    = args.data_dir
    file_bg_loc = args.tmp_dir
    
    pcs = process_chipseq()
    cf = common()
    
    #
    # MuG Tool Steps
    # --------------
    # 
    # 1. Create data files
    
    # Get the assembly
    #genome_fa = cf.getGenomeFromENA(data_dir, species, assembly, False)
    
    #2. Register the data with the DMP
    from dmp import dmp
    
    da = dmp()
    
    print da.get_files_by_user("test")
    
    genome_file = da.set_file("test", genome_fa, "fasta", "Assembly", 9606, None)
    file_in = da.set_file("test", file_loc, "fasta", "ChIP-seq", 9606, None)
    file_bg_in = da.set_file("test", file_bg_loc, "fasta", "ChIP-seq", 9606, None)
    
    print da.get_files_by_user("test")
    
    # 3. Instantiate and launch the App
    from basic_modules import WorkflowApp
    app = WorkflowApp()
    results = app.launch(process_chipseq, [genome_file, file_in, file_bg_in], {})
    
    print da.get_files_by_user("test")
    
