
#!/usr/bin/env python3

#To run : python3 cmAdapter.py -b code/tests/generic_039/base_test.cpp  -t code/tests/generic_039/generic_039 -p code/tests/generic_039
import os
import re
import sys
import stat
import subprocess
import argparse
import time
import traceback
import itertools
from shutil import copyfile
import concurrent.futures
import multiprocessing
from tqdm import tqdm


#All functions that has options go here
FallocOptions = ['FALLOC_FL_ZERO_RANGE','FALLOC_FL_ZERO_RANGE | FALLOC_FL_KEEP_SIZE','FALLOC_FL_PUNCH_HOLE | FALLOC_FL_KEEP_SIZE', '0',  'FALLOC_FL_KEEP_SIZE']

FsyncOptions = ['fsync','fdatasync']

RemoveOptions = ['remove','unlink']

LinkOptions = ['link','symlink']

WriteOptions = ['WriteData','WriteDataMmap', 'pwrite']

redeclare_map = {}

def parse_args():
    parser = argparse.ArgumentParser(description='Ace Workload Generator')

    # global args
    parser.add_argument('--input', '-i', default='', required=True, type=str,
                        help='Source file path. If it is tests/seq1/, ' \
                             'the J-lang files are in tests/seq1/j-lang-files/, ' \
                             'the output cpps are in tests/seq1/ (will overwrites) existing cpps.')

    parser.add_argument('--cpus', '-n', default=1, required=True, type=int,
                        help='Number of cpus to use')

    args = parser.parse_args()
    print(args)

    if not os.path.isdir(args.input):
        print("No such input dir: %s" % (args.input))
        exit(0)

    max_cpus = multiprocessing.cpu_count()
    if args.cpus == 0 or args.cpus >= max_cpus:
        args.cpus = max_cpus - 1

    return args


def print_setup(parsed_args):
    print('\n{: ^50s}'.format('XFSMonkey Workload generatorv0.1\n'))
    print('='*20, 'Setup' , '='*20, '\n')
    print('{0:20}  {1}'.format('Base test file', parsed_args.base_file))
    print('{0:20}  {1}'.format('Test skeleton', parsed_args.test_file))
    print('{0:20}  {1}'.format('Target directory', parsed_args.target_path))
    print('{0:20}  {1}'.format('Output file', parsed_args.output_name))
    print('\n', '='*48, '\n')


def create_dir(dir_path):
    try:
        os.makedirs(dir_path)
    except OSError:
        if not os.path.isdir(dir_path):
            raise

def create_dict():
    operation_map = {'fsync': 0, 'fallocate': 0, 'open': 0, 'remove': 0}
    return operation_map


#These maps keep track of the line number in each method, to add the next function to in the C++ file
def updateSetupMap(index_map, num):
    index_map['setup'] += num
    index_map['run'] += num
    index_map['define'] += num

def updateRunMap(index_map, num):
    index_map['run'] += num
    index_map['define'] += num

def updateDefineMap(index_map, num):
    index_map['define'] += num

def insertDeclare(line, file, index_map, redeclare_map):

    with open(file, 'r+') as declare:
        contents = declare.readlines()

        updateRunMap(index_map, 1)

        to_insert = '\t\t\t\tint ' + line + ' = 0 ;\n'
        contents.insert(index_map['run'], to_insert)

        declare.seek(0)
        declare.writelines(contents)
        declare.close()


# Add the 'line' which declares a file/dir used in the workload into the 'file'
# at position specified in the 'index_map'
def insertDefine(line, file, index_map, redeclare_map):
    with open(file, 'r+') as define:

        contents = define.readlines()

        #Initialize paths in setup phase
        updateSetupMap(index_map, 1)
        file_str = ''
        if len(line.split('/')) != 1 :
            for i in range(0, len(line.split('/'))):
                file_str += line.split('/')[i]
        else:
            file_str = line.split('/')[-1]

        if file_str == 'test':
            to_insert = '\t\t\t\t' + file_str + '_path = mnt_dir_ ;\n'
        else:
            to_insert = '\t\t\t\t' + file_str + '_path = mnt_dir_' + ' + "/' + line + '";\n'

        contents.insert(index_map['setup'], to_insert)

        #Initialize paths in run phase
        updateRunMap(index_map, 1)
        file_str = ''
        if len(line.split('/')) != 1 :
            for i in range(0, len(line.split('/'))):
                file_str += line.split('/')[i]
        else:
            file_str = line.split('/')[-1]

        if file_str == 'test':
            to_insert = '\t\t\t\t' + file_str + '_path = mnt_dir_ ;\n'
        else:
            to_insert = '\t\t\t\t' + file_str + '_path =  mnt_dir_' + ' + "/' + line + '";\n'
        contents.insert(index_map['run'], to_insert)

        #Update defines portion
        #Get only the file name. We don't want the path here
        updateDefineMap(index_map, 1)
        file_str = ''
        if len(line.split('/')) != 1 :
            for i in range(0, len(line.split('/'))):
                file_str += line.split('/')[i]
        else:
            file_str = line.split('/')[-1]
        to_insert = '\t\t\t string ' + file_str + '_path; \n'

        contents.insert(index_map['define'], to_insert)

        define.seek(0)
        define.writelines(contents)
        define.close()


