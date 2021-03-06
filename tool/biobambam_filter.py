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

import os

from pycompss.api.parameter import FILE_IN, FILE_OUT
from pycompss.api.task import task

from basic_modules.metadata import Metadata
from basic_modules.tool import Tool

from .. import common

# ------------------------------------------------------------------------------

class biobambam(Tool):
    """
    Tool to sort and filter bam files
    """
    
    @task(bam_file_in = FILE_IN, bam_file_out = FILE_OUT, tmp_dir = IN)
    def biobambam_filter_alignments(self, bam_file_in, tmp_dir):
        """
        Sorts and filters the bam file.
        
        It is important that all duplicate alignments have been removed. This
        can be run as an intermediate step, but should always be run as a check
        to ensure that the files are sorted and duplicates have been removed.
        
        Parameters
        ----------
        bam_file_in : str
            Location of the input bam file
        tmp_dir : str
            Tmp location for intermediate files during the sorting
        
        Returns
        -------
        bam_file_out : str
            Location of the output bam file
        """
        command_line = 'bamsormadup --tmpfile=' + tmp_dir
        args = shlex.split(command_line)
        with open(bam_file_in, "r") as f_in:
            with open(bam_file_out, "w") as f_out:
                p = subprocess.Popen(args, stdin=f_in, stdout=f_out)
                p.wait()
        
        return True
    
    
    def run(self, input_files, metadata):
        """
        Standard function to call a task
        """
        output_file = input_files[0].replace('.bam', '.filtered.bam')
        
        # handle error
        if not self.biobambam_filter_alignments(input_files[0], output_file):
            output_metadata.set_exception(
                Exception(
                    "biobambamTool: Could not process files {}, {}.".format(*input_files)))
            output_file = None
output_file = None
        return ([output_file], [output_metadata])

# ------------------------------------------------------------------------------
