[![CircleCI](https://circleci.com/gh/appliedbinf/URDO-SMOREd.svg?style=svg&circle-token=3bb907d8bdfe27332d68c56fc6cafc849a3e80a0)](https://circleci.com/gh/appliedbinf/URDO-SMOREd) [![codecov](https://codecov.io/gh/appliedbinf/URDO-SMOREd/branch/master/graph/badge.svg)](https://codecov.io/gh/appliedbinf/URDO-SMOREd) ![PyPI - Python Version](https://img.shields.io/pypi/pyversions/Django.svg) 

# Readme for SMORE'D
=============================================================================================
### Usage
```
smored
[--buildDB]
[--predict]
[-1 filename_fastq1][--fastq1 filename_fastq1]
[-2 filename_fastq2][--fastq2 filename_fastq2]
[-d directory][--dir directory][--directory directory]
[-c][--config]
[-P][--prefix]
[-a]
[-k]
[-o output_filename][--output output_filename]
[-x][--overwrite]
[-r]
[-v]
[-h][--help]
```
==============================================================================================

### There are two steps to sequence matching using smored.
1. Create DB : `smored --buildDB`
2. Predict : `smored --predict`

#### 1. `smored --buildDB`

**Synopsis:**
`smored --buildDB -c <config file> -k <kmer length(optional)> -P <DB prefix(optional)>`  
config file : is a tab delimited file which has the information for reference sequences, their multifasta files and profile definition file.
    Format : 
```
[loci]  
amplicon    ampliconFile
[profile]
profile   profileFile
```
kmer length : is the kmer length for the db. Note, while processing this should be smaller than the read length.  
    - We suggest kmer lengths of 35, 66 depending on the read length.  
DB prefix(optional) : holds the information for DB files to be created and their location. This module creates 3 files with this prefix.  
    - You can use a folder structure with prefix to store your db at particular location.

**Required arguments**
`--buildDB`  
    Identifier for build db module  
`-c,--config = <configuration file>`  
    Config file in the format described above.   

**Optional arguments**  
`-k = <kmer length>`
    Kmer size for which the db has to be formed(Default k = 35).   
`-P,--prefix = <prefix>`  
  Prefix for db and log files to be created(Default = kmer). Also you can specify folder where you want the dbb to be created.  
`-a`
    File location to write build log  
`-h,--help`  
    Prints the help manual for this application  

 --------------------------------------------------------------------------------------------
 
#### 2. `smored --predict`
  
`smored --predict` : can run in two modes
  1) single sample (default mode)
  2) multi-sample: run abil\smored for all the samples in a folder 

**Synopsis**
`smored --predict -1 <fastq file> -2 <fastq file> -d <directory location>  -P <DB prefix(optional)> -k <kmer length(optional)> -o <output file> -x`

**Required arguments** 
`-c,--config = <configuration file>`
  Config file in the format described above. 
  
 `-1,--fastq1 = <fastq1_filename>`  
  Path to first fastq file for paired end sample.
    - Should have extension fastq or fq.
`-2,--fastq2 = <fastq2_filename>`  
  Path to second fastq file for paired end sample.
    - Should have extension fastq or fq.
    ------or--------
`-d,--dir,--directory = <directory>`  
  Directory containing paired end read files for multi-sample prediction 
  
**Optional arguments**
`--predict`
  Identifier for predict module - this is the default function of SMORE'D
`-1,--fastq1 = <fastq1_filename>`  
  Path to first fastq file for paired end sample.
    - Should have extension fastq or fq.
`-2,--fastq2 = <fastq2_filename>`  
  Path to second fastq file for paired end sample.
    - Should have extension fastq or fq.
`-d,--dir,--directory = <directory>`  
  Directory containing paired end read files for multi-sample prediction  
`-k = <kmer_length>`  
  Kmer length for which the db was created (Default k = 35).  
`-o,--output = <output_filename>`  
  Prints the output to a file instead of stdout.  
`-P,--prefix = <prefix>`  
  Prefix using which the db was created (Defaults = kmer). The location of the db could also be provided.  
`-r`  
  A FASTA file is generated in the current directory for each sample containing reads with kmer matches.  
`-R, --readsdir = < output directory >`  
  A FASTQ file is generated in the specified directory for each sample containing reads with kmer matches.
`-u`
  FASTA file is generated in the current directory that contains unclassified reads.
`-U, --unclassifed = < output directory >`
  A directory is created for the FASTA files of unclassified reads
`--report`
 Generate pre-sampel reports in Excel format. If an output path is given, per-sample reports will be deposited in teh same folder.
`-t`
 Integer number of thread to use to process samples.
`-v`  
  Prints the version of the software.  
`-x,--overwrite`  
  By default abil\_URDOcaller appends the results to the output\_filename if same name is used.
  This argument overwrites the previously specified output file.
`-h,--help`
  Prints the help manual for this application  