def insertCreateSnapshot(contents, line, index_map, redeclare_map, method):
    name = 'fd_procfs'
    decl = ' '
    if name not in redeclare_map:
        decl = 'int '
        redeclare_map[name] = 1

    # open the procfs
    to_insert = '\n\t\t\t\t' + decl + name + ' = cm_->CmOpen( "' + line.split(' ')[1] + '" , O_WRONLY );'
    to_insert += '\n\t\t\t\tif ( ' + name + ' < 0 ) {\n\t\t\t\t\treturn -1;\n\t\t\t\t}'

    # write to the procfs
    to_insert += '\n\t\t\t\tif ( cm_->CmWrite ( ' + name + ', "1", 1 ) != 1){ \n\t\t\t\t\treturn -1;\n\t\t\t\t}'

    # close the procfs
    to_insert += '\n\t\t\t\tif ( cm_->CmClose ( ' + name + ') < 0){ \n\t\t\t\t\treturn -1;\n\t\t\t\t}\n\n'

    if method == 'setup':
        contents.insert(index_map['setup'], to_insert)
        updateSetupMap(index_map, 11)
    else:
        contents.insert(index_map['run'], to_insert)
        updateRunMap(index_map, 11)

def insertDeleteSnapshot(contents, line, index_map, redeclare_map, method):
    name = 'fd_procfs'
    decl = ' '
    if name not in redeclare_map:
        decl = 'int '
        redeclare_map[name] = 1

    # open the procfs
    to_insert = '\n\t\t\t\t' + decl + name + ' = cm_->CmOpen( "' + line.split(' ')[1] + '" , O_WRONLY );'
    to_insert += '\n\t\t\t\tif ( ' + name + ' < 0 ) {\n\t\t\t\t\treturn -1;\n\t\t\t\t}'

    # write to the procfs
    buf = line.split(' ')[2]
    to_insert += '\n\t\t\t\tif ( cm_->CmWrite ( ' + name + ', "' + buf + '", sizeof( "' + buf + '" )  ) != sizeof("' + buf + '") ){ \n\t\t\t\t\treturn -1;\n\t\t\t\t}'

    # close the procfs
    to_insert += '\n\t\t\t\tif ( cm_->CmClose ( ' + name + ') < 0){ \n\t\t\t\t\treturn -1;\n\t\t\t\t}\n\n'

    if method == 'setup':
        contents.insert(index_map['setup'], to_insert)
        updateSetupMap(index_map, 11)
    else:
        contents.insert(index_map['run'], to_insert)
        updateRunMap(index_map, 11)


def insertMark(contents, line, index_map, method):
    # to_insert = '\n\t\t\t\tif ( mkdir(' + line.split(' ')[1] + '_path.c_str() , ' + line.split(' ')[2] + ') < 0){ \n\t\t\t\t\treturn -1;\n\t\t\t\t}\n\n'
    to_insert = '\n\t\t\t\tif ( cm_->CmMark('') < 0){ \n\t\t\t\t\treturn -1;\n\t\t\t\t}\n\n'

    if method == 'setup':
        contents.insert(index_map['setup'], to_insert)
        updateSetupMap(index_map, 4)
    else:
        contents.insert(index_map['run'], to_insert)
        updateRunMap(index_map, 4)

def insertFalloc(contents, line, index_map, method, func_count):
    fname = line.split(' ')[1]
    mode = line.split(' ')[2]
    off = line.split(' ')[3]
    length = line.split(' ')[4]

    to_insert = '\n'
    to_insert += '\t\t\t\tif (cm_->CmFallocate(fd_%s, %s, %s, %s) < 0) {\n' % (fname, mode, off, length)
    to_insert += '\t\t\t\t\treturn -1;\n'
    to_insert += '\t\t\t\t}\n'

    desc = '"falloc " + %s_path + " %s %s"' % (fname, mode, length)
    to_insert += '\t\t\t\tthis->get_disk_content("oracle_%02d_falloc.txt", %s);\n' % (func_count, desc)
    to_insert += '\n'

    if method == 'setup':
        contents.insert(index_map['setup'], to_insert)
        updateSetupMap(index_map, 5)
    else:
        contents.insert(index_map['run'], to_insert)
        updateRunMap(index_map, 5)

def insertMkdir(contents, line, index_map, method, func_count):
    dir_name = line.split(' ')[1]
    mode = line.split(' ')[2]

    to_insert = '\n'
    to_insert += '\t\t\t\tif (cm_->CmMkdir(%s_path.c_str(), %s) < 0) {\n' % (dir_name, mode)
    to_insert += '\t\t\t\t\treturn -1;\n'
    to_insert += '\t\t\t\t}\n'

    desc = '"mkdir " + %s_path + " %s"' % (dir_name, mode)
    to_insert += '\t\t\t\tthis->get_disk_content("oracle_%02d_mkdir.txt", %s);\n' % (func_count, desc)
    to_insert += '\n'

    if method == 'setup':
        contents.insert(index_map['setup'], to_insert)
        updateSetupMap(index_map, 5)
    else:
        contents.insert(index_map['run'], to_insert)
        updateRunMap(index_map, 5)


