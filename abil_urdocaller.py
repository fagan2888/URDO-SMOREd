#!/usr/bin/env python
"""
The program has 3 basic modes:
    buildDB: for building the required databases
    predict, single sample: Predict markers and phenotypes from raw reads
    predict, multisample: Like above, but for multiple samples stored
        at a common location (paired end samples)
"""
import getopt
import sys
import logging
import os
import subprocess
import tempfile
import shutil
from itertools import islice
import operator
import urdohelper
VERSION = """ abil_URDOcaller ALPHA.3 (updated : September XX, 2018) """
"""
abil_URDOcaller free for academic users and requires permission before any
commercial or government usage of any version of this code/algorithm.
If you are a commercial or governmental user, please contact abil@ihrc.com
for permissions.

abil_URDOcaller is licensed under a modified Creative Commons By-NC-SA v4
license, please see the LICENSE file for specific terms.

For additional terms and conditions for government employees, see
"For Government Employees" section
"""

# predict part starts here
############################################################

__buildDB__ = False
__predict__ = False
OUTPUT_FILENAME = None
__batch__ = False
OVERWRITE = False
__paired__ = False
__fastq1__ = None
__fastq2__ = None
__user_k__ = False
__config__ = None
__timeDisp__ = False
__db_prefix__ = 'kmer'
__log__ = ''
__k__ = 35
__directory__ = None
__reads__ = False
#__allele_count__ = {}
__kmer_dict__ = {}
__weight_dict_global__ = {}
__st_profile__ = {}
__config_dict__ = {}
WORKERS = 10
WEIGHT = False
READ_PATH = ''
SUMMARY_STATS = {}
TMPDIR = tempfile.mkdtemp()

def batch_tool(kmer, results):
    """
    Function   : batch_tool
    Input      : Directory name, paired only, k value
    Output     : STs and allelic profiles for each FASTQ file
    Description: Processes all FASTQ files present in the input directory
    """
    freq_dict_samples = {}
    all_first_reads = [x for x in os.listdir(__directory__) if "_R1_" in x]
    for first_read_name in all_first_reads:
        sample_name = "_".join(first_read_name.split("_")[:-3])
        if sample_name in freq_dict_samples:
            freq_dict_samples[sample_name] += 1
        else:
            freq_dict_samples[sample_name] = 1
    urdohelper.link_reads(freq_dict_samples, all_first_reads)
    file_list = [x for x in os.listdir(TMPDIR) if "_R1_" in x]
    import threading
    from queue import Queue
    sample_queue = Queue()

    def add_jobdata_to_queue(read_one):
        """Make job data for queue"""
        fastq1_processed = f"{TMPDIR}/{read_one}"
        fastq2_processed = fastq1_processed.replace("_R1_", "_R2_")
        data = (fastq1_processed, fastq2_processed, kmer, results)
        return data
    for file in file_list:
        sample_queue.put(add_jobdata_to_queue(file))

    def process_samples(sample_queue):
        """Queue production"""
        while True:
            job_config = sample_queue.get()
            single_sample_tool(data=job_config)
            sample_queue.task_done()
    worker_count = 0
    while worker_count < WORKERS:
        thread_id = threading.Thread(target=process_samples, args=(sample_queue,))
        thread_id.daemon = True
        thread_id.start()
        worker_count += 1

    sample_queue.join()
    shutil.rmtree(TMPDIR)
    return results


