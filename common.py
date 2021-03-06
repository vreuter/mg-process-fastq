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

import argparse, urllib2, gzip, shutil, shlex, subprocess, os.path

from socket import error as SocketError
import errno

try :
    import pysam
except ImportError :
    print "[Error] Cannot import \"pysam\" package. Have you installed it?"
    exit(-1)

class common:
    """
    Functions for downloading and processing *-seq FastQ files. Functions
    provided allow for the downloading andindexing of the genome assemblies.
    """
    
    def __init__ (self):
        """
        Initialise the module
        """
        self.ready = ""
    
    
    def getGenomeFile(self, data_dir, species, assembly, index = True):
        """
        Function for downloading and extracting the DNA files from the ensembl
        FTP
        
        Parameters
        ----------
        
        
        
        Returns
        -------
        """
        
        file_name = data_dir + species + '_' + assembly + '/' + species + '.' + assembly + '.dna.toplevel.fa.gz'
        file_name_unzipped = file_name.replace('.fa.gz', '.fa')
        print file_name
        
        if os.path.isfile(file_name) == False:
            ftp_url = 'ftp://ftp.ensembl.org/pub/current_fasta/' + species.lower() + '/dna/' + species[0].upper() + species[1:] + '.' + assembly + '.dna.toplevel.fa.gz'
            
            self.download_file(file_name, ftp_url)
            
        if os.path.isfile(file_name_unzipped) == False:
            print "Unzipping"
            with gzip.open(file_name, 'rb') as f_in, open(file_name_unzipped, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        
        indexes = {}
        if index == True:
            indexes = self.run_indexers(file_name_unzipped)
        
        return {'zipped': file_name, 'unzipped': file_name_unzipped, 'index' : indexes}
    
    
    def getGenomeFromENA(self, data_dir, species, assembly, index = True):
        """
        Obtain the Assembly from the ENA. This means that it is possible to get
        the exact assembly matching that defined by the user.
        """
        
        file_name = data_dir + species + '_' + assembly + '/' + species + '.' + assembly + '.fa'
        
        if os.path.isfile(file_name) == False:
          ftp_list_url = 'ftp://ftp.ebi.ac.uk/pub/databases/ena/assembly/' + assembly[0:7] + '/' + assembly[0:10] + '/' + assembly + '_sequence_report.txt'
          res_list = urllib2.urlopen(ftp_list_url)
          table = res_list.read()
          table = table.split("\n")
          
          chr_list = []
          for row in table:
              col = row.split("\t")
              if len(col) > 5 and col[3] == 'assembled-molecule':
                  chr_list.append(col[0])
          
          ftp_url = 'http://www.ebi.ac.uk/ena/data/view/' + ','.join(chr_list) + '&display=fasta'
          self.download_file(file_name, ftp_url)
        
        indexes = {}
        if index == True:
            self.replaceENAHeader(file_name)
            indexes = self.run_indexers(file_name)
        
        return {'unzipped': file_name, 'index' : indexes}
    
    
    def replaceENAHeader(self, file_path):
        """
        The ENA header has pipes in the header as part of teh stable_id. This
        function removes the ENA stable_id and replaces it with the final
        section after splitting the stable ID on the pipe.
        """
        from tempfile import mkstemp
        from shutil import move
        from os import remove, close
        
        #Create temp file
        fh, abs_path = mkstemp()
        with open(abs_path,'w') as new_file:
            with open(file_path) as old_file:
                for line in old_file:
                    if line[0] == '>':
                        space_line = line.split(" ")
                        new_file.write(">" + space_line[0].split("|")[-1].replace(">", "") + " " + " ".join(space_line[1:]))
                    else:
                        new_file.write(line)
        close(fh)
        #Remove original file
        remove(file_path)
        #Move new file
        move(abs_path, file_path)
    
    
    def getcDNAFiles(self, data_dir, species, assembly, e_release):
        """
        Function for downloading and extracting the CDNA files from the ensembl FTP
        """
        
        file_name = data_dir + species + '_' + assembly + '/' + species + '.' + assembly + '.cdna.all.fa.gz'
        
        if os.path.isfile(file_name) == False:
            ftp_url = 'ftp://ftp.ensembl.org/pub/release-' + e-release + '/' + species.lower() + '/cdna/' + species[0].upper() + species[1:] + '.' + assembly + '.cdna.all.fa.gz'
            
            self.download_file(file_name, ftp_url)
        
        return file_name
    
    
    def getFastqFiles(self, ena_err_id, data_dir, ena_srr_id = None):
        """
        Function for downloading and extracting the FastQ files from the ENA
        """
        
        f_index = urllib2.urlopen(
        'http://www.ebi.ac.uk/ena/data/warehouse/filereport?accession=' + str(ena_err_id) + '&result=read_run&fields=study_accession,run_accession,tax_id,scientific_name,instrument_model,library_layout,fastq_ftp&download=txt')
        data = f_index.read()
        rows = data.split("\n")
        row_count = 0
        files = []
        gzfiles  = []
        for row in rows:
            if row_count == 0:
                row_count += 1
                continue
            
            row = row.rstrip()
            row = row.split("\t")
            
            if len(row) < 6:
                continue
            
            project = row[0]
            srr_id = row[1]
            if (ena_srr_id != None and srr_id != ena_srr_id):
                continue
            fastq_files = row[6].split(';')
            row_count += 1
            
            for fastq_file in fastq_files:
                file_name = fastq_file.split("/")
                
                print data_dir + project + "/" + file_name[-1]
                
                if os.path.isfile(data_dir + '/' + project + "/" + file_name[-1]) == False and os.path.isfile(data_dir + '/' + project + "/" + file_name[-1].replace('.fastq.gz', '.fastq')) == False:
                    file_location = data_dir + '/' + project + "/" + file_name[-1]
                    ftp_url = "ftp://" + fastq_file
                    self.download_file(file_location, ftp_url)
                
                if os.path.isfile(data_dir + '/' + project + "/" + file_name[-1]) == True:
                    gzfiles.append(data_dir + '/' + project + "/" + file_name[-1])
                files.append(data_dir + '/' + project + "/" + file_name[-1].replace('.fastq.gz', '.fastq'))
        
        for gzf in gzfiles:
            with gzip.open(gzf, 'rb') as f_in, open(gzf.replace('.fastq.gz', '.fastq'), 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
            os.remove(gzf)
        
        return files
    
    
    def download_file(self, file_location, url):
        """
        Function to download a file to a given location and file name. Will
        attempt to restart the download up to 5 times if the connection is
        closed by the remote server.
        """
        
        restart_counter = 0
        
        while True:
            meta = urllib2.urlopen(url)
            info = meta.info()
            if restart_counter > 0:
                byte_start = int(os.stat(file_location).st_size) + 1
                request = urllib2.Request(url, headers={"Range" : "bytes=" + str(byte_start) + "-" + str(info["content-length"])})
            else:
                request = urllib2.Request(url)
            
            req = urllib2.urlopen(request)
            CHUNK = 16 * 1024
            
            try:
                if restart_counter == 0 :
                    with open(file_location, 'wb') as fp:
                        while True:
                            chunk = req.read(CHUNK)
                            if not chunk: break
                            fp.write(chunk)
                else:
                    with open(file_location, 'ab') as fp:
                        while True:
                            chunk = req.read(CHUNK)
                            if not chunk: break
                            fp.write(chunk)
                
                req.close()
            except SocketError as e:
                if e.errno != errno.ECONNRESET:
                    raise
                print e
                print "Attempting to restart download ..."
                restart_counter += 1
            
            if restart_counter >= 5 :
                return False
            break
        
        return True
    
    
    def run_indexers(self, file_name):
        """
        
        """
        
        file_name_unzipped = file_name.replace('.fa.gz', '.fa')
        file_name_nofa = file_name_unzipped.replace('.fa', '')
        
        if os.path.isfile(file_name_unzipped) == False:
            print "Unzipping"
            with gzip.open(file_name, 'rb') as f_in, open(file_name_unzipped, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        
        if os.path.isfile(file_name_unzipped + '.bwt') == False:
            print "Indexing - BWA"
            self.bwa_index_genome(file_name)
        
        if os.path.isfile(file_name_nofa + '.1.bt2') == False:
            print "Indexing - Bowtie"
            self.bowtie_index_genome(file_name_unzipped)
        
        if os.path.isfile(file_name_nofa + '.gem') == False:
            print "Indexing - GEM"
            self.gem_index_genome(file_name_unzipped)
        
        return {'bowtie' : file_name_unzipped + '.1.bt2', 'bwa' : file_name_unzipped + '.bwt', 'gem' : file_name_unzipped + '.gem'}
    
    
    def gem_index_genome(self, genome_file):
        """
        Create an index of the genome FASTA file with GEM. These are saved
        alongside the assembly file.
        
        Parameters
        ----------
        genome_file : str
            Location of the assembly file in the file system
        """
        file_name = genome_file.split("/")
        
        command_line = 'gem-indexer -i ' + genome_file + ' -o ' + file_name[-1].replace('.fa', '')
        
        args = shlex.split(command_line)
        p = subprocess.Popen(args)
        p.wait()
        
        file_name = genome_file.split("/")
        file_name[-1].replace('.fa', '.gem')
        return '/'.join(file_name)
    
    
    def bowtie_index_genome(self, genome_file):
        """
        Create an index of the genome FASTA file with Bowtie2. These are saved
        alongside the assembly file.
        
        Parameters
        ----------
        genome_file : str
            Location of the assembly file in the file system
        """
        file_name = genome_file.split("/")
        file_name[-1].replace('.fa', '')
        
        command_line = 'bowtie2-build ' + genome_file + ' ' + file_name[-1].replace('.fa', '')
        
        args = shlex.split(command_line)
        p = subprocess.Popen(args)
        p.wait()
        
        return True
    
    
    def bwa_index_genome(self, genome_file):
        """
        Create an index of the genome FASTA file with BWA. These are saved
        alongside the assembly file.
        
        Parameters
        ----------
        genome_file : str
            Location of the assembly file in the file system
        """
        command_line = 'bwa index ' + genome_file
        
        args = shlex.split(command_line)
        p = subprocess.Popen(args)
        p.wait()
        
        amb_name = genome_file.split("/")
        amb_name[-1].replace('.fa', '.amb')
        
        ann_name = genome_file.split("/")
        ann_name[-1].replace('.fa', '.ann')
        
        bwt_name = genome_file.split("/")
        bwt_name[-1].replace('.fa', '.bwt')
        
        pac_name = genome_file.split("/")
        pac_name[-1].replace('.fa', '.pac')
        
        sa_name = genome_file.split("/")
        sa_name[-1].replace('.fa', '.pac')
        
        return ('/'.join(amb_name), '/'.join(ann_name), '/'.join(bwt_name), '/'.join(pac_name), '/'.join(sa_name))
        
        
    def bwa_align_reads(self, genome_file, reads_file):
        """
        Map the reads to the genome using BWA
        
        Parameters
        ----------
        genome_file : str
            Location of the assembly file in the file system
        reads_file : str
            Location of the reads file in the file system
        """
        
        reads_file = data_dir + project_id + '/' + run_id + '.fastq'
        intermediate_file = reads_file.replace('.fastq', '.sai')
        intermediate_sam_file = reads_file.replace('.fastq', '.sam')
        output_bam_file = reads_file.replace('.fastq', '.bam')
        
        command_lines = [
            'bwa aln -q 5 -f ' + intermediate_file + ' ' + genome_file + ' ' + reads_file,
            'bwa samse -f ' + intermediate_sam_file  + ' ' + genome_file + ' ' + intermediate_file + ' ' + reads_file,
            'samtools view -b -o ' + output_bam_file + ' ' + intermediate_sam_file
        ]
        
        print command_lines
        
        for command_line in command_lines:
            args = shlex.split(command_line)
            p = subprocess.Popen(args)
            p.wait()
    
    
    #def merge_bam(self, data_dir, project_id, final_id, run_ids=[]):
    def merge_bam(self, data_dir, project_id, final_id, run_ids=[]):
        """
        Merge together all the bams in a directory and sort to create the final
        bam ready to be filtered
        
        If run_ids is blank then the function looks for all bam files in the
        data_dir
        """
        out_bam_file = data_dir + project_id + '/' + final_id + '.bam'
        
        if len(run_ids) == 0:
            bam_files = [f for f in listdir(data_dir + project_id) if f.endswith(("sai"))]
        else:
            bam_files = [f + ".bam" for f in run_ids]
        
        bam_sort_files = []
        bam_merge_files = []
        for bam in bam_files:
            bam_loc = data_dir + project_id + '/' + bam
            bam_sort_files.append(bam_loc)
            bam_merge_files.append(bam_loc)

        for bam_sort_file in bam_sort_files:
            print bam_sort_file
            pysam.sort("-o", str(bam_sort_file), str(bam_sort_file))

        if len(bam_sort_files) == 1:
            pysam.sort("-o", str(out_bam_file), str(bam_sort_files[0]))
        else:
            pysam.merge(out_bam_file, *bam_merge_files)
            pysam.sort("-o", str(out_bam_file), "-T", str(out_bam_file) + ".bam_sort", str(out_bam_file))

        pysam.index(str(out_bam_file))