def insertOpenFile(contents, line, index_map, redeclare_map, method, func_count):
    name = 'fd_' + line.split(' ')[1]
    flag = line.split(' ')[2]
    mode = line.split(' ')[3]

    decl = ' '
    if name not in redeclare_map:
        decl = 'int '
        redeclare_map[name] = 1

    # TODO: prevent redeclations here
    to_insert = '\n\t\t\t\t' + decl + 'fd_' + line.split(' ')[1] + ' = cm_->CmOpen(' + line.split(' ')[1] + '_path.c_str() , ' + line.split(' ')[2] + ' , ' + line.split(' ')[3] + '); \n\t\t\t\tif ( fd_' + line.split(' ')[1] + ' < 0 ) {\n\t\t\t\t\treturn -1;\n\t\t\t\t}\n'

    if 'O_CREAT' in flag:
        desc = '"open " + %s_path + " %s %s"' % (line.split(' ')[1], flag, mode)
        to_insert += '\t\t\t\tthis->get_disk_content("oracle_%02d_open.txt", %s);\n' % (func_count, desc)
        to_insert += '\n'


    if method == 'setup':
        contents.insert(index_map['setup'], to_insert)
        updateSetupMap(index_map, 6)
    else:
        contents.insert(index_map['run'], to_insert)
        updateRunMap(index_map, 6)

def insertMknodFile(contents, line, index_map, redeclare_map, method):

    name = 'fd_' + line.split(' ')[1]
    decl = ' '
    if name not in redeclare_map:
        decl = 'int '
        redeclare_map[name] = 1

    # TODO: prevent redeclations here
    to_insert = '\n\t\t\t\t' + decl + 'fd_' + line.split(' ')[1] + ' = mknod(' + line.split(' ')[1] + '_path.c_str() , ' + line.split(' ')[2] + ' , ' + line.split(' ')[3] + '); \n\t\t\t\tif ( fd_' + line.split(' ')[1] + ' < 0 ) { \n\t\t\t\t\tcm_->CmClose( fd_' + line.split(' ')[1] + '); \n\t\t\t\t\treturn -1;\n\t\t\t\t}\n\n'

    if method == 'setup':
        contents.insert(index_map['setup'], to_insert)
        updateSetupMap(index_map, 6)
    else:
        contents.insert(index_map['run'], to_insert)
        updateRunMap(index_map, 6)

def insertOpenDir(contents, line, index_map, redeclare_map, method):

    name = 'fd_' + line.split(' ')[1]
    decl = ' '
    if name not in redeclare_map:
        decl = 'int '
        redeclare_map[name] = 1

    # TODO: prevent redeclations here
    to_insert = '\n\t\t\t\t' + decl + 'fd_' + line.split(' ')[1] + ' = cm_->CmOpen(' + line.split(' ')[1] + '_path.c_str() , O_DIRECTORY , ' + line.split(' ')[2] + '); \n\t\t\t\tif ( fd_' + line.split(' ')[1] + ' < 0 ) { \n\t\t\t\t\tcm_->CmClose( fd_' + line.split(' ')[1] + '); \n\t\t\t\t\treturn -1;\n\t\t\t\t}\n\n'

    if method == 'setup':
        contents.insert(index_map['setup'], to_insert)
        updateSetupMap(index_map, 6)
    else:
        contents.insert(index_map['run'], to_insert)
        updateRunMap(index_map, 6)


def insertRemoveFile(contents,option, line, index_map, method, func_count):
    fname = line.split(' ')[1]

    if option == "remove":
        to_insert = '\n'
        to_insert += '\t\t\t\tif (cm_->CmRemove(%s_path.c_str()) < 0){\n' % (fname)
        to_insert += '\t\t\t\t\treturn -1;\n'
        to_insert += '\t\t\t\t}\n'

        desc = '"remove " + %s_path' % (fname)
        to_insert += '\t\t\t\tthis->get_disk_content("oracle_%02d_remove.txt", %s);\n' % (func_count, desc)
        to_insert += '\n'
    else:
        to_insert = '\n'
        to_insert += '\t\t\t\tif (cm_->CmUnlink(%s_path.c_str()) < 0){\n' % (fname)
        to_insert += '\t\t\t\t\treturn -1;\n'
        to_insert += '\t\t\t\t}\n'

        desc = '"unlink " + %s_path' % (fname)
        to_insert += '\t\t\t\tthis->get_disk_content("oracle_%02d_unlink.txt", %s);\n' % (func_count, desc)
        to_insert += '\n'

    if method == 'setup':
        contents.insert(index_map['setup'], to_insert)
        updateSetupMap(index_map, 5)
    else:
        contents.insert(index_map['run'], to_insert)
        updateRunMap(index_map, 5)


def insertTruncateFile(contents, line, index_map, method, func_count):
    fname = line.split(' ')[1]
    size = line.split(' ')[2]

    to_insert = '\n'
    to_insert += '\t\t\t\tif (cm_->CmTruncate(%s_path.c_str(), %s) < 0) {\n' % (fname, size)
    to_insert += '\t\t\t\t\treturn -1;\n'
    to_insert += '\t\t\t\t}\n'

    desc = '"truncate " + %s_path + " %s"' % (fname, size)
    to_insert += '\t\t\t\tthis->get_disk_content("oracle_%02d_truncate.txt", %s);\n' % (func_count, desc)
    to_insert += '\n'

    if method == 'setup':
        contents.insert(index_map['setup'], to_insert)
        updateSetupMap(index_map, 5)
    else:
        contents.insert(index_map['run'], to_insert)
        updateRunMap(index_map, 5)