def single_sample_tool(**kwargs):
    """
    Function   : single_sample_tool
    Input      : fastq file 1 and 2, paired or single, k value, output dictionary
    Output     : STs and allelic profiles for each FASTQ file
    Description: Processes both FASTQ files passed to the function
    """
    if 'data' in kwargs:
        fastq1, fastq2, k, sample_results = kwargs['data']
    else:
        fastq1, fastq2, k, sample_results = kwargs.values()

    sample_name = fastq1.split('/')[-1].split('_')[0]
    if __reads__:
        read_file_name = READ_PATH + sample_name + '_reads.fq'
        try:
            read_file = open(read_file_name, 'w+')
        except OSError as error:
            print(f"Count not open {read_file}\n{error}")
    logging.debug(f"Preprocessing: working with {fastq1} and {fastq2}")
    logging.debug(f"Preprocessing: [Merging reads] Merging {fastq1} and {fastq2}")
    vsearch_cmd = "vsearch --fastq_mergepairs {} --reverse {} --fastaout {}/{}.fa".format(
        fastq1, fastq2, TMPDIR, sample_name)
    vsearch_cmd += " --minseqlength 75"
    logging.debug(f"Preprocessing: [Merging reads] VSEARCH command\n\t{vsearch_cmd}")
    try:
        vsearch_pipes = subprocess.Popen(vsearch_cmd,
                                         shell=True,
                                         stdout=subprocess.PIPE,
                                         stderr=subprocess.PIPE)
        std_out, std_err = vsearch_pipes.communicate()
        logging.debug(f"Preprocessing: [Merging reads]\n")
        logging.debug(f"{std_out.decode('utf-8')}{std_err.decode('utf-8')}")
    except subprocess.CalledProcessError as subprocess_error:
        logging.error(f"Preprocessing: [Merging reads] Could not merge {sample_name}")
        logging.error(f"ERROR: {subprocess_error}")
        sys.exit(f"Could not merge read files for {sample_name}!")
    vsearch_cmd = "vsearch  --derep_fulllength  {0}/{1}.fa  --output {0}/{1}_centroids.fa ".format(
        TMPDIR, sample_name)
    vsearch_cmd += "--relabel out_ --sizeout --fasta_width 0"
    try:
        vsearch_pipes = subprocess.Popen(vsearch_cmd,
                                         shell=True,
                                         stdout=subprocess.PIPE,
                                         stderr=subprocess.PIPE)
        std_out, std_err = vsearch_pipes.communicate()
        logging.debug(f"Preprocessing: [Merging reads]\n")
        logging.debug(f"{std_out.decode('utf-8')}{std_err.decode('utf-8')}")
    except subprocess.CalledProcessError as subprocess_error:
        logging.error(f"Preprocessing: [Merging reads] Could not merge {sample_name}")
        logging.error(f"ERROR: {subprocess_error}")
        sys.exit(f"Could not merge read files for {sample_name}!")
    if __reads__:
        read_processor(TMPDIR, k, sample_name, sample_results, read_file)
    else:
        read_processor(TMPDIR, k, sample_name, sample_results, None)
    if sample_results[sample_name] == {}:
        string = f"No k-mer matches were found for the sample {fastq1} and {fastq2}"
        string += f"\n\tProbable cause of the error:  low quality data/too many N's in the data"
        logging.error(f"ERROR: {string}")
        if not __batch__:
            exit()
    if __reads__:
        read_file.close()
    # if 'data' in kwargs:
    return sample_results