def insertClose(contents, line, index_map, method):
    to_insert = '\n\t\t\t\tif ( cm_->CmClose ( fd_' + line.split(' ')[1] + ') < 0){ \n\t\t\t\t\treturn -1;\n\t\t\t\t}\n\n'

    if method == 'setup':
        contents.insert(index_map['setup'], to_insert)
        updateSetupMap(index_map, 4)
    else:
        contents.insert(index_map['run'], to_insert)
        updateRunMap(index_map, 4)

def insertRmdir(contents, line, index_map, method, func_count):
    dir_name = line.split(' ')[1]

    to_insert = '\n'
    to_insert += '\t\t\t\tif (cm_->CmRmdir(%s_path.c_str()) < 0) {\n' % (dir_name)
    to_insert += '\t\t\t\t\treturn -1;\n'
    to_insert += '\t\t\t\t}\n'

    desc = '"rmdir " + %s_path' % (dir_name)
    to_insert += '\t\t\t\tthis->get_disk_content("oracle_%02d_rmdir.txt", %s);\n' % (func_count, desc)
    to_insert += '\n'

    if method == 'setup':
        contents.insert(index_map['setup'], to_insert)
        updateSetupMap(index_map, 5)
    else:
        contents.insert(index_map['run'], to_insert)
        updateRunMap(index_map, 5)


def insertFsync(contents, option,  line, index_map, method):
    if option == 'fsync':
        ins = 'cm_->CmFsync'
    elif option == 'fdatasync':
        ins = 'cm_->CmFdatasync'

    to_insert = '\n\t\t\t\tif ( ' + ins + '( fd_' + line.split(' ')[1] + ') < 0){ \n\t\t\t\t\treturn -1;\n\t\t\t\t}\n\n'

    if method == 'setup':
        contents.insert(index_map['setup'], to_insert)
        updateSetupMap(index_map, 4)
    else:
        contents.insert(index_map['run'], to_insert)
        updateRunMap(index_map, 4)


def insertSync(contents, line, index_map, method):
    to_insert = '\n\t\t\t\tcm_->CmSync(); \n\n'

    if method == 'setup':
        contents.insert(index_map['setup'], to_insert)
        updateSetupMap(index_map, 2)
    else:
        contents.insert(index_map['run'], to_insert)
        updateRunMap(index_map, 2)

#def insertCheckpoint(contents, line, index_map, method):
#
#    to_insert = '\n\t\t\t\tif ( Checkpoint() < 0){ \n\t\t\t\t\treturn -1;\n\t\t\t\t}\n\t\t\t\tlocal_checkpoint += 1; \n\t\t\t\tif (local_checkpoint == checkpoint) { \n\t\t\t\t\treturn 1;\n\t\t\t\t}\n\n'
#
#    if method == 'setup':
#        contents.insert(index_map['setup'], to_insert)
#        updateSetupMap(index_map, 8)
#    else:
#        contents.insert(index_map['run'], to_insert)
#        updateRunMap(index_map, 8)

def insertCheckpoint(contents, line, index_map, method):

    to_insert = '\n\t\t\t\tif ( cm_->CmCheckpoint() < 0){ \n\t\t\t\t\treturn -1;\n\t\t\t\t}\n\t\t\t\tlocal_checkpoint += 1; \n\t\t\t\tif (local_checkpoint == checkpoint) { \n\t\t\t\t\treturn '+ line.split(' ')[1] + ';\n\t\t\t\t}\n\n'

    if method == 'setup':
        contents.insert(index_map['setup'], to_insert)
        updateSetupMap(index_map, 8)
    else:
        contents.insert(index_map['run'], to_insert)
        updateRunMap(index_map, 8)


def insertRename(contents, line, index_map, method, func_count):
    src_fname = line.split(' ')[1]
    dst_fname = line.split(' ')[2]

    to_insert = '\n'
    to_insert += '\t\t\t\tif (cm_->CmRename(%s_path.c_str(), %s_path.c_str()) < 0) {\n' % (src_fname, dst_fname)
    to_insert += '\t\t\t\t\treturn -1;\n'
    to_insert += '\t\t\t\t}\n'

    desc = '"rename " + %s_path + " " + %s_path' % (src_fname, dst_fname)
    to_insert += '\t\t\t\tthis->get_disk_content("oracle_%02d_rename.txt", %s);\n' % (func_count, desc)
    to_insert += '\n'

    if method == 'setup':
        contents.insert(index_map['setup'], to_insert)
        updateSetupMap(index_map, 5)
    else:
        contents.insert(index_map['run'], to_insert)
        updateRunMap(index_map, 5)

def insertLink(contents, line, index_map, method, func_count):
    src_fname = line.split(' ')[1]
    dst_fname = line.split(' ')[2]

    to_insert = '\n'
    to_insert += '\t\t\t\tif (cm_->CmLink(%s_path.c_str(), %s_path.c_str()) < 0) {\n' % (src_fname, dst_fname)
    to_insert += '\t\t\t\t\treturn -1;\n'
    to_insert += '\t\t\t\t}\n'

    desc = '"link " + %s_path + " " + %s_path' % (src_fname, dst_fname)
    to_insert += '\t\t\t\tthis->get_disk_content("oracle_%02d_link.txt", %s);\n' % (func_count, desc)
    to_insert += '\n'

    if method == 'setup':
        contents.insert(index_map['setup'], to_insert)
        updateSetupMap(index_map, 5)
    else:
        contents.insert(index_map['run'], to_insert)
        updateRunMap(index_map, 5)

def insertSymlink(contents, line, index_map, method, func_count):
    src_fname = line.split(' ')[1]
    dst_fname = line.split(' ')[2]

    to_insert = '\n'
    to_insert += '\t\t\t\tif (cm_->CmSymlink(%s_path.c_str(), %s_path.c_str()) < 0) {\n' % (src_fname, dst_fname)
    to_insert += '\t\t\t\t\treturn -1;\n'
    to_insert += '\t\t\t\t}\n'

    desc = '"symlink " + %s_path + " " + %s_path' % (src_fname, dst_fname)
    to_insert += '\t\t\t\tthis->get_disk_content("oracle_%02d_symlink.txt", %s);\n' % (func_count, desc)
    to_insert += '\n'

    if method == 'setup':
        contents.insert(index_map['setup'], to_insert)
        updateSetupMap(index_map, 5)
    else:
        contents.insert(index_map['run'], to_insert)
        updateRunMap(index_map, 5)

def insertFsetxattr(contents, line, index_map, method):
    pass

def insertRemovexattr(contents, line, index_map, method):
    pass

def insertChmod(contents, line, index_map, method):
    pass

def insertWrite(contents, option, line, index_map, redeclare_map, method, func_count):
    if option == 'mmapwrite':
        name = 'filep_' + line.split(' ')[1]
        decl = ' '
        data_decl = ' '
        text_decl = ' '
        filep_decl = ' '
        moffset_decl = ' '

        if name not in redeclare_map:
            # decl = 'int '
            filep_decl = 'char *'
            data_decl = 'void* mdata_' +line.split(' ')[1] + ';'
            text_decl = 'const char *mtext_' + line.split(' ')[1] +'  = \"mmmmmmmmmmklmnopqrstuvwxyz123456\";'
            redeclare_map[name] = 1

        to_write = "to_write" + line.split(' ')[1]
        if to_write not in redeclare_map:
            decl = "int "
            redeclare_map[to_write] = 1

        moffset = 'moffset_'+ line.split(' ')[1]
        if moffset not in redeclare_map:
            moffset_decl = "int "
            redeclare_map[moffset] =1


        to_insert = '\n\t\t\t\tif ( fallocate( fd_' + line.split(' ')[1] + ' , 0 , ' + line.split(' ')[2] + ' , '  + line.split(' ')[3] + ') < 0){ \n\t\t\t\t\tcm_->CmClose( fd_' + line.split(' ')[1]  +');\n\t\t\t\t\t return -1;\n\t\t\t\t}\n\t\t\t\t' + filep_decl + 'filep_' + line.split(' ')[1] + ' = (char *) cm_->CmMmap(NULL, ' + line.split(' ')[3] + ' + ' + line.split(' ')[2]  +', PROT_WRITE|PROT_READ, MAP_SHARED, fd_' + line.split(' ')[1] + ', 0);\n\t\t\t\tif (filep_' + line.split(' ')[1] + ' == MAP_FAILED) {\n\t\t\t\t\t return -1;\n\t\t\t\t}\n\n\t\t\t\t' +moffset_decl+ 'moffset_'+ line.split(' ')[1] +' = 0;\n\t\t\t\t' + decl + to_write +' = ' + line.split(' ')[3] + ' ;\n\t\t\t\t'+ text_decl+ '\n\n\t\t\t\twhile (moffset_'+line.split(' ')[1]+' < '+ line.split(' ')[3] +'){\n\t\t\t\t\tif (' + to_write +' < 32){\n\t\t\t\t\t\tmemcpy(filep_'+ line.split(' ')[1]+ ' + ' + line.split(' ')[2] + ' + moffset_'+ line.split(' ')[1] +', mtext_'+ line.split(' ')[1] +', ' + to_write +');\n\t\t\t\t\t\tmoffset_'+ line.split(' ')[1]+' += ' + to_write +';\n\t\t\t\t\t}\n\t\t\t\t\telse {\n\t\t\t\t\t\tmemcpy(filep_'+ line.split(' ')[1] + ' + ' + line.split(' ')[2] + ' + moffset_' +line.split(' ')[1] + ',mtext_'+line.split(' ')[1] + ', 32);\n\t\t\t\t\t\tmoffset_'+line.split(' ')[1] +' += 32; \n\t\t\t\t\t} \n\t\t\t\t}\n\n\t\t\t\tif ( cm_->CmMsync ( filep_' + line.split(' ')[1] + ' + ' + line.split(' ')[2] + ', 8192 , MS_SYNC) < 0){\n\t\t\t\t\tcm_->CmMunmap( filep_' + line.split(' ')[1] + ',' + line.split(' ')[2] + ' + ' + line.split(' ')[3] +'); \n\t\t\t\t\treturn -1;\n\t\t\t\t}\n\t\t\t\tcm_->CmMunmap( filep_' + line.split(' ')[1] + ' , ' + line.split(' ')[2] + ' + ' +  line.split(' ')[3] +');\n\n'

        if method == 'setup':
            contents.insert(index_map['setup'], to_insert)
            updateSetupMap(index_map, 30)
        else:
            contents.insert(index_map['run'], to_insert)
            updateRunMap(index_map, 30)



    elif option == 'write':
        fname = line.split(' ')[1]
        off = line.split(' ')[2]
        length = line.split(' ')[3]

        to_insert = '\n'
        to_insert += '\t\t\t\tif (cm_->CmWriteData(fd_%s, %s, %s) < 0) {\n' % (fname, off, length)
        to_insert += '\t\t\t\t\treturn -1;\n'
        to_insert += '\t\t\t\t}\n'

        desc = '"write " + %s_path + " %s %s"' % (fname, off, length)
        to_insert += '\t\t\t\tthis->get_disk_content("oracle_%02d_write.txt", %s);\n' % (func_count, desc)
        to_insert += '\n'

        if method == 'setup':
            contents.insert(index_map['setup'], to_insert)
            updateSetupMap(index_map, 5)
        else:
            contents.insert(index_map['run'], to_insert)
            updateRunMap(index_map, 5)

    else:
        name = 'offset_' + line.split(' ')[1]
        decl = ' '
        write_decl = ''
        data_decl = ' '
        text_decl = ' '

        if name not in redeclare_map:
            decl = 'int '
            data_decl = 'void* data_' +line.split(' ')[1] + ';'
            text_decl = 'const char *text_' + line.split(' ')[1] +'  = \"ddddddddddklmnopqrstuvwxyz123456\";'
            redeclare_map[name] = 1

        to_write = "to_write" + line.split(' ')[1]
        if to_write not in redeclare_map:
            write_decl = "int "
            redeclare_map[to_write] = 1

        to_insert ='\n\t\t\t\tcm_->CmClose(fd_' + line.split(' ')[1] + '); \n\t\t\t\tfd_' + line.split(' ')[1] + ' = cm_->CmOpen(' + line.split(' ')[1] +'_path.c_str() , O_RDWR|O_DIRECT|O_SYNC , 0777); \n\t\t\t\tif ( fd_' + line.split(' ')[1] +' < 0 ) {\n\t\t\t\t\treturn -1;\n\t\t\t\t}\n\n\t\t\t\t' + data_decl+'\n\t\t\t\tif (posix_memalign(&data_' + line.split(' ')[1] +' , 4096, ' + line.split(' ')[3] +' ) < 0) {\n\t\t\t\t\treturn -1;\n\t\t\t\t}\n\n\t\t\t\t \n\t\t\t\t' +decl+ 'offset_'+ line.split(' ')[1] +' = 0;\n\t\t\t\t' + write_decl + to_write +' = ' + line.split(' ')[3] + ' ;\n\t\t\t\t'+ text_decl+ '\n\t\t\t\twhile (offset_'+line.split(' ')[1]+' < '+ line.split(' ')[3] +'){\n\t\t\t\t\tif (' + to_write +' < 32){\n\t\t\t\t\t\tmemcpy((char *)data_'+ line.split(' ')[1]+ '+ offset_'+ line.split(' ')[1] +', text_'+ line.split(' ')[1] +', ' + to_write +');\n\t\t\t\t\t\toffset_'+ line.split(' ')[1]+' += ' + to_write +';\n\t\t\t\t\t}\n\t\t\t\t\telse {\n\t\t\t\t\t\tmemcpy((char *)data_'+ line.split(' ')[1] +'+ offset_'+line.split(' ')[1] +',text_'+line.split(' ')[1] +', 32);\n\t\t\t\t\t\toffset_'+line.split(' ')[1] +' += 32; \n\t\t\t\t\t} \n\t\t\t\t} \n\n\t\t\t\tif ( cm_->CmPwrite ( fd_' + line.split(' ')[1] + ', data_'+ line.split(' ')[1] + ', '  + line.split(' ')[3] + ', ' + line.split(' ')[2] +') < 0){\n\t\t\t\t\treturn -1;\n\t\t\t\t}\n'

        desc = '"dwrite " + %s_path + " %s %s"' % (line.split(' ')[1], line.split(' ')[2], line.split(' ')[3])
        to_insert += '\t\t\t\tthis->get_disk_content("oracle_%02d_dwrite.txt", %s);\n' % (func_count, desc)
        to_insert += '\n'

        if method == 'setup':
            contents.insert(index_map['setup'], to_insert)
            updateSetupMap(index_map, 31)
        else:
            contents.insert(index_map['run'], to_insert)
            updateRunMap(index_map, 31)