def read_processor(fastq, k, sample_name, count_dict, read_fh):
    """
    Function   : read_processor
    Input      : fastq file, k value
    Output     : Edits a global dictionary - results
    Description: Processes the single fastq file
    """
    fastq = f"{fastq}/{sample_name}_centroids.fa"
    msg = f"Analysis: Begin processing merged reads ({fastq})"
    logging.debug(msg)
    if os.path.isfile(fastq):
        logging.debug(f"Analysis: Kmer counting using k={k}")
        if sample_name not in count_dict:
            count_dict[sample_name] = {}
        fastq_file = open(fastq)
        for lines in iter(lambda: list(islice(fastq_file, 2)), ()):
            if len(lines) < 2:
                logging.debug(
                    "ERROR: Please verify the input FASTQ files are correct")
            try:
                if len(lines[1]) < k:
                    continue
            except IndexError:
                logging.debug(f"ERROR: Check fastq file {fastq_file}")
                return 0
            start = int((len(lines[1])-k)//2)
            kmer_list = [str(lines[1][:k]), str(
                lines[1][start:k+start]), str(lines[1][-35:])]
            if any(kmer in __kmer_dict__[k] for kmer in kmer_list):
                k_cov, assignment = count_kmers(lines, k, sample_name, count_dict)
                if __reads__:
                    lines[0] = f"{lines[0].rstrip()};{k_cov:.3f};{assignment}\n"
                    read_fh.write(''.join('{}'.format(l) for l in lines))
    else:
        logging.error(f"ERROR: File does not exist: {fastq}")


def count_kmers(read, k, sample_name, count_dict):
    """
    Function   : goodReads
    Input      : sequence read, k, step size
    Output     : Edits the count of global variable __allele_count__
    Description: Increment the count for each k-mer match
    """
    __allele_count__ = {}
    start_pos = 0
    read[1].rstrip()
    for start_pos in range(len(read[1])-k+1):
        kmer_string = str(read[1][start_pos:start_pos+k])
        if kmer_string in __kmer_dict__[k]:
            for prob_locus in __kmer_dict__[k][kmer_string]:
                if prob_locus not in __allele_count__:
                    __allele_count__[prob_locus] = {}
                prob_alleles = __kmer_dict__[k][kmer_string][prob_locus]
                for allele in prob_alleles:
                    allele = allele.rstrip()
                    if allele in __allele_count__[prob_locus]:
                        __allele_count__[prob_locus][allele] += 1
                    else:
                        __allele_count__[prob_locus][allele] = 1
        start_pos += 1
    max_supports = {}
    max_allele_count = 0
    max_allele = ''
    max_allele_number = 0
    allele_k_count = ''
    for allele in __allele_count__:
        allele_number = max(
            __allele_count__[allele].items(), key=operator.itemgetter(1))[0]
        allele_k_count = __allele_count__[allele][max(__allele_count__[allele].items(),
                                                      key=operator.itemgetter(1))[0]]
        if allele_k_count > max_allele_count:
            max_allele_count = allele_k_count
            max_allele = allele
            max_allele_number = allele_number

    if max_allele not in max_supports:
        max_supports[max_allele] = {}
    max_supports[max_allele][max_allele_number] = max_allele_count
    if max_allele not in count_dict[sample_name]:
        count_dict[sample_name][max_allele] = {}
    if max_allele_number not in count_dict[sample_name][max_allele]:
        count_dict[sample_name][max_allele][max_allele_number] = int(
            read[0].split(";")[1].split("=")[1])
    else:
        count_dict[sample_name][max_allele][max_allele_number] += int(
            read[0].split(";")[1].split("=")[1])
    return (max_allele_count/(len(read[1]) - k + 1)), __st_profile__[max_allele][max_allele_number]



def load_module(k, db_prefix):
    """
    Function   : load_module
    Input      : k value and prefix of the DB file
    Output     : Updates the DB dictionary variables
    Description: Used in loading the DB as set of variables by calling other functions
    """
    # global db_file
    db_file = db_prefix+'_'+str(k)+'.txt'
    weight_file = db_prefix+'_weight.txt'
    profile_file = db_prefix+'_profile.txt'
    __kmer_dict__[k] = load_kmer_dict(db_file)
    temp_weight_dict = {}
    temp_weight_dict = load_weight_dict(weight_file)
    __weight_dict_global__.update(temp_weight_dict)
    temp_st_dict = load_st_from_file(profile_file)
    __st_profile__.update(temp_st_dict)
    try:
        load_config(__config__)
    except OSError as error:
        print(error)
        logging.debug(error)
        exit(1)


def load_st_from_file(profile_file):
    """
    Function   : load_st_from_file
    Input      : profile definition file
    Output     : Updates the DB dictionary variables
    Description: Used in loading the DB as set of variables
    """
    with open(profile_file, 'r') as profiles_fh:
        st_table = {}
        for line in profiles_fh:
            if not line.startswith("marker"):
                cols = line.rstrip().rsplit('\t')
                if cols[0] not in st_table:
                    st_table[cols[0]] = {}
                st_table[cols[0]][cols[1]] = cols[2]
    return st_table


def load_kmer_dict(db_file):
    """
    Function   : load_kmer_dict
    Input      : DB prefix
    Output     : Updates the DB dictionary variables
    Description: Used in loading the DB as set of variables
    """
    kmer_table_dict = {}
    with open(db_file, 'r') as kmer_fh:
        lines = kmer_fh.readlines()
        for line in lines:
            array = line.rstrip().rsplit('\t')
            kmer_table_dict[array[0]] = {}
            kmer_table_dict[array[0]][array[1]] = array[2][1:-1].rsplit(',')
    return kmer_table_dict


def load_weight_dict(weight_file):
    """
    Function   : load_weight_dict
    Input      : Weight file prefix
    Output     : Updates the DB dictionary variables
    Description: Used in loading the DB as set of variables
    """
    __weight_dict_global__.clear()
    with open(weight_file, 'r') as weight_table_fh:
        lines = weight_table_fh.readlines()
        for line in lines:
            array = line.rstrip().rsplit('\t')
            try:
                (loc, allele) = array[0].replace('-', '_').rsplit('_', 1)
            except ValueError:
                print(
                    "Error : Allele name in locus file should be seperated by '_' or '-'")
                exit(0)
            if loc not in __weight_dict_global__:
                __weight_dict_global__[loc] = {}
            __weight_dict_global__[loc][allele] = float(array[1])
    return __weight_dict_global__


def load_config(config):
    """
    Function   : load_config
    Input      : config file path from getopts
    Output     : Updates configDict
    Description: Used to find allele fasta files for getCoverage
    """
    config_dict = {}
    with open(config) as config_fh:
        lines = config_fh.readlines()
        head = ''
        for line in lines:
            if line.rstrip() == '':
                continue
            if line.rstrip() == '[loci]':
                head = 'loci'
                config_dict[head] = {}
            elif line.rstrip() == '[profile]':
                head = 'profile'
                config_dict[head] = {}
            else:
                arr = line.strip().split()
                config_dict[head][arr[0]] = arr[1]
    for head in config_dict:
        for element in config_dict[head]:
            if not os.path.isfile(config_dict[head][element]):
                raise OSError("ERROR: %s file does not exist at %s" %
                              (element, config_dict[head][element]))
    __config_dict__.update(config_dict)
    return


def print_results(results, output_filename, overwrite):
    """
    Function   : print_results
    Input      : results, output file, overwrite?
    Output     : Prints on the screen or in a file
    Description: Prints the results in the format asked by the user
    """
    # pp.pprint(results)
    if output_filename != None:
        if overwrite is False:
            outfile = open(output_filename, "a")
        else:
            outfile = open(output_filename, "w")
    # pp.pprint(__st_profile__)
    output = {}
    out_string = 'Sample'
    logging.debug(
        "Post-processing: Finding most likely phenotypes and markers")
    output = select_markers(results)
    sorted_samples = sorted(output["sample"])
    for sample in sorted_samples:
        out_string += (f"\t{sample}")
    out_string += "\n"
    sorted_output_keys = sorted(output)
    for key in sorted_output_keys:
        if key != "sample":
            out_string += f"{key}"
            for sample in sorted_samples:
                if sample in output[key]:
                    out_string += f"\t{output[key][sample]}"
                else:
                    out_string += f"\t0"
            out_string += "\n"
    if output_filename != None:
        outfile.write(f"{out_string}\n")
    else:
        print(f"{out_string}\n")

def select_markers(result_dict):
    """Reformat results dict for printing"""
    output = {}
    output["sample"] = []
    for sample in result_dict:
        output["sample"].append(sample)
        for loc in result_dict[sample]:
            if loc == "genericmarkers":
                for marker_id in result_dict[sample][loc]:
                    if __st_profile__[loc][marker_id] not in output:
                        output[__st_profile__[loc][marker_id]] = {}
                    if sample not in output[__st_profile__[loc][marker_id]]:
                        output[__st_profile__[loc][marker_id]
                              ][sample] = result_dict[sample][loc][marker_id]
                    else:
                        output[__st_profile__[loc][marker_id]
                              ][sample] += result_dict[sample][loc][marker_id]
            else:
                max_marker_id = max(
                    result_dict[sample][loc].items(), key=operator.itemgetter(1))[0]
                if __st_profile__[loc][max_marker_id] not in output:
                    output[__st_profile__[loc][max_marker_id]] = {}
                output[__st_profile__[loc][max_marker_id]
                      ][sample] = result_dict[sample][loc][max_marker_id]
    return output
################################################################################
# Predict part ends here
################################################################################


def reverse_complement(seq):
    """
    Build DB part starts
    Returns the reverse complement of the sequence
    """
    seq_uppercase = seq.upper()
    seq_dict = {'A': 'T', 'T': 'A',
                'G': 'C', 'C': 'G', 'Y': 'R',
                'R': 'Y', 'S': 'S', 'W': 'W',
                'K': 'M', 'M': 'K', 'N': 'N'}
    try:
        return "".join([seq_dict[base] for base in reversed(seq_uppercase)])
    except ValueError:
        logging.debug(f"Reverse Complement Error: {seq_uppercase}")


def get_fasta_dict(full_locus_file):
    """
    Function   : get_fasta_dict
    Input      : locus file name
    Output     : dictionary with all the allele sequences
    Description: Stores each allele sequence in a dictionary
    """
    logging.debug("Create Fasta Dict")
    logging.debug(full_locus_file)
    fasta_file = open(full_locus_file, 'r').read()
    entries = [x for x in fasta_file.split('>') if len(x) != 0]
    fasta_dict = {}
    for entry in entries:
        key = [x for x in entry.split('\n')[0].split() if len(x) != 0][0]
        sequence = ''.join(entry.split('\n')[1:]).rstrip()
        fasta_dict[key] = {'sequence': sequence}
    return fasta_dict


def form_kmer_db(config_dict, k, output_filename):
    """
    Function   : form_kmer_db
    Input      : configuration file, k value, output prefix
    Output     : abil_URDOcaller DB
    Description: Constructs the k-mer DB in both strand orientation
    """
    mean = {}
    for locus in config_dict['loci']:
        logging.debug(f"formKmerDB : {locus}")
        fasta_dict = get_fasta_dict(config_dict['loci'][locus])
        total_kmer_length = 0
        seq_location = 0
        for allele in list(fasta_dict.keys()):
            seq = fasta_dict[allele]['sequence'].strip()
            total_kmer_length += len(seq)
            seq_location += 1
            allele_id = allele.replace('-', '_').rsplit('_', 1)
            i = 0
            while i+k <= len(seq):
                kmer = seq[i:i+k]
                rev_comp_kmer = reverse_complement(kmer)
                if kmer not in __kmer_dict__:
                    __kmer_dict__[kmer] = {}
                    __kmer_dict__[kmer][allele_id[0]] = []
                    __kmer_dict__[kmer][allele_id[0]].append(int(allele_id[1]))
                else:
                    if allele_id[0] not in __kmer_dict__[kmer]:
                        __kmer_dict__[kmer][allele_id[0]] = []
                        __kmer_dict__[kmer][allele_id[0]].append(
                            int(allele_id[1]))
                    else:
                        __kmer_dict__[kmer][allele_id[0]].append(
                            int(allele_id[1]))
                if rev_comp_kmer not in __kmer_dict__:
                    __kmer_dict__[rev_comp_kmer] = {}
                    __kmer_dict__[rev_comp_kmer][allele_id[0]] = []
                    __kmer_dict__[rev_comp_kmer][allele_id[0]].append(
                        int(allele_id[1]))
                else:
                    if allele_id[0] not in __kmer_dict__[rev_comp_kmer]:
                        __kmer_dict__[rev_comp_kmer][allele_id[0]] = []
                        __kmer_dict__[rev_comp_kmer][allele_id[0]].append(
                            int(allele_id[1]))
                    else:
                        __kmer_dict__[rev_comp_kmer][allele_id[0]].append(
                            int(allele_id[1]))
                i += 1
        mean[locus] = total_kmer_length/seq_location*1.0
    write_db(output_filename, k)
    write_weight_file(output_filename, config_dict, mean)

def write_db(db_file_path, kmer):
    """Write kmer db file"""
    db_file_name = f"{db_file_path}_{kmer}.txt"
    with open(db_file_name, 'w') as kfile:
        for key in __kmer_dict__:
            for key1 in __kmer_dict__[key]:
                string = str(key)+'\t'+str(key1)+'\t' + \
                    str(__kmer_dict__[key][key1]).replace(" ", "")+'\n'
                kfile.write(string)
    kfile.close()

def write_weight_file(weight_file_path, w_config, locus_means):
    """Write weight file"""
    weight_file_name = f"{weight_file_path}_weight.txt"
    with open(weight_file_name, 'w') as wfile:
        for locus in w_config['loci']:
            fasta_dict = get_fasta_dict(w_config['loci'][locus])
            for allele in list(fasta_dict.keys()):
                seq = fasta_dict[allele]['sequence']
                seq_len = len(seq)
                frac = (seq_len / locus_means[locus])
                output_string = allele + '\t' + str(frac) + '\n'
                if frac > 1.05 or frac < 0.95:
                    wfile.write(output_string)
    wfile.close()


def copy_profile(profile_dict, output_filename):
    """
    Function   : copy_profile
    Input      : profileDict
    Output     : None
    Description: Duplicated profile file for db
    """
    profile_filename = output_filename+'_profile.txt'
    with open(profile_dict['profile']) as profiles_fh:
        lines = profiles_fh.readlines()
        with open(profile_filename, "w") as profiles_out_fh:
            profiles_out_fh.writelines(lines)


def make_custom_db(config, k, output_filename):
    """
    Function   : make_custom_db
    Input      : configuration file, k value, output prefix
    Output     : None
    Description: Processes the config file and calls the relevant function
    """
    config_dict = {}
    if output_filename is None:
        output_filename = 'kmerDB'
    with open(config, 'r') as config_file:
        lines = config_file.readlines()
        head = ''
        for line in lines:
            if line.rstrip() == '':
                continue
            if line.rstrip() == '[loci]':
                head = 'loci'
                config_dict[head] = {}
            elif line.rstrip() == '[profile]':
                head = 'profile'
                config_dict[head] = {}
            else:
                print(line.strip().split())
                arr = line.strip().split()
                config_dict[head][arr[0]] = arr[1]
    for head in config_dict:
        for element in config_dict[head]:
            if not os.path.isfile(config_dict[head][element]):
                print("ERROR: %s file does not exist at %s" %
                      (element, config_dict[head][element]))
                exit(0)
    form_kmer_db(config_dict, k, output_filename)
    copy_profile(config_dict['profile'], output_filename)

################################################################################
# Build DB part ends
# Check Parameters
################################################################################
def check_params(params):
    """
    Check input parameters
    """
    build_db, predict, config, k, batch, directory, fastq1, fastq2, db_prefix = params
    if predict:
        if config is None:
            print(urdohelper.HELP_TEXT_SMALL)
            print("Config parameter is required.")
            exit(0)
        if not os.path.isfile(db_prefix+'_'+str(k)+'.txt'):
            print(urdohelper.HELP_TEXT_SMALL)
            print(f"DB file does not exist : {db_prefix}_{k}.txt or change DB prefix.")
            exit(0)
        if not os.path.isfile(db_prefix+'_weight.txt'):
            print(urdohelper.HELP_TEXT_SMALL)
            print(f"DB file does not exist : {db_prefix}_weight.txt or change DB prefix.")
            exit(0)
        if not os.path.isfile(db_prefix+'_profile.txt'):
            print(urdohelper.HELP_TEXT_SMALL)
            print(f"DB file does not exist : {db_prefix}_profile.txt or change DB prefix.")
            exit(0)
        elif batch:
            if not os.path.isdir(directory):
                print(urdohelper.HELP_TEXT_SMALL)
                print(f"Error: Directory ({directory}) does not exist!")
                exit(0)
        elif predict and not batch:
            if not os.path.isfile(fastq1) or not os.path.isfile(fastq2):
                print(f"Error: Please check FASTQ file paths")
                exit(0)
    if build_db:
        try:
            if not os.path.isfile(config):
                print(urdohelper.HELP_TEXT_SMALL)
                print(f"Error: Configuration file ({config}) does not exist!")
                exit(0)
        except RuntimeError:
            print(urdohelper.HELP_TEXT_SMALL)
            print("Error: Specify Configuration file")
            exit(0)

################################################################################
# The Program Starts Execution Here

# Input arguments
__options__, __remainder__ = getopt.getopt(sys.argv[1:], 'o:x1:2:k:bd:phP:c:rR:va:wt:', [
    'buildDB',
    'predict',
    'output=',
    'config=',
    'prefix=',
    'overwrite',
    'batch',
    'fastq1=',
    'fastq2=',
    'dir=',
    'directory=',
    'help',
    'readsdir=',
    'threads='])
for opt, arg in __options__:
    if opt in ('-o', '--output'):
        OUTPUT_FILENAME = arg
    elif opt in ('-x', '--overwrite'):
        OVERWRITE = True
    elif opt in '--buildDB':
        __buildDB__ = True
    elif opt in ('-P', '--prefix'):
        __db_prefix__ = arg
    elif opt in '--predict':
        __predict__ = True
    elif opt in ('-c', '--config'):
        __config__ = arg
    elif opt in '-k':
        __user_k__ = True
        try:
            __k__ = int(arg)
        except ValueError:
            print("Error: Enter a numerical k value.")
            exit(0)
        # Check to make sure the arg is an int.
    elif opt in ('-1', '--fastq1'):
        __fastq1__ = arg
    elif opt in ('-2', '--fastq2'):
        __fastq2__ = arg
    elif opt in ('-d', '--dir', '--directory'):
        __directory__ = os.path.abspath(arg) + "/"
        urdohelper.__directory__ = __directory__
        urdohelper.TMPDIR = TMPDIR
        __batch__ = True
    elif opt in '-a':
        __log__ = arg
    elif opt in '-r':
        __reads__ = True
    elif opt in '-R':
        __reads__ = True
        READ_PATH = os.path.abspath(arg) + "/"
        if not os.path.isdir(READ_PATH):
            try:
                os.makedirs(READ_PATH)
            except OSError as error:
                print(f"Count not make {READ_PATH}\n{error}")
                exit(1)
    elif opt in '-v':
        print(VERSION)
        exit(0)
    elif opt in ('-h', '--help'):
        print(urdohelper.HELP_TEXT)
        exit(0)
    elif opt == '-w':
        WEIGHT = True
    elif opt in ('-t', '--threads'):
        try:
            WORKERS = int(opt)
        except ValueError:
            print("Please provide an integer number of threads")
            exit()

if __name__ == "__main__":
    if __predict__ and __buildDB__:
        print(urdohelper.HELP_TEXT_SMALL)
        print("Select either predict or buildDB module")
        exit(0)
    if not __predict__ and not __buildDB__:
        print(urdohelper.HELP_TEXT_SMALL)
        print("Select either predict or buildDB module")
        exit(0)
    PARAMETERS = [__buildDB__, __predict__, __config__, __k__, __batch__,
                  __directory__, __fastq1__, __fastq2__, __db_prefix__]

    check_params(PARAMETERS)
    if __buildDB__:
        try:
            if not __log__:
                __log__ = subprocess.check_output('date "+%Y%m%d_%H%M"',
                                                  shell=True).decode('utf-8').rstrip() +'.log'
                sys.stderr.write(f"Writing log file to: {__log__}\n")
        except TypeError:
            __log__ = 'kmer.log'
        logging.basicConfig(filename=__log__, level=logging.DEBUG,
                            format='%(asctime)s %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p')
        if os.path.isfile(__config__):
            print("Info: Making DB for k = ", __k__)
            print("Info: Making DB with prefix =", __db_prefix__)
            print("Info: Log file written to ", __log__)
            make_custom_db(__config__, __k__, __db_prefix__)
        else:
            print("Error: The input config file "+__config__ + " does not exist.")
    elif __predict__:
        try:
            if not __log__:
                __log__ = subprocess.check_output('date "+%Y%m%d_%H%M"',
                                                  shell=True).decode('utf-8').rstrip() +'.log'
                sys.stderr.write(f"Writing log file to: {__log__}\n")
        except TypeError:
            __log__ = 'kmer.log'
        logging.basicConfig(filename=__log__, level=logging.DEBUG,
                            format='%(asctime)s %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p')
        logging.debug(
            "==============================================================================")
        logging.debug(f"Command: {' '.join(sys.argv)}")
        logging.debug("Starting Marker Prediction")
        logging.debug(f"Temporary directory: {TMPDIR}")
        load_module(__k__, __db_prefix__)
        RAW_COUNTS = {}
        if __batch__:
            RAW_COUNTS = batch_tool(__k__, RAW_COUNTS)
        else:
            # fastq1, fastq2, k, sample_results
            RAW_COUNTS = single_sample_tool(fastq1=__fastq1__,
                                            fastq2=__fastq2__,
                                            k=__k__,
                                            sample_results=RAW_COUNTS)
        if WEIGHT:
            WEIGHT_COUNTS = urdohelper.weight_profile(RAW_COUNTS, __weight_dict_global__)
            print_results(WEIGHT_COUNTS, OUTPUT_FILENAME, OVERWRITE)
        else:
            print_results(RAW_COUNTS, OUTPUT_FILENAME, OVERWRITE)
    else:
        print("Error: Please select the mode")
        print("--buildDB (for database building) or --predict (for marker discovery)")