# Insert a function in 'line' into 'file' at location specified by 'index_map' in the specified 'method'
# If the workload has functions with various possible paramter options, the 'permutation' defines the set of
# paramters to be set in this file.

def insertFunctions(line, file, index_map, redeclare_map, method, func_count):
    with open(file, 'r+') as insert:

        contents = insert.readlines()

        if line.split(' ')[0] == "mark":
            pass
            # if method == 'setup':
            #     updateSetupMap(index_map, 1)
            # else:
            #     updateRunMap(index_map, 1)
            # insertMark(contents, line, index_map, method)

        if line.split(' ')[0] == 'falloc':
            if method == 'setup':
                updateSetupMap(index_map, 1)
            else:
                updateRunMap(index_map, 1)

            func_count += 1
            insertFalloc(contents, line, index_map, method, func_count)
            if line.split(' ')[-2] == 'addToSetup':
                line = line.replace(line.split(' ')[1], line.split(' ')[-1], 1)
                insertFalloc(contents, line, index_map, 'setup')

        elif line.split(' ')[0] == 'mkdir':
            if method == 'setup':
                updateSetupMap(index_map, 1)
            else:
                updateRunMap(index_map, 1)

            func_count += 1
            insertMkdir(contents, line, index_map, method, func_count)

        elif line.split(' ')[0] == 'mknod':
            pass
            # if method == 'setup':
            #     updateSetupMap(index_map, 1)
            # else:
            #     updateRunMap(index_map, 1)
            # insertMknodFile(contents, line, index_map, redeclare_map, method)


        elif line.split(' ')[0] == 'open':
            if method == 'setup':
                updateSetupMap(index_map, 1)
            else:
                updateRunMap(index_map, 1)
            func_count += 1
            insertOpenFile(contents, line, index_map, redeclare_map, method, func_count)

        elif line.split(' ')[0] == 'opendir':
            if method == 'setup':
                updateSetupMap(index_map, 1)
            else:
                updateRunMap(index_map, 1)
            insertOpenDir(contents, line, index_map, redeclare_map, method)

        elif line.split(' ')[0] == 'remove' or line.split(' ')[0] == 'unlink':
            if method == 'setup':
                updateSetupMap(index_map, 1)
            else:
                updateRunMap(index_map, 1)
            option = line.split(' ')[0]
            func_count += 1
            insertRemoveFile(contents, option, line, index_map, method, func_count)

        elif line.split(' ')[0] == 'close':
            if method == 'setup':
                updateSetupMap(index_map, 1)
            else:
                updateRunMap(index_map, 1)
            insertClose(contents, line, index_map, method)

        elif line.split(' ')[0] == 'rmdir':
            if method == 'setup':
                updateSetupMap(index_map, 1)
            else:
                updateRunMap(index_map, 1)
            func_count += 1
            insertRmdir(contents, line, index_map, method, func_count)

        elif line.split(' ')[0] == 'truncate':
            if method == 'setup':
                updateSetupMap(index_map, 1)
            else:
                updateRunMap(index_map, 1)
            func_count += 1
            insertTruncateFile(contents, line, index_map, method, func_count)

        elif line.split(' ')[0] == 'fsync' or line.split(' ')[0] == 'fdatasync':
            if method == 'setup':
                updateSetupMap(index_map, 1)
            else:
                updateRunMap(index_map, 1)
            option = line.split(' ')[0]
            insertFsync(contents, option, line, index_map, method)

        elif line.split(' ')[0] == 'sync':
            if method == 'setup':
                updateSetupMap(index_map, 1)
            else:
                updateRunMap(index_map, 1)
            insertSync(contents, line, index_map, method)

        elif line.split(' ')[0] == 'checkpoint':
            pass
            # if method == 'setup':
            #     updateSetupMap(index_map, 1)
            # else:
            #     updateRunMap(index_map, 1)
            # insertCheckpoint(contents, line, index_map, method)

        elif line.split(' ')[0] == 'rename':
            if method == 'setup':
                updateSetupMap(index_map, 1)
            else:
                updateRunMap(index_map, 1)
            func_count += 1
            insertRename(contents, line, index_map, method, func_count)

        elif line.split(' ')[0] == 'fsetxattr':
            if method == 'setup':
                updateSetupMap(index_map, 1)
            else:
                updateRunMap(index_map, 1)
            insertFsetxattr(contents, line, index_map, method)

        elif line.split(' ')[0] == 'removexattr':
            if method == 'setup':
                updateSetupMap(index_map, 1)
            else:
                updateRunMap(index_map, 1)
            insertRemovexattr(contents, line, index_map, method)

        elif line.split(' ')[0] == 'chmod':
            pass
            # if method == 'setup':
            #     updateSetupMap(index_map, 1)
            # else:
            #     updateRunMap(index_map, 1)
            # insertChmod(contents, line, index_map, method)

        elif line.split(' ')[0] == 'link':
            if method == 'setup':
                updateSetupMap(index_map, 1)
            else:
                updateRunMap(index_map, 1)
            # option = line.split(' ')[0]
            func_count += 1
            insertLink(contents, line, index_map, method, func_count)

        elif line.split(' ')[0] == 'symlink':
            if method == 'setup':
                updateSetupMap(index_map, 1)
            else:
                updateRunMap(index_map, 1)
            # option = line.split(' ')[0]
            func_count += 1
            insertSymlink(contents, line, index_map, method, func_count)

        elif line.split(' ')[0] == 'write' or line.split(' ')[0] == 'dwrite' or line.split(' ')[0] == 'mmapwrite':
            if method == 'setup':
                updateSetupMap(index_map, 1)
            else:
                updateRunMap(index_map, 1)
            option = line.split(' ')[0]
            func_count += 1
            insertWrite(contents, option, line, index_map, redeclare_map, method, func_count)

        elif line.split(' ')[0] == 'createSnapshot':
            if method == 'setup':
                updateSetupMap(index_map, 1)
            else:
                updateRunMap(index_map, 1)
            insertCreateSnapshot(contents, line, index_map, redeclare_map, method)

        elif line.split(' ')[0] == 'deleteSnapshot':
            if method == 'setup':
                updateSetupMap(index_map, 1)
            else:
                updateRunMap(index_map, 1)
            insertDeleteSnapshot(contents, line, index_map, redeclare_map, method)

        elif line.split(' ')[0] == 'none':
            pass

        insert.seek(0)
        insert.writelines(contents)
        insert.close()

    return func_count


def generateOneCpp(base_cpp_file, j_lang_file, target_path):
    #Create a pre-populated dictionary of replacable operations
    operation_map = create_dict()

    #Copy base file to target path
    base_cpp_file = os.path.join(target_path, os.path.basename(base_cpp_file))
    j_lang_file = os.path.join(target_path + "/j-lang-files", os.path.basename(j_lang_file))

    index_map = {'define' : 0, 'setup' : 0, 'run' : 0}
    redeclare_map = {}
    func_count = 0

    #iterate through the base file and populate these values
    index = 0
    with open(base_cpp_file, 'r') as f:
        contents = f.readlines()
        for index, line in enumerate(contents):
            index += 1
            line = line.strip()
            if line.find('virtual int setup()') != -1:
                if line.split(' ')[2] == 'setup()':
                    index_map['setup'] = index
            elif line.find('virtual int run()') != -1:
                if line.split(' ')[2] == 'run()':
                    index_map['run'] = index
            elif line.find('private') != -1:
                if line.split(' ')[0] == 'private:':
                    index_map['define'] = index
    f.close()

    val = 0
    new_cpp_file = os.path.basename(j_lang_file)  + ".cpp"
    new_cpp_file = os.path.join(target_path, new_cpp_file)
    copyfile(base_cpp_file, new_cpp_file)

    new_index_map = index_map.copy()
    #Iterate through test file and fill up method by method
    with open(j_lang_file, 'r') as f:
        iter = 0
        for line in f:

            #ignore newlines
            if line.split(' ')[0] == '\n':
                continue

            #Remove leading, trailing spaces
            line = line.strip()

            #if the line starts with #, it indicates which region of base file to populate and skip this line
            if line.split(' ')[0] == '#' :
                method = line.strip().split()[-1]
                continue

            if method == 'define':
                insertDefine(line, new_cpp_file, new_index_map, redeclare_map)

            elif method == 'declare':
                insertDeclare(line, new_cpp_file, new_index_map, redeclare_map)

            elif (method == 'setup' or method == 'run'):
                op_map={}
                func_count = insertFunctions(line, new_cpp_file, new_index_map, redeclare_map, method, func_count)

    f.close()
    val += 1

def generateOneCppParallel(thread_id, input_dir, base_cpp_file, j_lang_file_list, lower_idx, upper_idx):
    percent_1_span = (upper_idx - lower_idx) // 100
    for idx in tqdm(range(lower_idx, upper_idx), desc=f'thd #{thread_id}'):
        # if idx == lower_idx + percent_1_span * 10:
        #     print(f"thread: {thread_id}: completed 10%\n")
        # elif idx == lower_idx + percent_1_span * 20:
        #     print(f"thread: {thread_id}: completed 20%\n")
        # elif idx == lower_idx + percent_1_span * 30:
        #     print(f"thread: {thread_id}: completed 30%\n")
        # elif idx == lower_idx + percent_1_span * 40:
        #     print(f"thread: {thread_id}: completed 40%\n")
        # elif idx == lower_idx + percent_1_span * 50:
        #     print(f"thread: {thread_id}: completed 50%\n")
        # elif idx == lower_idx + percent_1_span * 60:
        #     print(f"thread: {thread_id}: completed 60%\n")
        # elif idx == lower_idx + percent_1_span * 70:
        #     print(f"thread: {thread_id}: completed 70%\n")
        # elif idx == lower_idx + percent_1_span * 80:
        #     print(f"thread: {thread_id}: completed 80%\n")
        # elif idx == lower_idx + percent_1_span * 90:
        #     print(f"thread: {thread_id}: completed 90%\n")
        # elif idx == lower_idx + percent_1_span * 100:
        #     print(f"thread: {thread_id}: completed 100%\n")

        j_lang_file = j_lang_file_list[idx]
        # print(thread_id, base_cpp_file, j_lang_file, input_dir)
        generateOneCpp(base_cpp_file, j_lang_file, input_dir)

    return 0

def main():
    args = parse_args()
    cpus = args.cpus
    input_dir = args.input
    j_file_dir = "%s/j-lang-files" % (input_dir)
    base_cpp_file = "%s/base.cpp" % (input_dir)
    j_lang_file_list = [f for f in os.listdir(j_file_dir) if os.path.isfile(os.path.join(j_file_dir, f))]

    files_per_cpu = len(j_lang_file_list)//cpus
    range_cpus = []
    for i in range(cpus):
        # one cpu runs on [lower_idx, upper_idx)
        lower_idx = i * files_per_cpu + 1
        upper_idx = (i + 1) * files_per_cpu + 1
        if i == 0:
            lower_idx = 0
        if i + 1 == cpus:
            upper_idx = len(j_lang_file_list)
        range_cpus.append([lower_idx, upper_idx])

    print(range_cpus)
    with concurrent.futures.ThreadPoolExecutor(max_workers=cpus) as executor:
        # Submit tasks to the thread pool
        future_to_task = {executor.submit(generateOneCppParallel, i, input_dir, base_cpp_file, j_lang_file_list, range_cpus[i][0], range_cpus[i][1]): i for i in range(len(range_cpus))}

        # Process the results as they become available
        for future in concurrent.futures.as_completed(future_to_task):
            task_id = future_to_task[future]
            try:
                result = future.result()
                if result == 0:
                    pass
                else:
                    print("failed")
            except Exception as e:
                traceback.print_exc()
                print(f"Task {task_id} generated an exception: {e.__class__.__name__,}: {e}")

if __name__ == '__main__':
	main()